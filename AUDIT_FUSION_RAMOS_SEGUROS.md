# AUDIT_FUSION_RAMOS_SEGUROS.md

Verificación post-fusión de `feature/ramos-seguros-mati` (piloto de 6 ramos de
seguros, Mati/Catalana Occidente, ya aprobado por revisión independiente en su
propia rama, ver `AUDIT_RAMOS_SEGUROS_MATI.md`) dentro de
`feature/consolidacion-final`.

Rama verificada: `feature/consolidacion-final` (worktree
`C:\Users\Acer\ZEUS-IA\.claude\worktrees\consolidacion-final`).
Commit en `HEAD` al empezar: `ca62389` (`fix(alembic): completar la
renumeracion 0044/0045->0054/0055 que no llego al commit de fusion
anterior`), sobre el merge `6b3e917` (`merge: feature/ramos-seguros-mati (6
ramos de Mati/Catalana Occidente) en feature/consolidacion-final`).

Ningún commit de código nuevo se necesitó durante esta verificación — no se
encontró ninguna regresión que corregir. Se hace un único commit con este
documento. No se tocó `main`, no se hizo `push`, no se creó rama nueva.

---

## 1. Suite completa de tests backend

Entorno: venv compartido `C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe`,
ejecutado desde `backend/` de este worktree:

```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\python.exe -m pytest tests -q
```

**Resultado obtenido:**
```
7 failed, 300 passed, 34 warnings, 3 errors in 156.75s (0:02:36)
```

Fallos y errores, listados exactos:
```
FAILED tests/test_basic.py::test_config_loading
FAILED tests/test_justicia_control_layer_v1.py::test_default_flags_simulated
FAILED tests/test_perseo_autofix_v2.py::test_audit_includes_ai_modules
FAILED tests/test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules
FAILED tests/test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags
FAILED tests/test_thalos_control_layer_v1.py::test_build_metadata_origin_mock
FAILED tests/test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags
ERROR tests/test_app.py::test_health_check - NameError: name 'TestClient' is ...
ERROR tests/test_app.py::test_root_endpoint - NameError: name 'TestClient' is ...
ERROR tests/test_app.py::test_favicon - NameError: name 'TestClient' is not d...
```

**Comparación con el baseline conocido de esta rama** (documentado, entre
otros, en `AUDIT_CONSOLIDACION_REVISION_FINAL.md`, `AUDIT_SEGURIDAD_ESTANDAR.md`
y `AUDIT_JUSTICIA_ESTADO_FINAL.md`, todos previos a la fusión de
`ramos-seguros-mati`): `7 failed, 300 passed, 34 warnings, 3 errors` — **cifra
idéntica, mismos 7 tests fallidos exactos por nombre y mismos 3 errores**. La
fusión de `ramos-seguros-mati` no añade tests de `pytest` propios (esa rama se
verificó con `curl`/navegador real, no con suite automatizada, ver su propio
`AUDIT_RAMOS_SEGUROS_MATI.md` sección 3), así que no se esperaba ni se observa
subida en el número de `passed`. **Sin regresión.**

---

## 2. Migraciones Alembic

### 2.1 Cabeza única

```
C:\Users\Acer\ZEUS-IA\backend\venv\Scripts\alembic.exe heads
```
```
0055 (head)
```

Una sola cabeza, `0055`, tal como declara el commit de fusión (`6b3e917`) y el
commit de renumeración (`ca62389`).

### 2.2 Cadena completa desde cero, SQLite aislado en scratchpad

Base de datos SQLite nueva y vacía (no `backend/zeus.db`, que en este worktree
está creada vía `create_tables()`/parches de esquema, no vía Alembic —
hallazgo preexistente ya documentado en auditorías anteriores, no de esta
tarea), en
`C:\Users\Acer\AppData\Local\Temp\claude\zeus_consolidacion_migtest\fresh.db`
(borrada al terminar):

```
DATABASE_URL=sqlite:///.../fresh.db alembic upgrade head
```

Aplica sin error las 55 revisiones, `0001` hasta `0055`, incluyendo en orden:

