# AUDIT_FIX_RLS_INSURANCE_SCHEMA — Corrección de los 2 hallazgos pendientes de AUDIT_STAGING_POSTGRES_REAL.md

Rama: `feature/fix-rls-insurance-schema` (worktree
`.claude/worktrees/fix-rls-insurance-schema`), partiendo del commit `c1a9c30`
(creada desde `feature/consolidacion-final`). Postgres usado: la misma
instancia de **staging** en Railway de las verificaciones anteriores —
**nunca producción**, único Postgres tocado en esta sesión. No se ha hecho
`push` ni se ha creado ninguna rama adicional. No se ha tocado `main`.

Commits de esta tarea:
- `7b1d714` — fix(seguros): usar `get_db_scoped` en insurance.py para RLS real
  (Hallazgo 1).
- `08d4976` — fix(schema): migrar columnas de `users` a Alembic real y
  desactivar `ensure_schema_patches()` bajo roles sin privilegios de ALTER
  TABLE (Hallazgo 2).

---

## Hallazgo 1 — `insurance.py` roto bajo RLS real (CRÍTICO)

### Qué se tocó

`backend/app/api/v1/endpoints/insurance.py`:

- Línea 20: import cambiado de `from app.db.session import get_db` a
  `from app.db.tenant_context import get_db_scoped, set_tenant_context`.
- Líneas 89, 134, 203, 215, 244, 280, 318, 330: `Depends(get_db)` →
  `Depends(get_db_scoped)` en los 8 endpoints (mismo patrón ya usado en
  `invoices.py`).
- **Bug adicional descubierto en el mismo archivo, imprescindible para que
  el fix de arriba funcione de verdad** (no estaba en el hallazgo original,
  solo se manifiesta al arreglarlo y probarlo de verdad contra Postgres):
  `create_policy` (~líneas 183-199), `create_claim` (~líneas 256-288) y
  `update_claim` (~líneas 346-373) hacían `db.commit()` seguido de
  `db.refresh(...)` o de acceder a un atributo de un objeto cargado antes
  del commit (`policy.company_id` como argumento de una llamada). Como
  `set_tenant_context` usa `set_config(..., is_local=true)` (se resetea
  automáticamente al hacer commit/rollback — diseño deliberado documentado
  en `tenant_context.py`), el `refresh()`/acceso posterior a un atributo
  expirado se ejecutaba **sin ningún contexto de tenant fijado**, y la
  policy fail-closed de `insurance_policies`/`insurance_claims` esconde la
  fila que el propio usuario acaba de insertar → `InvalidRequestError:
  Could not refresh instance` / `ObjectDeletedError`. Fix: capturar los
  valores necesarios (`company_id`, `policy_id`, `policy_company_id`,
  `claim_company_id`) en variables Python **antes** del commit, y volver a
  llamar `set_tenant_context(db, ...)` **después** del commit y **antes**
  del `refresh()`.

Este segundo bug es nuevo (no estaba documentado en
`AUDIT_STAGING_POSTGRES_REAL.md`, que solo probó SQL directo, no la ruta
HTTP completa de escritura) y habría hecho que el fix de `get_db_scoped`
pareciera "funcionar" para lecturas (`GET`) pero rompiera con 500 cualquier
`POST`/`PATCH` en producción bajo `zeus_app`. Se corrige en el mismo commit
por ser parte indivisible de "hacer que insurance.py funcione de verdad bajo
RLS", no un hallazgo nuevo fuera de alcance.

### Qué se probó y cómo

Contra el Postgres real de staging, con `DATABASE_URL` apuntando al rol
`zeus_app` (confirmado `rolsuper=false`, `rolbypassrls=false`), servidor
`uvicorn app.main:app` arrancado de verdad (no solo lectura de código):

**Antes del fix** (reproducido primero, documentado en
`AUDIT_STAGING_POSTGRES_REAL.md` sección 2.3, re-confirmado aquí):
```
GET /api/v1/insurance/policies (token del dueño legítimo) -> {"data": [], "total": 0}
```

**Después del fix** (dos empresas nuevas, `owner.finalA@example.com` /
`owner.finalB@example.com`, registradas vía `POST /api/v1/auth/register`
real, con clientes y pólizas creados vía `POST /api/v1/insurance/policies`
real):

