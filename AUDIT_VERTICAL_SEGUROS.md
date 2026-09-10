# AUDIT_VERTICAL_SEGUROS.md

Primer trabajo real de la vertical Seguros (ciclo Multirriesgo: captación →
venta → gestión → siniestros), construido desde cero sobre `main` limpio en
la rama `feature/vertical-seguros`. Sin merge ni push a `main` en ningún
momento.

Rama: `feature/vertical-seguros` (creada desde `main`, commit base
`97b949a`).

Commits:
- `89fd215` — modelos `InsurancePolicy`/`InsuranceClaim` + migración 0043 con RLS real.
- `25aeb47` — endpoints REST `/api/v1/insurance` (policies + claims).
- `5337242` — frontend Seguros (listado, alta de póliza, siniestros).

---

## 1. Qué se construyó

### Backend

- `backend/app/models/insurance.py` — `InsurancePolicy`, `InsuranceClaim`,
  enums `PolicyStatus`/`ClaimStatus`.
- `backend/app/schemas/insurance.py` — schemas Pydantic (create/update/inDB/
  response/list) para pólizas y siniestros, incluido `ClaimDocument`.
- `backend/alembic/versions/0043_insurance_policies_claims.py` — migración
  real (siguiente número correlativo tras `0042_zeus_domain_events.py`, la
  última existente en `main`).
- `backend/app/api/v1/endpoints/insurance.py` — endpoints REST reales.
- `backend/app/api/v1/__init__.py` — router registrado bajo `/api/v1/insurance`.
- `backend/app/db/base.py` — import de los nuevos modelos añadido a
  `create_tables()` para que el `create_all()` de arranque local (SQLite)
  los cree, igual que el resto de modelos del proyecto.

### Frontend

- `frontend/src/views/InsuranceView.vue` — listado de pólizas, alta de
  póliza, detalle de póliza con sus siniestros, apertura de siniestro
  (con adjunto real vía `POST /api/v1/upload`), cambio de estado de
  siniestro.
- `frontend/src/router/index.js` — ruta `/insurance` registrada (top-level,
  mismo patrón que `/office-crm`).
- `frontend/src/components/DashboardProfesional.vue` — entrada de menú
  "Seguros" (🛡️) en la barra lateral, visible para cualquier usuario no
  empleado.
- `frontend/src/i18n/locales/{es,en}.json` — clave `dashboardPro.nav.insurance`.

---

## 2. Decisiones de diseño

### `coverages` / `insured_risk` — JSON libre, no columnas fijas

`InsurancePolicy.coverages` y `InsurancePolicy.insured_risk` son columnas
JSON sin esquema fijo. Multirriesgo hoy usa claves como `hogar`, `incendio`,
`robo`, `responsabilidad_civil_capital`; otro ramo (Auto, Vida, Salud...)
mañana usará otras claves, sin necesidad de una migración de esquema nueva.
El frontend construye un subconjunto razonable de esas claves para
Multirriesgo, pero el backend no las valida por nombre — solo exige que
`coverages` sea un objeto.

### `status` con `values_callable` — evita desde el origen el bug ya conocido

El módulo ERP (`erp.py`) tuvo un bug real y ya corregido (documentado en
`CICLO_PRODUCCION.md`, Ciclo 2, en otra rama no fusionada): SQLAlchemy
guardaba los Enum por **nombre** en mayúscula, Pydantic serializaba por
**valor** en minúscula, y el `commit()` ocurría antes del `refresh()`,
dejando filas corruptas persistidas tras un 500. Aquí se evita ese patrón
desde el modelo: `Column(SAEnum(PolicyStatus, values_callable=lambda e:
[x.value for x in e], name=...))` hace que SQLAlchemy lea/escriba por
**valor** en minúscula, igual que Pydantic. Verificado en vivo: crear,
listar, filtrar y actualizar por `status` funciona sin `LookupError` en
ningún punto de la sesión de pruebas.

### `InsuranceClaim.company_id` duplicado a propósito

Aunque `company_id` ya es derivable vía `InsuranceClaim.policy.company_id`,
se duplicó como columna propia para que tanto el filtro de aplicación como
las políticas RLS de Postgres no dependan de un JOIN para aislar por
tenant — mismo criterio que ya usa `agent_activities` en la migración de
referencia consultada (`feature/multi-tenant-bd:0047_row_level_security.py`).