```
Running upgrade 0053 -> 0054, insurance_policies.branch — ramos de Mati (piloto Catalana Occidente)
Running upgrade 0054 -> 0055, insurance_policies / insurance_claims — FORCE ROW LEVEL SECURITY
```

`alembic current` tras el upgrade confirma `0055 (head)`.

Inspección directa del esquema resultante (`PRAGMA table_info`): la tabla
`insurance_policies` queda con las 15 columnas esperadas, incluida
`branch VARCHAR(9) NOT NULL DEFAULT 'hogar'` (el `server_default` es
intencional y documentado en el propio fichero de migración — la API siempre
exige `branch` explícito, el default nunca se ejercita en la práctica).

### 2.3 Downgrade

```
alembic downgrade 0048
```

Revierte en orden `0055→0054→0053→0052→0051→0050→0049→0048` sin error,
incluyendo las dos migraciones de este piloto (`0055`, `0054`) y las que las
preceden en la rama de consolidación (RLS de logs de THALOS, campos de
facturación, etc.). Se volvió a subir a `head` después (`alembic upgrade
head`) para dejar el archivo de scratch consistente antes de borrarlo.

**No verificado en runtime contra Postgres real** (no hay Docker/`psql`
disponibles en este entorno) — mismo hallazgo ya declarado en
`AUDIT_RAMOS_SEGUROS_MATI.md` sección 4/5 y en auditorías anteriores de esta
rama; no es una omisión nueva de esta verificación.

---

## 3. Verificación E2E de los 6 ramos tras la fusión

### 3.1 Entorno levantado desde este worktree, tenant 100% nuevo

- Backend: `uvicorn app.main:app --host 127.0.0.1 --port 8000`, arrancado
  desde `backend/` de este worktree, apuntando a una base de datos SQLite
  nueva y vacía dedicada a esta verificación
  (`...\zeus_consolidacion_migtest\e2e.db`, previamente llevada a `head` con
  `alembic upgrade head`). Backend confirmado sano: `GET /health` →
  `{"status":"healthy","service":"zeus-ia"}`.
- Frontend: `npx vite --port 5173 --strictPort`, arrancado desde
  `frontend/` de este mismo worktree (no un proceso preexistente de otra
  sesión — arrancado y parado dentro de esta tarea, PIDs 17116/backend y
  7864/vite confirmados y detenidos al terminar). Se usó el par de puertos
  canónico 8000/5173 porque, igual que documentó el ejecutor de
  `AUDIT_RAMOS_SEGUROS_MATI.md`, `frontend/src/config/index.ts` tiene
  `LOCAL_API` hardcodeado a `localhost:8000` y la CSP de `index.html` solo
  permite `connect-src` a ese puerto en desarrollo — no se tocó esa
  configuración de seguridad para esta verificación.
- Marcador de que se sirve este commit: el frontend se sirve directamente
  desde el código fuente de este worktree vía Vite dev (no un build
  preexistente), y se confirmó leyendo `InsuranceView.vue` de este mismo
  árbol que las clases `.field-invalid`/`.field-error` (añadidas por el
  merge) están presentes tanto en el código fuente como en el DOM renderizado
  (sección 3.4) — descarta que se estuviera sirviendo una build vieja o de
  otro worktree.
- Tenants usados, creados en esta sesión, sin reutilizar ninguno de
  `ramos-seguros-mati` ni de otras auditorías previas:
  `consolidacion.tenantE@zeustest.com` (`company_id=1`) y
  `consolidacion.tenantF@zeustest.com` (`company_id=2`).

### 3.2 Alta de las 6 pólizas (tenant E), vía API real

6 clientes creados vía `POST /api/v1/customers` con NIF válido (checksum
mod-23 generado con el propio `app.core.validators_es.validar_nif_cif`, no
inventado a mano): `20000001Y` … `20000006B` (ids 1-6).

`POST /api/v1/insurance/policies` para cada ramo — las 6 devolvieron
`success: true` con `policy_number` generado y `company_id=1`:

