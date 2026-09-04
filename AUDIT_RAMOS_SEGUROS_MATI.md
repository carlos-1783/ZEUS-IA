# AUDIT_RAMOS_SEGUROS_MATI.md

Continuación y cierre de verificación del piloto Mati (agente exclusiva
Catalana Occidente, vertical Seguros) sobre `feature/vertical-seguros`. Un
ejecutor anterior en esta misma tarea fue cortado por límite de sesión
dejando 4 commits reales ya aplicados y el árbol limpio; este documento
cubre la verificación con Playwright/navegador real y las comprobaciones
adicionales que quedaron a medias.

Rama: `feature/ramos-seguros-mati` (worktree
`C:\Users\Acer\ZEUS-IA\.claude\worktrees\ramos-seguros-mati`), sobre
`feature/vertical-seguros`. Sin merge ni push a `main` en ningún momento.
Ningún commit nuevo de código se añadió en esta sesión — el trabajo de esta
sesión es enteramente de **verificación** (más este propio documento).

Commits ya aplicados por el ejecutor anterior (revisados línea a línea con
`git show` antes de empezar a verificar, no asumidos):

- `c1457e7` — `chore(seguros): reutilizar validators_es.py/validatorsEs.ts (NIF/CIF/IBAN) de feature/onboarding-facturacion`. Copia literal de `backend/app/core/validators_es.py` (NIF mod-23, CIF algoritmo AEAT, IBAN mod-97) y `frontend/src/utils/validatorsEs.ts`.
- `8081ffb` — `feat(insurance): ramo real (6 valores), DNI/NIF validado y campos por ramo — piloto Mati/Catalana Occidente`.
  - `backend/app/models/insurance.py:60-104` — enum `PolicyBranch` (hogar/comunidad/coche/vida/decesos/salud) + columna `branch` NOT NULL indexada en `InsurancePolicy`.
  - `backend/alembic/versions/0044_insurance_policy_branch.py` — `ADD COLUMN branch` con `server_default='hogar'` temporal, retirado en Postgres tras el upgrade.
  - `backend/app/schemas/insurance.py:18-101` — `PolicyBranch`, `REQUIRED_INSURED_RISK_FIELDS` (coche/vida/salud), `InsurancePolicyCreate.customer_tax_id` con `@field_validator` sobre `validar_nif_cif`, `@model_validator` que exige los campos obligatorios de `insured_risk` por ramo.
  - `backend/app/api/v1/endpoints/insurance.py:152-195` — `create_policy` exige DNI/NIF/CIF válido (informado o ya en `Customer.tax_id`) antes de emitir la póliza, persiste el tax_id nuevo sobre el cliente en el mismo commit atómico, filtro `?branch=` en `list_policies`, log `insurance_policy_created` con `branch=`.
- `d543ace` — `fix(insurance): FORCE ROW LEVEL SECURITY en insurance_policies/insurance_claims`.
  - `backend/alembic/versions/0045_insurance_force_rls.py` — añade `ALTER TABLE ... FORCE ROW LEVEL SECURITY` sobre ambas tablas (0043 solo tenía `ENABLE`, lo que eximía al propietario de la tabla de la política). No-op en SQLite.
- `f06e3fc` — `feat(insurance): frontend — selector de ramo (6), DNI/NIF con feedback inmediato y campos por ramo`.
  - `frontend/src/views/InsuranceView.vue` — select de ramo obligatorio, input DNI/NIF/CIF con validación en vivo (`validarNifCif`) que deshabilita "Crear póliza" si no es válido, fieldsets condicionales por ramo (coche/vida/salud), listado/detalle muestran el ramo.

No se tocó código de producción en esta sesión de verificación (solo un
ajuste temporal y revertido de `frontend/vite.config.ts`, ver sección 3).

---

## 1. Qué se probó y cómo — backend real, `curl`, dos tenants propios + uno preexistente

Backend real levantado desde este worktree, dos veces:

1. Puerto propio 8021 (`uvicorn app.main:app --host 127.0.0.1 --port 8021`,
   arrancado desde `backend/` de este worktree) — usado para el grueso de
   las pruebas de API.