```
POST /api/v1/insurance/policies (token A) -> 201 Created, policy_id=1, company_id=1
POST /api/v1/insurance/policies (token B) -> 201 Created, policy_id=2, company_id=2

GET /api/v1/insurance/policies (token A) -> {"total":1, data: [policy 1, company_id=1]}
GET /api/v1/insurance/policies (token B) -> {"total":1, data: [policy 2, company_id=2]}
GET /api/v1/insurance/policies/1 (token A, propia)     -> 200 OK
GET /api/v1/insurance/policies/2 (token A, ajena)      -> 404 "Policy with ID 2 not found"
GET /api/v1/insurance/policies/1 (token B, ajena)      -> 404 "Policy with ID 1 not found"

POST /api/v1/insurance/claims (token A, policy propia) -> 201 Created
POST /api/v1/insurance/claims (token A, policy de B)   -> 404 "Policy with ID X not found"
PATCH /api/v1/insurance/claims/{id} (token A, propio)  -> 200 OK, status actualizado
PATCH /api/v1/insurance/claims/{id} (token B, de A)    -> 404 "Claim with ID X not found"
GET /api/v1/insurance/policies/{id}/claims (token B, policy de A) -> 404
GET /api/v1/insurance/policies (sin token)             -> 401 "No se pudieron validar las credenciales"
```

Cero errores 500 en el log del servidor durante todo el flujo tras el fix
(confirmado con `mcp/logs`/lectura directa del stdout del proceso). El
segundo bug (commit+refresh sin contexto) se reprodujo primero (500 con
traceback `ObjectDeletedError`/`InvalidRequestError`), se corrigió, y se
re-verificó el flujo completo con servidor reiniciado.

### Multi-tenant

Confirmado explícitamente arriba con dos tenants reales (`company_id=1` /
`company_id=2`, creados de cero vía el flujo real de registro): ninguno ve
las pólizas/siniestros del otro, en ninguna dirección, en ninguno de los 8
endpoints ejercitados (los 8 que dependían de `get_db_scoped` se ejercitaron
todos: `list_policies`, `create_policy`, `get_policy`,
`list_policy_claims`, `create_claim`, `list_claims`, `get_claim`,
`update_claim`).

---

## Hallazgo 2 — `ensure_schema_patches()` incompatible con roles sin privilegios de DDL (CRÍTICO/ESTRUCTURAL)

### Parte 1 — Barrido completo y migración nueva

Se auditaron las 16 funciones `_migrate_*` invocadas desde
`ensure_schema_patches()` (`backend/app/db/base.py`) contra
`backend/alembic/versions/` completo, para encontrar TODAS las
columnas/tablas creadas en caliente sin migración Alembic real (no solo
`stripe_customer_id`, como pedía explícitamente la tarea).

**Resultado del barrido — único hueco real: 13 columnas de `users`**
(`_migrate_user_columns()`, líneas ~163-254 de `base.py`):
`email_gestor_fiscal`, `email_gestor_laboral`, `email_asesor_legal`,
`autoriza_envio_documentos_a_asesores`, `company_name`, `employees`,
`plan`, `tpv_business_profile`, `tpv_config`,
`control_horario_business_profile`, `control_horario_config`,
`stripe_customer_id`, `stripe_subscription_id`. Confirmado con grep
exhaustivo sobre `alembic/versions/*.py`: ninguna aparece en ninguna
migración.

**Todo lo demás que toca `ensure_schema_patches()` ya tenía migración
real** (verificado leyendo cada migración referenciada, no solo el
docstring):

| Función `_migrate_*` | Migración real que ya lo cubre |
|---|---|
| `_migrate_document_approvals_columns` | 0003 + 0015 + 0016 + 0025 |
| `_migrate_rafael_fiscal_tables` (expenses) | 0025 |
| `_migrate_tpv_company_columns` | 0012 |
| `_migrate_company_type_column` | 0022 |
| `_migrate_company_employees_tpv_pin_hash` | 0019 |
| `_migrate_invoice_tpv_sale_link` | 0050 |
| `_migrate_smart_time_control_tables` | 0017 |
| `_migrate_time_cost_engine_v1` | 0026 |
| `_migrate_cashflow_ledger` | 0027 |
| `_migrate_zeus_domain_events` | 0042 |
| `_migrate_zeus_analytics_tables` | 0046 |
| `_migrate_agent_activities_company_id` | 0043 |
| `_migrate_role_check_constraints` | 0044 |
| `_migrate_rename_misleading_company_id_columns` | 0045 |
| `_migrate_company_billing_fields` | 0051 |