### Diseño de rutas — anidado, sin `GET /claims` como colección "primaria" separada

Implementado (decisión propia, la tarea dejaba abierto elegir):
- `POST /api/v1/insurance/policies`, `GET .../policies`, `GET .../policies/{id}`
- `GET /api/v1/insurance/policies/{id}/claims` — siniestros anidados bajo su póliza (usado por el frontend para el detalle).
- `POST /api/v1/insurance/claims`, `GET /api/v1/insurance/claims`, `GET/PATCH .../claims/{id}`

Se mantuvo también `GET /api/v1/insurance/claims` (colección plana, filtrable
por `policy_id`/`status`) porque es útil para una futura vista "todos los
siniestros abiertos de la empresa" sin tener que iterar pólizas — no lo usa
el frontend actual, pero está probado y documentado.

### Adjuntos de siniestro — reutiliza el upload real existente, no un storage nuevo

`InsuranceClaim.documents` es una lista JSON de referencias
(`{name, url, content_type, size_bytes, uploaded_at}`). El frontend sube el
fichero real a `POST /api/v1/upload` (el mecanismo unificado ya usado en el
resto del proyecto, con límite de tamaño y tipos permitidos) y adjunta la
URL devuelta al crear el siniestro. No se construyó un sistema de storage
nuevo, tal como pedía explícitamente la tarea.

### `company_type` — NO se creó uno nuevo para Seguros

Se revisó el código real (`frontend/src/utils/companyModules.ts`,
`router/index.js`) antes de decidir. `MODULES_BY_TYPE` hoy solo conoce
`bar_restaurant` y `office`, y `ROUTE_MODULE_MAP` solo gatea 4 rutas
(`TPV`, `ControlHorario`, `OfficeCrm`, `PayrollDrafts`). Construir un
`company_type: 'insurance'` nuevo habría exigido tocar el backend de
`/company/config`/`/auth/me` (fuera del alcance de esta tarea) para un
beneficio dudoso en esta primera versión. Decisión: la ruta `/insurance` **no
se añadió a `ROUTE_MODULE_MAP`**, por lo que `routeAllowed()` la deja pasar
igual que cualquier ruta no listada (comportamiento por defecto del propio
código, no un bypass añadido). El botón de menú se muestra a cualquier
usuario no-empleado autenticado, mismo criterio que ya usa "Ajustes". Es una
decisión deliberadamente simple para esta primera entrega — si Seguros
necesita ocultarse para empresas de otras verticales en el futuro, hay que
extender `companyModules.ts` explícitamente.

---

## 3. Verificación de RLS — qué es real y qué NO se pudo verificar en runtime

**Entorno confirmado:** no hay Postgres ni Docker disponibles en esta
sesión (`where docker`, `where psql` → sin resultados), igual que en todos
los ciclos anteriores documentados en `CICLO_PRODUCCION.md`. El desarrollo
local corre sobre SQLite (`backend/zeus.db`).

**Lo que SÍ se verificó, real, no simulado:**

1. **Migración aplicada con el CLI real de Alembic** (`alembic upgrade
   0043` / `alembic downgrade 0042`) contra una base SQLite aislada y
   fresca (`/tmp/alembic_verify.db`, con `companies`/`customers`/`users`
   mínimas y `alembic_version` estampada en `0042`) — no solo `create_all()`
   de la app. Confirmado por inspección directa del esquema resultante:
   ambas tablas, todas las columnas, todos los índices (`ix_insurance_
   policies_company_id`, `ix_insurance_policies_customer_id`,
   `ix_insurance_policies_policy_number` único, `ix_insurance_claims_
   policy_id`, `ix_insurance_claims_company_id`) presentes y correctos.
   `downgrade` también verificado sin error.
2. **No-op confirmado en SQLite**: el bloque RLS/rol `zeus_app` no se
   ejecuta (guardado por `_is_postgres()`), consistente con el resto de
   migraciones del proyecto que ya usan este mismo patrón de guardia por
   dialecto.