2. Se descubrió un backend (puerto 8000) y un frontend Vite (puerto 5173)
   **ya corriendo desde este mismo worktree**, huérfanos de la sesión del
   ejecutor anterior (confirmado inspeccionando `CommandLine` de los
   procesos con `Get-CimInstance Win32_Process`: ambos apuntan literalmente
   a `...\worktrees\ramos-seguros-mati\...`). Se reutilizaron para la
   verificación E2E de navegador en vez de forzar puertos alternativos,
   porque la CSP de `index.html` y el fallback `LOCAL_API` de
   `src/config/index.ts` están hardcodeados a `localhost:8000`/`5173` (ver
   sección 3) — usar el par canónico evitó tener que tocar configuración de
   seguridad no relacionada con esta tarea.

Todas las pruebas de esta sección corresponden a llamadas HTTP reales
contra el servidor real, con payloads reales, contra la misma
`backend/zeus.db` (SQLite de desarrollo, historial acumulado de sesiones
anteriores).

### 1.1 Alta de las 6 pólizas (una por ramo), tenant A

`POST /api/v1/auth/register` → `mati.tenantA@zeustest.com`, `company_id=59`.
`POST /api/v1/auth/login` (form data) → token real.

Cliente CRM creado por API (`POST /api/v1/customers`) para cada ramo, con
NIF real válido (checksum mod-23 calculado con el propio algoritmo de
`validators_es.py`, no inventado a mano):

| Cliente | NIF | id |
|---|---|---|
| Juana Perez Hogar | 12345678Z | 13 |
| Comunidad Rosales | 23456789D | 14 |
| Carlos Gomez Coche | 34567890V | 15 |
| Ana Lopez Vida | 45678901G | 16 |
| Pedro Diaz Decesos | 11223344B | 17 |
| Marta Ruiz Salud | 99887766P | 18 |

`POST /api/v1/insurance/policies` para cada ramo — las 6 devolvieron `201`
con `policy_number` generado y `company_id=59`:

| Ramo | policy_number | Campos específicos enviados |
|---|---|---|
| hogar | POL-20260904-70E1CC | `insured_risk.direccion`, `m2` |
| comunidad | POL-20260904-6D2149 | `insured_risk.direccion`, `m2`, `coverages.responsabilidad_civil_capital` |
| coche | POL-20260904-D193D1 | `matricula=1234ABC`, `conductor_habitual`, `marca_modelo=Seat Leon` |
| vida | POL-20260904-B5A449 | `beneficiario`, `capital_asegurado=150000` |
| decesos | POL-20260904-B2B412 | sin campos adicionales (correcto, el ramo no los exige) |
| salud | POL-20260904-009EA1 | `numero_asegurados=3`, `cuadro_medico` |

**Persistencia real en BD confirmada por SQL directo** (no solo la
respuesta de la API), consulta a `backend/zeus.db`:

```
7 59 hogar     POL-20260904-70E1CC 320.5  {"direccion": "Calle Mayor 10, Madrid", "m2": 90}
8 59 comunidad POL-20260904-6D2149 890    {"direccion": "Av. Rosales 5, Sevilla", "m2": 1200}
9 59 coche     POL-20260904-D193D1 450.75 {"matricula": "1234ABC", "conductor_habitual": "Carlos Gomez Coche", "marca_modelo": "Seat Leon"}
10 59 vida     POL-20260904-B5A449 180    {"beneficiario": "Luis Lopez (hijo)", "capital_asegurado": 150000}
11 59 decesos  POL-20260904-B2B412 95.2   {}
12 59 salud    POL-20260904-009EA1 260    {"numero_asegurados": 3, "cuadro_medico": "Cuadro medico nacional Catalana Occidente"}
```

`customers.tax_id` confirmado persistido para los 6 clientes con el NIF
exacto enviado.

`GET /api/v1/insurance/policies` (tenant A) → `total: 6`, los 6 ramos
presentes en el listado con su `branch` correcto.

`GET /api/v1/insurance/policies/9` (coche), `/10` (vida), `/12` (salud) →
reapertura de cada póliza confirma que `insured_risk` con los campos
específicos del ramo se recupera completo y correcto (matrícula/conductor/
marca-modelo; beneficiario/capital asegurado; nº asegurados/cuadro médico).

`GET /api/v1/insurance/policies?branch=vida` (contra el servidor del
puerto 8000, código idéntico, misma BD) → `total: 1`, confirma el filtro
`?branch=` documentado en el commit `8081ffb`.