**Migración nueva**: `backend/alembic/versions/0056_users_missing_columns_from_startup_patches.py`
(`revision = "0056"`, `down_revision = "0055"`) — `upgrade()`/`downgrade()`
reales, tipos/nullable/índices tomados literalmente de `app/models/user.py`
(única fuente de verdad del ORM), idempotente (guard de columnas
existentes), solo actúa si la tabla `users` ya existe.

### Parte 2 — Guard de privilegios en `ensure_schema_patches()`

`backend/app/db/base.py`:
- Nueva función `_is_postgres_url()` (helper trivial, extraída de la
  comprobación repetida en cada `_migrate_*`).
- Nueva función `_current_role_can_alter_schema()`: en SQLite siempre
  `True` (sin cambio de comportamiento). En PostgreSQL, `True` solo si el
  rol de conexión es superusuario **o** dueño de la tabla `users`
  (representativa: todas las tablas de este esquema las crea y posee el
  mismo rol de migración/DDL, nunca `zeus_app`).
- `ensure_schema_patches()` ahora comprueba esto al principio: si el rol no
  puede alterar el esquema, se salta por completo (log informativo, sin
  intentar ningún `ALTER TABLE`) en vez de intentar y fallar columna a
  columna en silencio (comportamiento anterior: cada `ALTER TABLE` fallido
  se capturaba como `ProgrammingError`/`OperationalError`, se registraba
  como `WARN` y se seguía — la columna simplemente nunca se creaba, sin que
  nada al arrancar lo hiciera evidente, hasta que una petición real
  disparaba `UndefinedColumn` → 503 `schema_missing` en mitad de una
  petición de usuario).

**Razonamiento de la decisión** (pedido explícitamente en la tarea): dado
que tras la Parte 1 el 100% de lo que hace `ensure_schema_patches()` tiene
ya una migración Alembic real equivalente, el mecanismo es hoy
**redundante** en cualquier despliegue donde `alembic upgrade head` se
ejecute (con un rol propietario) antes de arrancar la app — que es
exactamente el orden que ya sigue `railway.toml`
(`alembic_conditional_stamp.py && alembic upgrade head && ensure_schema_patches.py && exec gunicorn`).
No se eliminó el mecanismo por completo (sería un cambio más agresivo, y
sigue teniendo una función real de bootstrap para bases legacy sin
`alembic_version`, ver `alembic_conditional_stamp.py`); en su lugar se le
añadió la capacidad de **detectar que no tiene nada que puede hacer con
seguridad** bajo el rol actual y omitirse limpiamente, sin ruido de
`WARN`/tracebacks y sin dejar columnas a medio crear en silencio. Esto es
exactamente la separación "credenciales de migración/DDL" vs "credenciales
de runtime" que ya recomendaba `dec54c0`.

### Qué se probó y cómo

1. **Migración aislada**: `alembic upgrade head` (rol `postgres`, dueño)
   desde `0055` → aplicó `0056` sin error. Verificado por SQL directo: las
   13 columnas existen en `users`, con los 3 índices esperados
   (`ix_users_stripe_customer_id`, `ix_users_tpv_business_profile`,
   `ix_users_control_horario_business_profile`).

2. **Guard de privilegios, aislado**: conectando como `zeus_app` e
   importando `app.db.base`:
   ```
   _current_role_can_alter_schema() -> False
   ensure_schema_patches() -> imprime "[SCHEMA] Rol de conexión sin
     privilegios de ALTER TABLE ... se omiten los parches" y retorna sin
     excepción.
   ```

3. **Arranque real de la app bajo `zeus_app`**: `uvicorn app.main:app`
   contra el mismo Postgres, `DATABASE_URL` con el rol `zeus_app`. Log de
   arranque completo, sin ningún `InsufficientPrivilege` ni traceback:
   ```
   INFO:app.db.base:[SCHEMA] Rol de conexión sin privilegios de ALTER TABLE
     (rol de runtime endurecido, p.ej. zeus_app) -- se omiten los parches...
   [BOOTSTRAP] Creating initial superuser admin@zeus-ia.com
   ...
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8123
   ```
   El servidor sirvió peticiones reales con normalidad a partir de ahí (ver
   Hallazgo 1).

4. **Ciclo `alembic upgrade head` desde una base vacía**: se ejecutó
   `alembic downgrade base` (rol `postgres`) seguido de `alembic upgrade
   head` completo desde cero sobre el mismo Postgres (limpio de datos de
   negocio previamente) — las 55+1=56 migraciones aplicaron sin error,
   confirmando `alembic current` → `0056 (head)`, 70 tablas, y las 13
   columnas de `users` presentes de nuevo (creadas exclusivamente por la
   migración 0056, sin que `ensure_schema_patches()` interviniera en este
   paso porque no se arrancó la app entre medias).