3. **Revisión manual línea a línea del SQL específico de Postgres** (no
   solo "se ve bien"): confirmado que `USING (...)` sin `WITH CHECK`
   explícito hace que Postgres reutilice la misma expresión para
   `WITH CHECK` en política `ALL` (comportamiento documentado de
   PostgreSQL), por lo que también protege escrituras, no solo lecturas.
   Confirmado que `GRANT`/`REVOKE` son ejecutables directamente dentro de
   un bloque `DO $$ ... $$` sin necesidad de `EXECUTE` (SPI de PL/pgSQL).
   Confirmado que los nombres de excepción `insufficient_privilege` y
   `undefined_object` son condiciones SQLSTATE válidas de Postgres.

**Lo que NO se pudo verificar (declarado explícitamente, no simulado):**

- **No se ejecutó el bloque de RLS/rol contra un Postgres real.** No se
  puede confirmar en runtime que `zeus_app` conectado con `SET
  app.current_company_id = 'X'` solo vea filas de esa empresa, ni que una
  query sin ese contexto vea 0 filas (diseño fail-closed, ver más abajo).
  Esto es una limitación del entorno, no una omisión de trabajo — igual
  limitación que declararon honestamente los ciclos anteriores del núcleo.
- No se probó el camino de fallo real de `CREATE ROLE` por privilegios
  insuficientes (el `EXCEPTION WHEN insufficient_privilege` es defensivo,
  no ejercitado).

**Diseño de las policies — fail-closed, distinto del patrón de referencia:**

La migración de referencia consultada (`feature/multi-tenant-bd:
0047_row_level_security.py`, solo para entender el patrón, no copiada
literal) usa un diseño "fail-open cuando no hay contexto" (si nadie fijó
`app.current_company_id`, deja ver todo) — justificado allí porque
protegía tablas legacy con consumidores que aún no habían migrado a
`get_db_scoped()`. Aquí, al ser tablas completamente nuevas sin ningún
consumidor legacy, se optó por **fail-closed**: sin contexto fijado, la
policy no deja ver ninguna fila. Es más estricto y no depende de que cada
endpoint recuerde fijar el contexto para tener protección real. Detalle
completo de la justificación en los comentarios de cabecera de
`0043_insurance_policies_claims.py`.

**Rol `zeus_app`:** creado sin `SUPERUSER`/`BYPASSRLS`/`CREATEDB`/
`CREATEROLE`, con `LOGIN` pero **sin contraseña fijada en la migración**
(fijarla en un fichero versionado sería el mismo antipatrón de credenciales
hardcodeadas ya señalado como hallazgo en `CICLO_PRODUCCION.md`, Ciclo 6).
La contraseña real debe fijarse fuera de banda (`ALTER ROLE zeus_app WITH
PASSWORD '...'`) usando el gestor de secretos de Railway. Esto queda
pendiente de que alguien con acceso a Postgres real de producción/staging
lo haga y verifique en runtime — no se puede cerrar en esta sesión.

---

## 4. Verificación backend — real, con curl, dos tenants propios

Backend real levantado limpio (`uvicorn app.main:app --port 8000`, tras
matar un proceso residual de sesión anterior en el puerto 8000 — nota de
transparencia: al iniciar la tarea ya había un `uvicorn --reload` huérfano
corriendo en el puerto 8000 desde antes de esta sesión, que había recreado
las tablas de `insurance` automáticamente al detectar mis archivos nuevos;
se mató y se relanzó limpio para tener control total sobre la versión de
código servida).

Dos empresas nuevas registradas por mí mismo vía `POST /api/v1/auth/
register` (no reutilicé tokens de nadie): `seguros.a@zeustest.com`
(`company_id=1029`) y `seguros.b@zeustest.com` (`company_id=1030`).

Casos probados con resultado exacto:

| Caso | Resultado |
|---|---|
| `GET /insurance/policies` sin token | `401` |
| `GET /insurance/policies` con token basura | `401` |
| `POST /insurance/policies` (A, cliente propio) | `201`, `policy_number` generado, `company_id=1029` |
| `GET /insurance/policies` (A) | `200`, 1 póliza |
| `GET /insurance/policies` (B) | `200`, 0 pólizas (aislamiento confirmado) |
| `GET /insurance/policies/1` (B, póliza de A) | `404` |
| `GET /insurance/policies/1` (A, propia) | `200` |
| `POST /insurance/policies` (B, con `customer_id` de A) | `404` "Customer not found" |
| `POST /insurance/claims` (A, sobre póliza propia) | `201`, con `documents` real |
| `POST /insurance/claims` (B, sobre póliza de A) | `404` "Policy not found" |
| `GET /insurance/policies/1/claims` (B) | `404` |
| `GET /insurance/claims/1` (B) | `404` |
| `PATCH /insurance/claims/1` (B) | `404` |
| `PATCH /insurance/claims/1` (A): `investigating` → `resolved` + `resolved_amount` | `200` en ambos pasos, datos persistidos correctamente |