### 1.2 DNI/NIF — validación real, no solo de formato

| Caso | Payload | Resultado |
|---|---|---|
| NIF con letra de control incorrecta (`12345678A` en vez de `12345678Z`) | `POST /insurance/policies` | `422`, `"DNI/NIF/CIF no válido (formato o dígito/letra de control incorrecto)"` |
| Formato inválido (`XYZ12345`) | `POST /insurance/policies` | `422`, mismo mensaje |
| Rama `coche` sin `matricula`/`conductor_habitual`/`marca_modelo` en `insured_risk` | `POST /insurance/policies` | `422`, `"Faltan campos obligatorios para el ramo 'coche' en insured_risk: matricula, conductor_habitual, marca_modelo"` |

Los tres casos son rechazos reales del validador de Pydantic
(`@field_validator`/`@model_validator` en `backend/app/schemas/insurance.py`),
no un "éxito silencioso" ni un 500 opaco.

### 1.3 Aislamiento multi-tenant — dos tenants nuevos + verificación cruzada

`POST /api/v1/auth/register` → `mati.tenantB@zeustest.com`, `company_id=60`
(tenant nuevo, propio de esta sesión, no reutilizado de nadie).

| Caso | Resultado |
|---|---|
| `GET /insurance/policies` sin token | `401` |
| `GET /insurance/policies` (B) | `200`, `total: 0` (B no ve ninguna de las 6 pólizas de A) |
| `GET /insurance/policies/7` (B, póliza de A) | `404 "Policy with ID 7 not found"` |
| `POST /insurance/policies` (B, con `customer_id=13` de A) | `404 "Customer with ID 13 not found"` (B no puede ni referenciar un cliente ajeno) |
| `POST /customers` (B, cliente propio, NIF `87654321X`) | `201`, id `19` |
| `POST /insurance/policies` (B, sobre su propio cliente) | `201`, `company_id=60` |
| `GET /insurance/policies` (B) tras su alta | `200`, `total: 1` (solo la suya) |
| `GET /insurance/policies` (A) de nuevo | `200`, `total: 6` (sigue viendo solo las suyas, la póliza de B no se filtró incorrectamente hacia A) |

Aislamiento confirmado en ambas direcciones con datos reales, no solo
lectura de código.

---

## 2. Verificación E2E con navegador real (Claude Browser, equivalente Playwright)

### 2.1 Selección de puertos y motivo del cambio de plan

El plan inicial era levantar un frontend Vite propio en un puerto libre
(`npx vite --port <libre> --strictPort`) apuntando al backend propio del
puerto 8021. Se intentó parametrizar `frontend/vite.config.ts` (puerto y
proxy vía `VITE_DEV_PORT`/`VITE_DEV_BACKEND`) para no chocar con otros
worktrees ya usando 5173/8000 — **cambio revertido con `git checkout --
frontend/vite.config.ts` en cuanto se detectó el bloqueo real**, no forma
parte del estado final del árbol.

El bloqueo real: `frontend/src/config/index.ts` tiene un fallback
`LOCAL_API = 'http://localhost:8000/api/v1'` hardcodeado para modo
desarrollo (no relativo, no proxeado por Vite), y `frontend/index.html`
tiene una Content-Security-Policy con `connect-src` que solo permite
explícitamente `localhost:8000`/`127.0.0.1:8000` (además del dominio de
Railway). Un backend en un puerto distinto de 8000 queda bloqueado por la
propia CSP del navegador (`Connecting to '...' violates ... connect-src
...`), confirmado en consola real, no supuesto. Tocar la CSP o el fallback
de `config/index.ts` para esta verificación habría sido modificar
configuración de seguridad no relacionada con la tarea de Seguros —
decisión: no hacerlo, y en su lugar reutilizar el par de puertos canónico.

Al revisar el entorno se encontró un backend (`uvicorn`, puerto 8000) y un
frontend (`vite`, puerto 5173) **ya corriendo desde este mismo worktree**
(confirmado por `CommandLine` real de ambos procesos, apuntando a
`...\worktrees\ramos-seguros-mati\...`), casi con toda seguridad huérfanos
de la sesión del ejecutor anterior que fue cortada por límite. Se
reutilizaron tal cual (mismo código de este commit, misma
`backend/zeus.db`) en vez de matarlos y relanzar — transparencia: no fueron
arrancados por esta sesión de verificación, ya estaban ahí.