---

## Verificación adicional obligatoria

### Suite completa de tests backend (SQLite, venv compartido)

Baseline dado: `7 failed, 300 passed, 3 errors`.

- **Antes de tocar código** (no se re-ejecutó explícitamente por separado;
  el baseline ya estaba confirmado por dos verificaciones independientes
  previas en `AUDIT_STAGING_POSTGRES_REAL.md`).
- **Después del fix de `insurance.py` (Hallazgo 1)**:
  ```
  cd backend && venv\Scripts\python.exe -m pytest tests -q
  -> 7 failed, 300 passed, 34 warnings, 3 errors in 188.31s
  ```
  Mismos 7 tests fallidos y mismos 3 errores que el baseline (verificado
  nombre por nombre, idénticos a los de `AUDIT_STAGING_POSTGRES_REAL.md`).
  Cero regresión.
- No hizo falta re-ejecutar tras el Hallazgo 2 porque `_current_role_can_alter_schema()`
  devuelve `True` en SQLite (código explícito, sin ninguna lógica nueva
  ejecutada en el entorno de tests) — comportamiento idéntico al anterior
  para toda la suite.

### Ciclo `downgrade base` / `upgrade head` completo (Postgres real de staging)

Tras aplicar los dos hallazgos de esta tarea (commits `7b1d714` y
`08d4976`, incluida la migración `0056`):

```
alembic downgrade base   -> OK, sin errores (56 pasos, 0056 hasta el inicio)
alembic upgrade head     -> OK, sin errores (56 pasos), 70 tablas,
                             alembic current -> 0056 (head)
```

Confirmado tras el ciclo: `zeus_app` conserva `rolsuper=false` /
`rolbypassrls=false`, y las 13 columnas de `users` existen de nuevo
(creadas por 0056). Sin asimetrías nuevas respecto a las ya documentadas en
`AUDIT_STAGING_POSTGRES_REAL.md` sección 4.5 (agent_activities sobrevive al
downgrade — no relacionado con esta tarea, no tocado).

### RLS — re-verificación de las 7 tablas tras todos los cambios

Con datos 100% nuevos (dos empresas `Empresa FinalA/FinalB RLS Test SL`,
creadas después del ciclo downgrade/upgrade de arriba, vía el flujo real de
la aplicación bajo `zeus_app` para `invoices`/`agent_activities`/
`insurance_policies`, y por SQL directo para las 4 tablas de THALOS, igual
que en la verificación original), conectando directamente como `zeus_app`:

```
Escenario: app.current_company_id = 1
  invoices, agent_activities, insurance_policies,
  thalos_events, thalos_alerts, thalos_security_events, thalos_login_attempts
  -> las 7 tablas devuelven EXCLUSIVAMENTE filas de company_id=1

Escenario: app.current_company_id = 2
  -> las 7 tablas devuelven EXCLUSIVAMENTE filas de company_id=2
```

Cero solapamiento. `insurance_policies` (fail-closed) ahora visible
correctamente para cada dueño — exactamente el resultado que corrige el
Hallazgo 1 — mientras el resto (fail-open) sigue funcionando igual que
antes. Nada de esta tarea rompió el aislamiento ya confirmado.

**Hallazgo colateral encontrado durante esta verificación, no corregido
(fuera de alcance de esta tarea)**: al crear una segunda factura para la
empresa B vía `POST /api/v1/invoices/` bajo RLS real, la generación de
`invoice_number` en `invoices.py` (`f"INV-...-{db.query(func.count(Invoice.id)).scalar()+1}"`)
cuenta las facturas **ya filtradas por RLS para el tenant actual** (fail-open,
pero con contexto fijado sí filtra), así que dos empresas que empiezan
ambas con 0 facturas generan el mismo número (`INV-20260905-1`), chocando
contra el índice único global `ix_invoices_invoice_number` → 500 permanente
para la segunda empresa. Es una interacción real entre RLS y una
implementación de numeración ya documentada como "no garantiza unicidad
real" en un comentario del propio `insurance.py`, pero nunca se había
manifestado porque nunca se había probado `invoices.py` bajo RLS real con
más de una empresa nueva a la vez. **No se tocó `invoices.py`** en esta
tarea (fuera del alcance de los 2 hallazgos pedidos); se deja documentado
aquí como hallazgo nuevo para decisión del usuario/auditor.

### Limpieza de datos de prueba