Todos los comandos `curl` exactos se ejecutaron en vivo durante esta sesión
(no se resumen aquí por espacio, pero cada uno de los resultados de la
tabla corresponde a una llamada real, con payloads reales, contra el
servidor real).

---

## 5. Verificación E2E real con el navegador (Claude Browser / equivalente Playwright)

Backend (puerto 8000) y frontend (`vite`, puerto 5173) reales levantados,
tras matar procesos residuales previos en ambos puertos (uno en 5173 no
respondía a peticiones — proceso zombie de una sesión anterior; se mató y
se relanzó limpio).

Pasos ejecutados y confirmados con capturas de pantalla reales durante la
sesión (lectura de página + screenshots, equivalentes a Playwright):

1. **Login real** como `seguros.a@zeustest.com` en `http://localhost:5173/login`
   → redirección a `/dashboard` ("Panel").
2. **Navegación a `/insurance`** → vista carga con "Pólizas (1)" (la póliza
   creada antes por curl, confirmando que lee datos reales de la misma BD).
3. **Creación de póliza real desde el formulario del navegador** (no curl):
   seleccionado cliente "Cliente Multirriesgo A" del combobox real
   (poblado por `GET /api/v1/crm/customers`), prima `499.90`, coberturas
   Hogar+Incendio marcadas por defecto → clic en "Crear póliza" → la tabla
   pasó a "Pólizas (2)" con la nueva póliza `POL-20260819-BC6344` visible
   con los datos correctos.
4. **Apertura de siniestro real desde el navegador**: clic en "Ver" sobre
   la póliza nueva → detalle muestra "Siniestros (0)", coberturas "Hogar"/
   "Incendio" correctas → clic en "Abrir siniestro" → descripción
   "Rotura de cristal en ventana del salon por tormenta", importe estimado
   `220` → clic en "Abrir siniestro" → "Siniestros (1)" con la fila nueva,
   estado "Abierto", importe "220,00 €".
5. **Cambio de estado desde el navegador**: select de estado cambiado a
   "En investigación" → clic en "Guardar" → la tabla se refrescó desde el
   backend y el pill de estado pasó a mostrar "En investigación" (color
   correspondiente).
6. **Verificación de red real**: `read_network_requests` confirmó que cada
   paso disparó la llamada real esperada contra `localhost:8000`
   (`POST /insurance/policies` → 201, `POST /insurance/claims` → 201,
   `PATCH /insurance/claims/2` → 200, más los `GET` de refresco), sin
   ningún 500 ni error en el flujo de Seguros. Los pocos errores de
   consola detectados (`500`, `ERR_CONNECTION_REFUSED`) correspondieron a
   tráfico previo/no relacionado (reinicios de servidor durante el
   arranque de la sesión), no al flujo de Seguros verificado.
7. **Menú lateral**: confirmado por lectura de accesibilidad de la página
   (`read_page`) que el botón "🛡️ Seguros" aparece en la barra lateral
   entre "CRM oficina" y "Ajustes", y que un clic real sobre él navega a
   `/insurance` (título de pestaña cambia a "Seguros - ZEUS-IA").
8. **Aislamiento de tenant**: verificado por API directa (curl, sección 4),
   tal como permite explícitamente el criterio de la tarea porque el flujo
   de navegador ya cubrió el camino feliz con la Empresa A.

---

## 6. Regresión

Baseline establecido **antes** de tocar código (`git stash` de todos los
archivos nuevos/modificados, vuelta a `main` limpio, suite ejecutada):

```
7 failed, 214 passed, 2 skipped, 30 warnings, 3 errors in 104.73s
```

Tras aplicar todos los cambios de esta tarea, suite ejecutada de nuevo dos
veces (una antes del trabajo de frontend, otra al final de todo):