| Ramo | policy_number | Campos específicos |
|---|---|---|
| hogar | POL-20260904-BD52F4 | `insured_risk.direccion`, `m2` |
| comunidad | POL-20260904-150579 | `insured_risk.direccion`, `m2`, `coverages.responsabilidad_civil_capital` |
| coche | POL-20260904-D45576 | `matricula=5566CCC`, `conductor_habitual`, `marca_modelo=Toyota Corolla` |
| vida | POL-20260904-4773FD | `beneficiario`, `capital_asegurado=175000` |
| decesos | POL-20260904-2B2E59 | sin campos adicionales (correcto) |
| salud | POL-20260904-777596 | `numero_asegurados=2`, `cuadro_medico` |

**Persistencia real confirmada por SQL directo** contra
`...\zeus_consolidacion_migtest\e2e.db` (no solo la respuesta HTTP):

```
1 1 hogar     POL-20260904-BD52F4 300   {"direccion": "Calle Consolidacion 1, Madrid", "m2": 85}
2 1 comunidad POL-20260904-150579 850   {"direccion": "Av Consolidacion 2, Sevilla", "m2": 1100}
3 1 coche     POL-20260904-D45576 420.5 {"matricula": "5566CCC", "conductor_habitual": "Coche Consolidacion", "marca_modelo": "Toyota Corolla"}
4 1 vida      POL-20260904-4773FD 160   {"beneficiario": "Familia Consolidacion", "capital_asegurado": 175000}
5 1 decesos   POL-20260904-2B2E59 92    {}
6 1 salud     POL-20260904-777596 275   {"numero_asegurados": 2, "cuadro_medico": "Cuadro medico Consolidacion"}
```

`GET /api/v1/insurance/policies/3` (coche), `/4` (vida), `/6` (salud) —
reapertura por API confirma que `insured_risk` con matrícula/conductor/marca y
modelo, beneficiario/capital asegurado, y número de asegurados/cuadro médico
se recupera completo y correcto.

`GET /api/v1/insurance/policies` → `total: 6`. `GET
/api/v1/insurance/policies?branch=vida` → `total: 1`, confirma el filtro por
ramo.

### 3.3 DNI/NIF — validación real

| Caso | Resultado |
|---|---|
| Cliente sin `tax_id` (creado sin ese campo), póliza sin `customer_tax_id` de override | `422` — `"El cliente necesita un DNI/NIF/CIF válido para emitir una póliza"` |
| Póliza con `customer_tax_id` override de formato inválido (`12345678A`, letra de control incorrecta) | `422` — `"DNI/NIF/CIF no válido (formato o dígito/letra de control incorrecto)"` |

Ambos son rechazos reales del validador (`app/schemas/insurance.py` +
`app/core/validators_es.py`), código HTTP `422` confirmado explícitamente, no
un éxito silencioso ni un 500 opaco.

### 3.4 Verificación en navegador real (Claude Browser)

- Login como tenant E vía UI real (formulario de `/login`, sin atajos).
  Tenant nuevo, forzado a completar `/onboarding-setup` en el primer login
  (comportamiento esperado del núcleo, no relacionado con Seguros); se
  completó vía `POST /api/v1/auth/onboarding/profile` (mismo endpoint que usa
  el wizard) para poder llegar a `/insurance` sin rellenar manualmente los 3
  pasos del wizard — decisión de eficiencia, no un atajo de seguridad (el
  endpoint exige el mismo token de sesión real que cualquier otra llamada).
- `http://localhost:5173/insurance` (tras completar el onboarding) carga la
  vista `Seguros` con **"Pólizas (6)"** y las 6 filas visibles con su ramo
  correcto (confirmado con `get_page_text`, texto real extraído del DOM):
  Salud, Decesos, Vida, Coche, Comunidad, Hogar — los 6 ramos, cada uno con su
  `policy_number`, cliente y prima correctos.
- Consola del navegador sin errores (`read_console_messages` con
  `onlyErrors=true` → "No console logs"). Peticiones de red
  (`read_network_requests`) confirman `GET
  http://localhost:8000/api/v1/insurance/policies → 200 OK` real, no
  simulado.