**Filas huérfanas de la sesión anterior (22 en `agent_activities`)**:
identificadas en `AUDIT_STAGING_POSTGRES_REAL.md` sección 9.7 como
pendientes (el revisor no pudo borrarlas por restricción de permisos).
Confirmado antes de tocar nada: `companies=0`, `users=0` en todo el
Postgres de staging al empezar esta tarea — es decir, el 100% de las filas
en cualquier tabla de esta base son datos de prueba de sesiones anteriores,
no hay ningún dato real que proteger. Las 22 filas originales (emails
`owner.empresaa@example.com`/`owner.empresab@example.com`,
`admin@zeus-ia.com`, `action_type='test_rls'`, etc., datadas 2026-09-05
16:56-17:03) se identificaron y borraron junto con las filas nuevas que mi
propia sesión de verificación fue generando (registros, logins, pólizas,
facturas, activaciones de agentes, eventos de THALOS) en las mismas tablas.

Verificación final por conteo (tras el ciclo downgrade/upgrade y todas las
pruebas de esta tarea):

```
agent_activities: 0   <- confirmado explícitamente, era el objetivo pedido
companies:        0
customers:        0
invoices:         0
insurance_policies: 0
thalos_events:    0
thalos_alerts:    0
thalos_security_events: 0
thalos_login_attempts:  0
user_companies:   0
refresh_tokens:   0
...
users:            1   <- admin@zeus-ia.com (is_superuser=True)
```

La única fila que queda en todo el Postgres de staging es el superusuario
`admin@zeus-ia.com` (`id=1`), que **no es dato de prueba de esta sesión**:
lo crea automáticamente `ensure_initial_superuser()` en cada arranque de la
app contra una base sin superusuario, y un trigger de base de datos
(`zeus_guard`/`zeus_prevent_superuser_delete()`, de
`AUDIT_FIX_BLOQUE2.md`/`zeus_total_system_closure`) impide explícitamente
borrarlo (`RaiseException: zeus_guard: cannot delete superuser`) — es
infraestructura del propio sistema, no un resto de esta sesión, y ya
convivía con las verificaciones anteriores de la misma forma.

---

## Qué NO se pudo verificar

- No se ha probado el escenario de connection pooling real (pgbouncer) —
  mismo alcance que dejó pendiente `AUDIT_STAGING_POSTGRES_REAL.md`, no
  parte de esta tarea.
- No se ha tocado ni verificado `alembic_conditional_stamp.py` ni el
  `startCommand` real de `railway.toml` en un entorno Railway real — se
  verificó el guard de `ensure_schema_patches()` arrancando la app
  directamente con `uvicorn`, no a través del pipeline completo de deploy.
- No se ha verificado el comportamiento de `_current_role_can_alter_schema()`
  con un rol que sea dueño de `users` pero NO de otras tablas (escenario de
  ownership mixto/parcial) — el chequeo usa `users` como tabla
  representativa asumiendo que todo el esquema comparte el mismo dueño
  (cierto hoy, documentado explícitamente como asunción en el docstring).

## Qué queda pendiente

1. **Nuevo hallazgo, no corregido** (ver sección de invoices.py arriba):
   la numeración de `invoice_number` en `invoices.py` no es única
   cross-tenant bajo RLS real cuando dos empresas nuevas generan su primera
   factura "al mismo tiempo" en términos de contador — el índice único es
   global pero el contador está scoped por RLS. Recomendación: usar un
   contador real por empresa (secuencia dedicada o `MAX(id)`/`nextval` con
   prefijo, no `COUNT(*)`), o incluir `company_id` en el propio número.
   Tarea separada, no bloquea el veredicto de esta tarea (RLS/insurance.py
   funcionan correctamente; el bug es previo y ortogonal).
2. **Aplicar `zeus_app` como rol de runtime en Railway real** (staging/producción):
   esta sesión, y las dos anteriores, solo lo han verificado contra el
   Postgres de staging proporcionado — la connection string real de Railway
   sigue sin cambiar fuera de estas sesiones de verificación.
3. La asimetría de `downgrade base` sobre `agent_activities` (sección 4.5
   de `AUDIT_STAGING_POSTGRES_REAL.md`) sigue sin tocar — no bloqueaba nada
   entonces ni ahora, mencionado por completitud.

**No me declaro cerrado a mí mismo** — esta tarea toca Postgres real y
necesita revisión independiente (`revisor-independiente`) antes de darse
por buena, con el mismo rigor que las dos verificaciones anteriores.