```
7 failed, 214 passed, 2 skipped, 30 warnings, 3 errors in 88-93s
```

**Idéntico al baseline** — mismos 7 tests fallidos (preexistentes, no
relacionados con Seguros: `test_config_loading`, `test_justicia_control_
layer_v1`, `test_perseo_autofix_v2`, 3x `test_thalos_control_layer_v1`,
`test_thalos_safe_v1`) y mismos 3 errores (`test_app.py`, `TestClient` no
definido, preexistente). Sin regresión.

---

## 7. Hallazgos fuera de alcance (no corregidos en este trabajo, declarados)

1. **`create_tables()` (bootstrap desde cero) está roto de forma
   preexistente**, no relacionado con Seguros: al intentar levantar una
   base SQLite completamente vacía con `Base.metadata.create_all()`, falla
   con `NoReferencedTableError: ... company_employees ...` porque el
   modelo `CompanyEmployee` no está en la lista de imports explícitos de
   `create_tables()` (backend/app/db/base.py) pese a que `TimeCostCheckin`
   sí lo está y lo referencia por FK. En la práctica esto no se nota
   porque el `zeus.db` de desarrollo local ya tiene historial acumulado de
   sesiones anteriores y esas tablas ya existen — pero un entorno
   realmente nuevo (o un test que borre `zeus.db` y arranque desde cero)
   se rompería en el primer arranque. Descubierto al intentar construir un
   entorno de verificación aislado para la migración 0043; no es un bug de
   esta tarea, no se tocó.
2. **La cadena completa de migraciones Alembic (`0001`→`0042`) no se puede
   ejecutar desde cero contra una base nueva**: `0003_add_fiscal_fields_
   to_document_approval.py` falla con `no such table: document_approvals`
   porque esa tabla nunca se crea vía Alembic en `0001`/`0002` (se creaba
   por otro camino, probablemente `create_all()` legacy). Confirma que
   ningún ciclo anterior de este proyecto ha probado realmente `alembic
   upgrade head` desde cero — todos dependían de `create_all()`. Mi propia
   migración 0043 SÍ se verificó de forma aislada (ver sección 3), pero la
   cadena completa alrededor tiene este problema preexistente, ajeno a mi
   trabajo.
3. **RLS/rol `zeus_app` sin verificación en runtime** (ya declarado en la
   sección 3) — requiere Postgres real, no disponible en este entorno.
   Pendiente de que alguien con acceso a staging/Railway lo verifique antes
   de confiar en él para producción.
4. Datos de prueba dejados en `backend/zeus.db` local: 2 empresas
   (`seguros.a@zeustest.com` / `seguros.b@zeustest.com`), 1 cliente CRM, 2
   pólizas y 1 siniestro. Sin impacto en producción/Railway (BD local
   SQLite), revertible si se pide.

---

## 8. Qué queda pendiente / decisiones que requieren al usuario

- **Contraseña real del rol `zeus_app`** debe fijarse en Postgres de
  staging/producción fuera de esta migración (variable de entorno /
  gestor de secretos de Railway) antes de que la aplicación pueda
  conectarse efectivamente con ese rol.
- **La aplicación todavía no usa el rol `zeus_app` para conectarse** —
  esta migración prepara la infraestructura de RLS (tablas, policies, rol)
  pero el motor de conexión de la app (`app/db/base.py`, `DATABASE_URL`)
  sigue usando el rol de conexión principal actual. Cambiar la conexión de
  runtime a `zeus_app` (y fijar `app.current_company_id` por request, al
  estilo de `get_db_scoped()` visto en `feature/multi-tenant-bd`) es
  trabajo adicional, fuera del alcance pedido para este primer commit de
  la vertical.
- **Verificación de RLS en runtime contra Postgres real** — bloqueada por
  falta de entorno, pendiente de staging.
- **Decisión de `company_type`**: documentada arriba (no se creó uno
  nuevo). Si el usuario quiere ocultar "Seguros" para empresas de otras
  verticales en el futuro, es trabajo adicional sobre
  `companyModules.ts` + backend de `/company/config`.
- Los 3 hallazgos preexistentes de la sección 7 (bootstrap roto desde
  cero, cadena Alembic no ejecutable desde `0001`, RLS no runtime-
  verificado) quedan para que el usuario decida si se abordan como tareas
  nuevas.