### 2.2 Aislamiento del desplegable de cliente — la verificación que quedó a medias

Al navegar a `http://localhost:5173/insurance` el navegador ya tenía una
sesión válida persistida (localStorage) de una tercera empresa de pruebas
del ejecutor anterior (no de los tenants A/B creados en esta sesión). Se
identificó por SQL directa: `company_id=57`, clientes `Cliente Prueba Uno`
(id 11) y `Cliente Prueba Dos (NIF invalido)` (id 12).

Esto permitió, sin necesidad de resolver el logout de la UI (no se
localizó un botón de logout accesible en el layout `DashboardProfesional`
usado por `/dashboard`/`/insurance` dentro del viewport disponible; existe
`logout()` en `MainLayout.vue`/`stores/auth.ts` pero no está expuesto en
esta vista concreta — hallazgo menor, no bloqueante, documentado en la
sección 4), verificar el aislamiento del desplegable con un **tercer
tenant real**, adicional a los A/B de la sección 1:

1. `GET /insurance/policies` (sesión de company 57) → "Pólizas (6)",
   confirmando que lee datos reales de la misma BD (6 pólizas propias de
   esa empresa, con ramos y números de póliza **distintos** a los de
   tenant A, ver captura/lectura de página).
2. Clic en "Nueva póliza" → formulario real abierto.
3. Lectura de accesibilidad del `<select>` "Cliente" (árbol ARIA real, no
   supuesto): únicamente dos opciones, `"Cliente Prueba Dos (NIF
   invalido)"` (value=12) y `"Cliente Prueba Uno"` (value=11) — **ninguno**
   de los 6 clientes de tenant A (ids 13-18: Juana Perez Hogar, Comunidad
   Rosales, Carlos Gomez Coche, Ana Lopez Vida, Pedro Diaz Decesos, Marta
   Ruiz Salud) ni el cliente de tenant B (id 19: Cliente B Hogar) aparecen
   en el desplegable. Confirmado con screenshot real (dropdown abierto,
   visible en pantalla) además de la lectura de accesibilidad.
4. Esto completa exactamente el punto que el ejecutor anterior dejó a
   medias ("seleccionar un cliente en un desplegable"): el `<select>` de
   cliente en el formulario de alta de póliza está correctamente scoped
   por empresa — la fuente de los datos es `GET /api/v1/crm/customers`,
   que ya filtra por `company_ids_for_user` (mismo patrón que el resto del
   endpoint, sin cambios de esta tarea).