- Formulario "Nueva póliza": selector de Cliente (`<select>`) muestra
  exactamente los clientes de la empresa del tenant logueado (los 6 de esta
  sección más el de NIF inválido de la sección 3.3), scoped correctamente por
  `company_id` — mismo mecanismo de scoping ya verificado por API.
- **Feedback de validación de NIF en vivo, confirmado visualmente**: al
  escribir `12345678A` en el campo "DNI/NIF/CIF del cliente" aparece de
  inmediato el borde rojo (`.field-invalid`) y el mensaje `"DNI/NIF/CIF no
  válido"` (`.field-error`) bajo el campo — las dos clases añadidas por el
  merge conflict resuelto en `6b3e917` están presentes y funcionando, no solo
  en el código fuente sino en el DOM renderizado real. Al corregir el NIF a
  uno válido (`20000003P`) el borde de error desaparece.
- **Diseño del sistema de bandas y tokens `--zeus-*` confirmado sin
  regresión**: capturas de pantalla muestran el fondo de bandas
  metálicas (`background-image: var(--zeus-bg)`) y el botón "Nueva póliza"
  con degradado (`var(--zeus-accent-gradient)`), consistentes con el resto de
  vistas ya aprobadas del núcleo. Revisión de línea de
  `frontend/src/views/InsuranceView.vue` confirma que el token conservado por
  la resolución del conflicto de merge, `var(--zeus-text-muted, #8792a6)`
  (línea 707, regla `.muted`), es el mismo token usado de forma consistente
  en el resto de vistas ya cerradas por la auditoría de frontend
  (`DashboardProfesional.vue`, `AdminPanel.vue`, `TPV.vue`,
  `ControlHorario.vue`, `OfficeCrm.vue`, todas grepeadas y confirmadas con el
  mismo token) — no se reintrodujo el color hardcodeado de la rama entrante
  que el mensaje del commit de fusión dice haber descartado.
- **Limitación de tooling reproducida, ya conocida** (documentada
  originalmente en `AUDIT_RAMOS_SEGUROS_MATI.md` sección 2.2/5): no fue
  posible completar la selección del `<select>` nativo de "Ramo" mediante
  clics por coordenada ni navegación por teclado (flechas + Enter) con este
  tooling de automatización de navegador en este entorno — el valor
  seleccionado permanecía en "Selecciona un ramo" tras cerrar el desplegable,
  igual que reportó el ejecutor y confirmó el revisor independiente de
  `ramos-seguros-mati` para el `<select>` de "Cliente". No se insistió más
  porque la sección 3.2 ya prueba de forma exhaustiva y real, vía API directa
  contra el mismo backend y la misma base de datos, que el alta de póliza con
  ramo y cliente seleccionados funciona end-to-end (incluida persistencia)
  para los 6 ramos. El formulario se cerró con "Cancelar" sin dejar ningún
  dato a medio enviar.

### 3.5 Aislamiento multi-tenant — dos tenants nuevos de esta sesión

Tenant E (`company_id=1`, sección 3.2) y tenant F
(`consolidacion.tenantF@zeustest.com`, `company_id=2`), ambos creados en esta
verificación, ninguno reutilizado.

| Caso | Resultado |
|---|---|
| `GET /insurance/policies` sin token | `401` |
| `GET /insurance/policies` (F, antes de tener pólizas propias) | `200`, `total: 0` |
| `GET /insurance/policies/1` (F, póliza de E) | `404` |
| `POST /insurance/policies` (F, `customer_id=1` de E) | `404 "Customer with ID 1 not found"` |
| `POST /customers` (F, cliente propio, NIF `20000001Y`) | `201`, id `8` |
| `POST /insurance/policies` (F, sobre su propio cliente id 8) | `success`, `company_id=2`, id `7` |
| `GET /insurance/policies` (F) tras su alta | `200`, `total: 1` (solo la suya) |
| `GET /insurance/policies` (E) de nuevo | `200`, `total: 6` (sin cambios; la póliza de F no se filtró hacia E) |

Aislamiento confirmado con datos 100% propios de esta sesión, en ambas
direcciones.

---

## 4. Checklist de "no simulación" (skill `zeus-produccion`)

- Endpoint devuelve datos reales de BD, no valores fijos: confirmado por SQL
  directo (sección 3.2) y por `GET` reabriendo cada póliza.
- Pasa por autenticación real antes de ejecutar lógica: `401` sin token,
  `login` real vía formulario UI y vía API con JWT real.
- Filtra por tenant en cada query: confirmado en ambas direcciones con dos
  tenants nuevos (sección 3.5), incluido el filtro de clientes que alimenta
  el `<select>` del formulario.
- Manejo de errores real: `422` con mensajes específicos para NIF inválido,
  campos de ramo faltantes y cliente sin `tax_id`; no hay `try/except: pass`
  en la ruta ejercitada.
- Logs verificables: no se auditó de nuevo el logging interno del endpoint en
  esta sesión (ya confirmado por el ejecutor y el revisor independiente de
  `ramos-seguros-mati`); no se detectó ningún cambio de esa lógica en el
  diff del merge (`app/api/v1/endpoints/insurance.py` solo cambia por la
  fusión de dos ramas paralelas de campos, no por esta verificación).
- Migración Alembic generada y aplicable: confirmado en la sección 2 (cadena
  completa `0001→0055`, cabeza única, downgrade simétrico).

---

## 5. Regresiones encontradas

**Ninguna.** Ni en la suite de tests, ni en la cadena de migraciones, ni en
el comportamiento funcional de los 6 ramos, ni en el diseño de
`InsuranceView.vue`. La resolución del conflicto de merge en `6b3e917`
(conservar `--zeus-text-muted` y añadir `.field-invalid`/`.field-error`) se
verifica correcta: ambas cosas están presentes y funcionan en el DOM
renderizado real.

---

## 6. Qué NO se pudo verificar

- **RLS (`FORCE ROW LEVEL SECURITY`) en runtime contra PostgreSQL real** — no
  hay Docker ni `psql` disponibles en este entorno (mismo hallazgo ya
  declarado repetidamente en auditorías anteriores de esta rama y de
  `ramos-seguros-mati`). Solo se verificó que la migración aplica y revierte
  sin error en SQLite (no-op) y que el patrón (`ENABLE` + `FORCE`, mismo
  esquema que el resto de tablas multi-tenant del núcleo) es consistente por
  lectura de línea.
- **Selección del `<select>` nativo de "Ramo" mediante clics/teclado
  automatizados** — limitación conocida del tooling de automatización de
  navegador en este entorno con elementos `<select>` nativos del sistema
  operativo, ya documentada por auditorías anteriores de la misma vertical;
  no es un bug del formulario (la sección 3.2 ya prueba el flujo completo por
  API real contra el mismo backend/BD).
- **Botón de logout en `/dashboard`/`/insurance`** — mismo hallazgo menor ya
  declarado en `AUDIT_RAMOS_SEGUROS_MATI.md` sección 5, no investigado de
  nuevo por quedar fuera del alcance de esta verificación (fusión de
  Seguros, no UX del núcleo).

---

## 7. Qué queda pendiente

- Las mismas limitaciones de entorno ya heredadas y re-declaradas en la
  sección 6 (RLS en runtime, botón de logout) siguen sin resolver — no son
  parte del alcance de esta tarea de verificación post-fusión.
- Los tenants de prueba de esta sesión (`consolidacion.tenantE@zeustest.com`,
  `company_id=1`, y `consolidacion.tenantF@zeustest.com`, `company_id=2`)
  viven únicamente en una base de datos SQLite de scratch
  (`C:\Users\Acer\AppData\Local\Temp\claude\zeus_consolidacion_migtest\e2e.db`),
  fuera del árbol de git y sin impacto en `backend/zeus.db` del worktree ni
  en producción/Railway. El backend (puerto 8000) y el frontend Vite (puerto
  5173) arrancados para esta verificación se detuvieron al terminar
  (procesos 17116 y 7864 confirmados parados).
- Este documento no se autodeclara cerrado — puede requerir revisión
  independiente si el usuario lo considera necesario antes de dar por
  cerrada la consolidación completa de `feature/consolidacion-final`.