**Limitación de herramienta encontrada y declarada, no ocultada:** no se
consiguió completar el *submit* real del formulario vía clics automatizados
sobre el `<select>` nativo del sistema operativo (el overlay de opciones
nativo de Chrome no registra el clic en la opción vía coordenadas ni vía
teclado con este tooling de automatización de navegador en este entorno;
tras varios intentos — clic por coordenada, flechas+Enter, "type-to-select"
— el valor seleccionado seguía siendo `"Selecciona un cliente"" tras cerrar
el desplegable). Esto es una limitación conocida de automatizar `<select>`
nativos vía control de mouse/teclado a bajo nivel, no un bug del
formulario: la sección 1 ya prueba de forma exhaustiva y real, vía API
directa contra el mismo backend/BD, que el alta de póliza con cliente y
ramo seleccionados funciona end-to-end (incluida la escritura en BD) para
los 6 ramos y ambos tenants A/B. El formulario se cerró con "Cancelar" sin
dejar ningún dato a medio enviar.

---

## 3. Regresión — suite completa de tests backend

Baseline establecido explícitamente **para esta rama** (parte de
`feature/vertical-seguros`, no de `feature/consolidacion-final`; puede
diferir de baselines de otras ramas de esta sesión), reconstruyendo el
estado de archivos previo a los 4 commits de esta tarea con
`git checkout aed639d -- .` (sin mover `HEAD`/la rama), ejecutando
`pytest tests/` (no la raíz completa: `TEST_SISTEMA_COMPLETO.py` en la
raíz de `backend/` hace `sys.exit(0)` a nivel de módulo y rompe la
recolección de pytest si se apunta a `backend/` completo — hallazgo
preexistente, no de esta tarea, ya usado así en `AUDIT_VERTICAL_SEGUROS.md`)
y restaurando después con `git checkout HEAD -- .`:

**Baseline (aed639d, antes de los 4 commits de este piloto):**
```
7 failed, 214 passed, 2 skipped, 30 warnings, 3 errors in 93.75s
```

**Estado actual (f06e3fc, con los 4 commits aplicados):**
```
7 failed, 214 passed, 2 skipped, 30 warnings, 3 errors in 98.66s
```

Mismos 7 tests fallidos exactos en ambos casos (`test_config_loading`,
`test_justicia_control_layer_v1::test_default_flags_simulated`,
`test_perseo_autofix_v2::test_audit_includes_ai_modules`,
3× `test_thalos_control_layer_v1`, `test_thalos_safe_v1`) y mismos 3
errores (`test_app.py`, `TestClient` no definido) — **idéntico al
baseline, sin regresión**. Coincide además, carácter a carácter, con el
baseline ya documentado independientemente en `AUDIT_VERTICAL_SEGUROS.md`
para el mismo punto del árbol (aed639d), lo que da doble confirmación.

`git status --short` tras restaurar: solo queda `.claude/` sin trackear
(preexistente de la sesión, no de este trabajo) — árbol de trabajo limpio,
ningún archivo quedó a medio revertir.

---

## 4. Verificación de la migración Alembic (0043→0044→0045)

Réplica del método ya usado por el ejecutor anterior en
`AUDIT_VERTICAL_SEGUROS.md` (BD SQLite aislada y fresca, no
`backend/zeus.db`), esta vez cubriendo la cadena completa hasta 0045:

1. BD SQLite nueva (`alembic_verify_ramos.db`, en el scratchpad de esta
   sesión, borrada al terminar) con tablas mínimas `companies`,
   `customers`, `users` y `alembic_version` estampada en `0042`.
2. `alembic upgrade 0045` (CLI real, `DATABASE_URL` apuntando a esa BD) →
   aplica `0042→0043→0044→0045` sin error. Log real:
   ```
   Running upgrade 0042 -> 0043, insurance_policies / insurance_claims
   Running upgrade 0043 -> 0044, insurance_policies.branch
   Running upgrade 0044 -> 0045, insurance_policies / insurance_claims — FORCE ROW LEVEL SECURITY
   ```
3. Inspección directa del esquema resultante: `insurance_policies` con las
   14 columnas esperadas incluida `branch VARCHAR(9) NOT NULL DEFAULT
   'hogar'` (el `server_default` es intencional, ver comentario de
   `0044_insurance_policy_branch.py` — la API siempre exige `branch`
   explícito, el default nunca se usa en la práctica) e índice
   `ix_insurance_policies_branch` creado.
4. `alembic downgrade 0042` → revierte `0045→0044→0043→0042` sin error;
   confirmado que `insurance_policies`/`insurance_claims` desaparecen del
   esquema y solo quedan `companies`/`customers`/`users`/`alembic_version`
   (estampada de vuelta en `0042`).

**Patrón RLS confirmado consistente con el núcleo** (revisión de línea,
no runtime): `0043_insurance_policies_claims.py` hace `ALTER TABLE ...
ENABLE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation_... USING
(...)` fail-closed + crea el rol `zeus_app` (`NOSUPERUSER NOCREATEDB
NOCREATEROLE NOBYPASSRLS NOINHERIT LOGIN`, sin contraseña fijada en el
fichero) sobre ambas tablas; `0045_insurance_force_rls.py` añade `ALTER
TABLE ... FORCE ROW LEVEL SECURITY` sobre las mismas dos tablas. Incluye
el `NOT EXISTS`/`EXCEPTION WHEN insufficient_privilege` defensivo para no
abortar la migración si el rol que la aplica no puede `CREATE ROLE`. Mismo
esquema (`ENABLE` + `FORCE`, rol de aplicación sin privilegios de
superusuario) que el resto de tablas multi-tenant del núcleo
(`feature/multi-tenant-bd`, solo consultado como referencia, no copiado
literal).

**Explícitamente NO verificado — requiere Postgres real:**
- No hay Postgres ni Docker disponibles en este entorno (`where docker`,
  `where psql` sin resultado, igual que en todos los ciclos anteriores
  documentados en `CICLO_PRODUCCION.md` y en `AUDIT_VERTICAL_SEGUROS.md`).
- No se puede confirmar en runtime que `zeus_app` con `FORCE ROW LEVEL
  SECURITY` + `SET app.current_company_id` realmente aísle filas para el
  propio propietario de la tabla (el motivo exacto por el que `d543ace`
  añadió el `FORCE`), ni que una conexión sin ese contexto vea 0 filas.
- No se probó el camino de fallo de `CREATE ROLE`/`GRANT` por privilegios
  insuficientes (los bloques `EXCEPTION WHEN insufficient_privilege` son
  defensivos, no ejercitados).
- La aplicación todavía no se conecta con el rol `zeus_app` en runtime
  (usa el rol de conexión principal) — mismo hallazgo ya declarado en
  `AUDIT_VERTICAL_SEGUROS.md`, sigue pendiente, no es parte del alcance de
  esta tarea.

Esto es una limitación del entorno de verificación, declarada de forma
explícita, no una omisión de trabajo.

---

## 5. Qué NO se pudo verificar

- **RLS/rol `zeus_app` contra Postgres real** (sección 4) — bloqueado por
  falta de Postgres/Docker en este entorno. Pendiente de que alguien con
  acceso a staging/Railway lo verifique antes de confiar en él para
  producción real con más de un tenant concurrente.
- **Submit real del formulario de alta de póliza mediante clics
  automatizados sobre el `<select>` nativo de cliente** (sección 2.2) —
  limitación del tooling de automatización de navegador con `<select>`
  nativos del sistema operativo en este entorno, no del formulario en sí
  (ya verificado end-to-end por API real en la sección 1, incluida
  persistencia en BD).
- **Botón de logout accesible en la UI de `/dashboard`/`/insurance`** — no
  localizado dentro del viewport/menú disponible en `DashboardProfesional`;
  existe la función `logout()` en `stores/auth.ts`/`MainLayout.vue` pero no
  se encontró expuesta en esta vista. No se investigó más a fondo por
  quedar fuera del alcance de esta tarea (Seguros), se deja como hallazgo
  menor para quien decida si aplica a otra vertical/al núcleo.

---

## 6. Qué queda pendiente / decisiones que requieren al usuario

Heredado de `AUDIT_VERTICAL_SEGUROS.md` (no resuelto por esta tarea, fuera
de su alcance):

1. Contraseña real del rol `zeus_app` — debe fijarse en Postgres de
   staging/producción fuera de esta migración (gestor de secretos de
   Railway).
2. La aplicación todavía no usa el rol `zeus_app` para conectarse en
   runtime — trabajo adicional, no pedido en este piloto.
3. Verificación de RLS en runtime contra Postgres real — bloqueada por
   entorno, pendiente de staging.
4. `create_tables()` desde cero y la cadena completa `0001→0042` de
   Alembic tienen problemas preexistentes ya documentados (no relacionados
   con Seguros, no tocados aquí).

Nuevo, de esta sesión de verificación:

5. Botón de logout no localizado en la UI de `/dashboard`/`/insurance`
   dentro del viewport probado (sección 5) — confirmar si es un problema
   real de UX/accesibilidad o solo una limitación del viewport de prueba
   usado en esta sesión, y si aplica, en qué vertical/capa corregirlo.
6. Datos de prueba dejados en `backend/zeus.db` local de este worktree:
   tenants `mati.tenantA@zeustest.com` (company_id=59, 6 clientes, 6
   pólizas) y `mati.tenantB@zeustest.com` (company_id=60, 1 cliente, 1
   póliza). Sin impacto en producción/Railway (BD local SQLite),
   revertible si se pide.
7. Los procesos huérfanos en los puertos 8000/5173 de este worktree
   (heredados de la sesión anterior, reutilizados en la sección 2, no
   iniciados ni detenidos por esta sesión) siguen corriendo — decisión
   deliberada de no matarlos por si el usuario los necesita para seguir
   inspeccionando manualmente; se pueden detener cuando ya no hagan falta.

Este documento no se autodeclara cerrado — queda pendiente de
`revisor-independiente`.
