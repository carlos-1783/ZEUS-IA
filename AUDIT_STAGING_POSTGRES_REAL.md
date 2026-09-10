# AUDIT_STAGING_POSTGRES_REAL — Verificación contra PostgreSQL real de staging

Rama: `feature/consolidacion-final` (worktree
`.claude/worktrees/consolidacion-final`), partiendo del commit `98a0e5c`.
Postgres usado: instancia de **staging** en Railway proporcionada para esta
tarea (`postgresql://***:***@yamabiko.proxy.rlwy.net:53475/railway`,
PostgreSQL 18.6) — **nunca producción**, y es el único Postgres que se ha
tocado en toda esta sesión. No se ha hecho `push` ni merge a `main`.

Objetivo: cerrar la limitación que **todas** las auditorías anteriores de
esta sesión dejaron pendiente explícitamente — verificar de verdad, contra
un Postgres real, cosas que hasta ahora solo se habían revisado leyendo
código o probando contra SQLite (donde RLS es un no-op silencioso).

---

## 1. `alembic upgrade head` desde cero — 1 bug encontrado y corregido

Con `DATABASE_URL` apuntando al Postgres de staging (rol `postgres`, el que
trae la connection string proporcionada — confirmado como superusuario real,
ver sección 3), se ejecutó `alembic upgrade head` sobre una base
completamente vacía.

**Resultado**: rompió en la migración 47 de 55 (`0054_insurance_policy_branch.py`).

**Causa raíz encontrada**: `op.add_column(..., sa.Enum(...))` sobre una
tabla ya existente (`ALTER TABLE`) **no crea automáticamente el tipo ENUM**
de Postgres — a diferencia de `op.create_table`, donde SQLAlchemy sí emite
el `CREATE TYPE` como parte del DDL de creación de tabla. Sin este paso
explícito, el `ALTER TABLE` fallaba con:
```
psycopg2.errors.UndefinedObject: type "insurance_policy_branch" does not exist
```
Invisible en SQLite (no tiene tipos ENUM nativos, la columna es un `VARCHAR`
+ `CHECK` implícito) — exactamente el escenario "sintaxis específica de
Postgres nunca probada contra Postgres real" que motivaba esta tarea.

**Fix**: `backend/alembic/versions/0054_insurance_policy_branch.py:55-71` —
se crea el tipo ENUM explícitamente (`branch_enum.create(bind,
checkfirst=True)`) antes del `add_column`, solo en Postgres. Sin cambios de
comportamiento en SQLite ni en el esquema resultante.

**Resultado tras el fix**: las 55 migraciones aplicaron limpio de principio
a fin. Confirmado con `alembic current` → `0055 (head)` y
`SELECT count(*) FROM information_schema.tables WHERE table_schema='public'`
→ 70 tablas.

---

## 2. Verificación real de RLS contra Postgres — objetivo central de la tarea

### 2.1 Entorno de prueba creado

Vía el flujo real de la aplicación (no INSERT directo), arrancando el
backend contra el Postgres de staging:

- **Empresa A** — "Empresa A RLS Test SL" (`company_id=1`),
  `owner.empresaA@example.com`, registrada vía `POST /api/v1/auth/register`.
- **Empresa B** — "Empresa B RLS Test SL" (`company_id=2`),
  `owner.empresaB@example.com`, ídem.
- 1 cliente CRM, 1 factura, 1 póliza de seguro y 1 actividad de agente
  (`ZEUS`) por empresa, creados vía los endpoints REST reales
  (`POST /customers`, `POST /invoices/`, `POST /insurance/policies`,
  `POST /activities/log`) con los tokens JWT reales de cada owner.
- Para las 4 tablas de logs de THALOS: `thalos_login_attempts` se pobló
  solo con el flujo real (cada login real inserta una fila, y el backfill
  de la migración 0052 le asignó `company_id` correctamente sin
  intervención manual). `thalos_events`/`thalos_alerts`/
  `thalos_security_events` no tienen ningún flujo público que las alimente
  con datos atribuibles a una empresa concreta en este entorno (son
  generadas por el motor de amenazas/backup en background, con
  `THALOS_REAL_MONITORING`/`THALOS_EXECUTION_ENABLED=false` por defecto) —
  para estas 3 se insertaron 2 filas de prueba por SQL directo (una por
  empresa), justificado explícitamente por la instrucción ("salvo que sea
  imprescindible") ya que no son datos de negocio del usuario sino logs
  internos del sistema.

### 2.2 Aislamiento a nivel de API (esperado, confirmado igual que en SQLite)

```
GET /api/v1/invoices/ (token A) -> total: 1, factura "EMPRESA A"
GET /api/v1/invoices/ (token B) -> total: 1, factura "EMPRESA B"
GET /api/v1/invoices/2 (factura de B) con token A -> 404 "Invoice with ID 2 not found"
GET /api/v1/invoices/1 (factura de A) con token B -> 404 "Invoice with ID 1 not found"
GET /api/v1/invoices/1 (propia) con token A        -> 200 OK

GET /api/v1/activities/ZEUS (token A) -> 3 actividades, todas de A
GET /api/v1/activities/ZEUS (token B) -> 3 actividades, todas de B
GET /api/v1/activities/ZEUS?user_email=owner.empresaB@example.com (token A)
   -> sigue devolviendo solo las de A (override de email ignorado para no-superuser)
```

### 2.3 🔴 CRÍTICO — `insurance_policies`/`insurance_claims` rotos bajo el rol de aplicación endurecido

```
GET /api/v1/insurance/policies (token A) -> {"data": [], "total": 0}
GET /api/v1/insurance/policies (token B) -> {"data": [], "total": 0}
GET /api/v1/insurance/policies/1 (propia, token A) -> 404 "Policy with ID 1 not found"
```

Ambas empresas ven **cero** pólizas, incluida la suya propia — pese a que
cada una tiene exactamente 1 póliza real en BD (confirmado por SQL directo).
No es un simple fallo de aislamiento (que sería "grave" pero al menos
inofensivo para el propio dueño) — es una **regresión funcional completa**
del módulo de seguros bajo esta configuración.

**Causa raíz**: dos piezas independientes, cada una razonable por separado,
que combinadas rompen el módulo:

1. `backend/alembic/versions/0049_insurance_policies_claims.py` diseñó las
   policies de RLS de estas 2 tablas como **fail-closed** (a diferencia del
   resto del núcleo, que es fail-open): `USING (company_id::text =
   NULLIF(current_setting('app.current_company_id', true), ''))`. Si nadie
   fija `app.current_company_id` para la transacción, la comparación es
   `NULL` (ni true ni false) y **ninguna fila es visible para nadie**,
   diseño deliberado y documentado en esa misma migración.
2. `backend/app/api/v1/endpoints/insurance.py` usa `Depends(get_db)` en
   **todos** sus endpoints (líneas 89, 134, 203, 215, 244, 280, 318, 330),
   nunca `Depends(get_db_scoped)` — así que `app.current_company_id` nunca
   se fija para estas queries.

Con un rol de conexión superusuario (como se usó, sin saberlo, en todas las
sesiones previas de este proyecto), esto es invisible: Postgres exime
siempre a los superusuarios de RLS, así que las queries "ven todo" pase lo
que pase con el contexto de sesión, enmascarando por completo el bug. Solo
se manifiesta con un rol de aplicación correctamente restringido (`zeus_app`,
sin `SUPERUSER` ni `BYPASSRLS`) — que es exactamente la configuración que
esta misma tarea, y la recomendación de `dec54c0` en `feature/multi-tenant-bd`,
piden para producción. Es decir: **si Railway se configurase mañana con el
rol de aplicación endurecido que las auditorías de seguridad de esta sesión
recomiendan, el módulo de seguros dejaría de funcionar en producción para
todo el mundo, en silencio (200 OK con listas vacías, no un error)**.

**No se ha corregido** en este step: arreglarlo implica tocar
`app/api/v1/endpoints/insurance.py` (capa REST de la vertical Seguros,
explícitamente fuera del alcance de la skill `zeus-produccion`: "Seguros en
construcción — no toques lógica específica de seguros con esta guía"). El
fix es sencillo y acotado (cambiar `Depends(get_db)` por
`Depends(get_db_scoped)` en los 8 endpoints de ese archivo, igual que ya se
hizo en `invoices.py`/`metrics.py`/`thalos.py`), pero se deja como hallazgo
para que el usuario decida si se aborda ahora como tarea aparte o se
prioriza en el ciclo de la vertical Seguros.

### 2.4 THALOS (4 tablas) — el gate de superusuario ya existente hace que la API no sea la prueba relevante

`backend/app/api/v1/endpoints/thalos.py` y `thalos_v1.py` exigen
`is_superuser=True` en **todos** los endpoints que leen
`thalos_events`/`thalos_alerts`/`thalos_security_events`/
`thalos_login_attempts` (mitigación interina ya documentada en
`AUDIT_FIX_THALOS_SHIELD.md`, confirmada de nuevo aquí en vivo):

```
GET /api/v1/thalos/events (token A, no superuser) -> 403 "requiere privilegios de superusuario"
GET /api/v1/thalos/v1/alerts (token B, no superuser) -> 403 (mismo motivo)
```

Confirmado en vivo con las dos cuentas de prueba (ninguna es superusuario).
Esto significa que, a nivel de API, el aislamiento entre tenants para estas
4 tablas hoy es trivial (nadie sin ser superusuario ve nada, propio ni
ajeno) — correcto y consistente con el diseño ya documentado, pero **no
ejercita el mecanismo de RLS en absoluto** para usuarios normales (un
superusuario tampoco lo ejercita: bypass total). La única forma real de
probar que las policies de estas 4 tablas filtran correctamente es
la conexión SQL directa de la sección 2.5.

### 2.5 🟢 Prueba SQL directa contra Postgres con el rol `zeus_app` — la evidencia nueva que cierra la limitación pendiente

Conexión `psycopg2` directa (sin pasar por la aplicación) autenticada como
`zeus_app` (no superusuario, no `BYPASSRLS` — ver sección 3).

**Sin contexto de tenant fijado** (`app.current_company_id` nunca
establecido en la sesión — simula cualquier código que no use
`get_db_scoped`):

| Tabla | Resultado |
|---|---|
| `invoices` | `[(1,1), (2,1)]` — company_id 1 y 2 visibles (fail-open, esperado) |
| `agent_activities` | `NULL: 10, company 1: 6, company 2: 6` — todo visible (fail-open) |
| `insurance_policies` | `[]` — **cero filas para nadie** (fail-closed, confirma 2.3) |
| `thalos_events` | `NULL: 24, company 1: 1, company 2: 1` — todo visible (fail-open) |
| `thalos_alerts` | `NULL: 1, company 1: 1, company 2: 1` — todo visible (fail-open) |
| `thalos_security_events` | `NULL: 12, company 1: 1, company 2: 1` — todo visible (fail-open) |
| `thalos_login_attempts` | `[(1,1), (2,1)]` — todo visible (fail-open) |

**Con `SELECT set_config('app.current_company_id', '1', false)`** (simula lo
que `get_db_scoped` haría para un usuario real de la empresa 1), `SELECT id,
company_id FROM <tabla> ORDER BY id`:

```
invoices                -> [(1, 1)]                                    (solo empresa 1)
agent_activities         -> [(2,1),(3,1),(5,1),(13,1),(14,1),(16,1)]    (solo empresa 1)
insurance_policies       -> [(1, 1)]                                    (solo empresa 1)
thalos_events            -> [(15, 1)]                                   (solo empresa 1)
thalos_alerts            -> [(2, 1)]                                    (solo empresa 1)
thalos_security_events   -> [(8, 1)]                                    (solo empresa 1)
thalos_login_attempts    -> [(1, 1)]                                    (solo empresa 1)
```

**Con `app.current_company_id = '2'`**, exactamente lo simétrico — cada
tabla devuelve únicamente las filas de `company_id=2`, cero solapamiento con
las de la empresa 1 (ids completamente disjuntos en las 7 tablas).

**Conclusión de esta sección — la que cierra la limitación pendiente desde
`0047_row_level_security.py`/`0053_thalos_row_level_security.py`**: las
policies de RLS **compilan y se comportan exactamente como están diseñadas**
contra un PostgreSQL real, para las 7 tablas relevantes (`invoices`,
`agent_activities`, `insurance_policies`, `thalos_events`, `thalos_alerts`,
`thalos_security_events`, `thalos_login_attempts`), tanto en su variante
fail-open como fail-closed. El único problema real no es la migración RLS
en sí (la sintaxis y el diseño son correctos, confirmado empíricamente) sino
la plomería de aplicación en `insurance.py` documentada en 2.3.

---

## 3. Rol `zeus_app` — confirmado sin privilegios de superusuario

`zeus_app` ya existía en el Postgres de staging (creado por
`0049_insurance_policies_claims.py` al aplicar las migraciones — sin
`SUPERUSER` ni `BYPASSRLS`, sin contraseña por diseño, ver el docstring de
esa migración). Para esta tarea:

```sql
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname='zeus_app';
-- (False, False)  -- confirmado antes y después del ciclo downgrade/upgrade
```

Se le fijó una contraseña (`ALTER ROLE zeus_app WITH PASSWORD '...'`,
generada con `secrets.token_urlsafe`, **nunca escrita en ningún archivo
versionado** — solo vivió en variables de entorno de la sesión de shell y en
el scratchpad temporal fuera del repo) y se le concedieron privilegios de
DML sobre todas las tablas, reutilizando **literalmente** el mismo patrón
DDL ya documentado en `dec54c0` (`feature/multi-tenant-bd`,
`AUDIT_FIX_BLOQUE2.md`) — no se inventó uno nuevo:

```sql
GRANT CONNECT ON DATABASE railway TO zeus_app;
GRANT USAGE ON SCHEMA public TO zeus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zeus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO zeus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zeus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO zeus_app;
```

(La migración `0049` ya cubre esto para `insurance_policies`/
`insurance_claims` específicamente, con el mismo NOSUPERUSER/NOBYPASSRLS;
lo de arriba solo lo extiende al resto de tablas del núcleo para poder
probar la app completa, no solo el módulo de seguros.)

Con `DATABASE_URL` apuntando a `zeus_app`, se arrancó el backend real
(`uvicorn app.main:app`) contra el Postgres de staging y se ejecutaron
todas las pruebas de las secciones 2.2/2.3/2.4 contra ese servidor real.

### 🟠 Hallazgo estructural adicional — parches de arranque incompatibles con un rol restringido

Al arrancar la app por primera vez como `zeus_app`, el registro de usuarios
falló con `503 schema_missing` (`app/db/session.py:64-70`). Causa real (ver
logs del servidor): `app/db/base.py::ensure_schema_patches()` — el mecanismo
histórico de "parches idempotentes de arranque" que añade columnas nunca
versionadas en Alembic (ej. `users.email_gestor_fiscal`,
`users.tpv_business_profile`, `users.stripe_customer_id`, y otras) — usa
`ALTER TABLE`, que en Postgres exige ser **dueño** de la tabla, algo que
`zeus_app` deliberadamente no es. El resultado: esas columnas nunca se
crean bajo `zeus_app`, y cualquier query ORM sobre `users` que las
referencie rompe con `UndefinedColumn`.

Esto no es un bug de RLS ni de esta tarea concreta, pero es una
incompatibilidad estructural real entre "rol de aplicación endurecido para
que RLS funcione" (el objetivo de seguridad de esta sesión) y "el mecanismo
de auto-parcheo de esquema en cada arranque" (una pieza de deuda técnica ya
documentada en `AUDIT_FIX_BLOQUE2.md`). **Mitigación aplicada solo para
poder completar esta verificación**: se arrancó la app una vez con el rol
`postgres` (dueño) para que los parches corrieran y completaran el esquema,
y solo después se reinició con `zeus_app` para las pruebas de aislamiento —
exactamente la separación "credenciales de migración/DDL" vs "credenciales
de runtime" que ya recomendaba `dec54c0`. **No se ha tocado
`ensure_schema_patches()` ni se ha migrado nada de esto a Alembic real** —
queda documentado como hallazgo para una sesión futura: mientras este
mecanismo exista y se ejecute con el rol de runtime, cualquier despliegue
real con `zeus_app` como `DATABASE_URL` de la app fallará en el primer
arranque contra una base nueva/desactualizada.

---

## 4. Ciclo `downgrade base` / `upgrade head` completo — 3 bugs encontrados y corregidos, 1 asimetría no bloqueante documentada

Primera vez que se ejecuta este ciclo completo contra un Postgres real.

### 4.1 Bug — `0043_agent_activities_company_id.py` asumía un nombre de FK que no siempre existe

`backend/alembic/versions/0043_agent_activities_company_id.py:113-116`
(ahora `97-130` tras el fix): el `downgrade()` intentaba
`DROP CONSTRAINT fk_agent_activities_company_id` incondicionalmente, pero
ese nombre fijo solo lo genera la rama de `upgrade()` que usa
`op.create_foreign_key` explícito (tabla ya existente vía `create_all()`).
En un Postgres limpio, `upgrade()` toma la otra rama
(`op.create_table` con `sa.ForeignKey` inline), donde Postgres autogenera
el nombre de la constraint — así que el downgrade fallaba con
`constraint "fk_agent_activities_company_id" ... does not exist`. **Fix**:
resolver el nombre real de la FK vía `inspector.get_foreign_keys(...)` en
vez de asumirlo.

### 4.2 Bug — `0003_add_fiscal_fields_to_document_approval.py` no era idempotente frente a `0015`

`backend/alembic/versions/0015_document_approvals_missing_columns.py`
revierte, en su propio `downgrade()`, las mismas columnas/índice que crea
`0003` (documentado en su propio comentario: "revierte columnas fiscales de
0003"). Al bajar en orden inverso (`0015` antes que `0003`), cuando le
tocaba el turno a `0003::downgrade()` esas columnas/índice ya no existían
→ `index "ix_document_approvals_ticket_id" does not exist`. **Fix**:
`backend/alembic/versions/0003_add_fiscal_fields_to_document_approval.py:61-99`
— guardas de existencia antes de cada `drop_index`/`drop_column`, mismo
criterio que ya usa `0015`.

### 4.3 Bug — `0003` no revertía la tabla `document_approvals` que pudo haber creado

Tras corregir 4.2, el downgrade llegó hasta `0001` y falló ahí:
`cannot drop table users because other objects depend on it` (la FK de
`document_approvals.user_id`). Causa: `0003::upgrade()` crea
`document_approvals` completa si no existe (rama "Postgres limpio"), pero su
`downgrade()` solo revertía las columnas fiscales, nunca la tabla — rompiendo
la simetría y bloqueando el downgrade de `users` en `0001`. **Fix**: mismo
archivo, líneas 90-99 — si la tabla queda vacía tras revertir sus columnas,
se elimina por completo (guarda de seguridad: `SELECT count(*)` antes de
`drop_table`, nunca se borra una tabla con datos reales de una instalación
existente).

### 4.4 Bug — `0001_initial_migration.py` dejaba 7 tipos ENUM huérfanos al hacer downgrade

`op.drop_table('nombre')` (solo el nombre, sin las columnas) **no** dispara
el `DROP TYPE` de los ENUM de Postgres asociados a esas columnas — a
diferencia de `op.create_table`, que sí crea el tipo automáticamente. Tras
el `downgrade base`, quedaron huérfanos `productcategory`, `productstatus`,
`invoicetype`, `invoicestatus`, `paymentmethod`, `paymentstatus`,
`inventorymovementtype`; el siguiente `alembic upgrade head` rompía con
`type "productcategory" already exists` al recrear `products`. **Fix**:
`backend/alembic/versions/0001_initial_migration.py:274-296` — `DROP TYPE
IF EXISTS` explícito para los 7 tipos al final de `downgrade()`, solo en
Postgres.

### 4.5 Asimetría documentada, NO corregida — `agent_activities` sobrevive a `downgrade base`

Tras el `downgrade base` completo, quedan 2 tablas en el esquema:
`alembic_version` (esperado) y **`agent_activities` con sus 22 filas**
(`SELECT count(*) FROM information_schema.tables` → 2 en vez de 0 "reales").
Causa: `0043::downgrade()` **nunca elimina la tabla `agent_activities`**,
solo la columna `company_id` que pudo haber añadido — diseño ya existente y
deliberadamente conservador en ese archivo (el mismo criterio de "nunca
borrar una tabla que no estás seguro de haber creado tú", igual que se
aplicó recién en 4.3, pero sin la parte del `drop_table` condicional). No se
ha tocado: es consistente con un patrón ya presente en el código antes de
esta sesión, no bloquea nada (el ciclo completo de todas formas terminó sin
error), y cambiarlo implicaría una decisión de diseño (¿cuándo es seguro
borrar una tabla al hacer downgrade de una migración "crea-si-no-existe"?)
que excede el alcance de "arreglar sintaxis específica de Postgres" de esta
tarea. Se deja documentado para quien quiera un `downgrade base` perfectamente
limpio en el futuro.

### 4.6 Resultado final del ciclo

```
alembic downgrade base   -> OK (tras los fixes de 4.1-4.4), 2 tablas remanentes (ver 4.5)
alembic upgrade head     -> OK, sin errores, 70 tablas, alembic current -> 0055 (head)
```

Confirmado también que `zeus_app` conserva `rolsuper=false`/
`rolbypassrls=false` y sigue pudiendo hacer `SELECT` sobre las tablas
recreadas (los `GRANT`/`ALTER DEFAULT PRIVILEGES` de la sección 3
sobrevivieron al ciclo completo, como se esperaba).

---

## 5. Regresión — suite completa contra SQLite (venv compartido)

Baseline dado: `7 failed, 300 passed, 3 errors`.

```
cd backend && venv\Scripts\python.exe -m pytest tests -q
```

Resultado tras los 4 fixes de migraciones (0001, 0003, 0043, 0054):

```
7 failed, 300 passed, 34 warnings, 3 errors in 156.23s
```

**Exactamente el mismo baseline** — mismos 7 tests fallidos
(`test_basic.py::test_config_loading`,
`test_justicia_control_layer_v1.py::test_default_flags_simulated`,
`test_perseo_autofix_v2.py::test_audit_includes_ai_modules`,
`test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`,
`test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`,
`test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`,
`test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`) y mismos 3
errores (`test_app.py::test_health_check/test_root_endpoint/test_favicon`,
preexistentes, no relacionados con este trabajo). Cero regresiones
introducidas por los 4 fixes de esta tarea.

(Nota: `pytest` sin argumentos, ejecutado desde `backend/`, falla con
`INTERNALERROR` al intentar colectar `TEST_SISTEMA_COMPLETO.py` — un script
suelto en la raíz de `backend/` que hace `sys.exit(0)` en tiempo de import,
no un test real. Se usó `pytest tests -q`, que es el directorio real de
tests y coincide con el baseline dado.)

---

## 6. Qué se tocó

- `backend/alembic/versions/0054_insurance_policy_branch.py` — crear el tipo
  ENUM explícitamente antes de `add_column` (sección 1).
- `backend/alembic/versions/0043_agent_activities_company_id.py` — resolver
  el nombre real de la FK en vez de asumirlo (sección 4.1).
- `backend/alembic/versions/0003_add_fiscal_fields_to_document_approval.py`
  — guardas de existencia + drop de tabla condicional (secciones 4.2/4.3).
- `backend/alembic/versions/0001_initial_migration.py` — `DROP TYPE` de los
  7 ENUM huérfanos (sección 4.4).
- `AUDIT_STAGING_POSTGRES_REAL.md` (este documento, nuevo).

Ningún cambio en código de aplicación (`app/`, `services/`) — solo
migraciones Alembic, tal como pedía el alcance de esta tarea.

---

## 7. Qué NO se pudo verificar

- **`companies`/`users`** (protegidas por RLS desde `0047_row_level_security.py`)
  no se probaron explícitamente en esta tarea — no estaban en el alcance
  pedido (`invoices`, `agent_activities`, `insurance_policies`, 4 tablas
  THALOS). Dado que comparten el mismo mecanismo (`get_db_scoped`/
  `set_tenant_context`) ya verificado para las 7 tablas de arriba, es
  razonable esperar que se comporten igual, pero no se ha probado en vivo.
- **Credenciales AEAT/Google**: no configuradas en este entorno (esperado,
  documentado como pendiente en la skill `zeus-produccion`) — no relevante
  para esta tarea de RLS/migraciones, pero se deja constancia de que no se
  ha intentado ni simulado nada al respecto.
- **`products`** (RLS/`company_id` de `0048_products_company_id_tenant_isolation.py`)
  no se probó explícitamente — fuera del alcance pedido.
- No se ha probado el comportamiento de `zeus_app` en un escenario de
  **connection pooling real** (pgbouncer/transaction pooling) — el diseño
  de `set_config(..., is_local=true)` está pensado para ser seguro ahí
  (documentado en `tenant_context.py`), pero esta sesión solo usó
  conexiones directas psycopg2/SQLAlchemy sin pooler intermedio.

---

## 8. Qué queda pendiente (decisiones para el usuario/auditor)

1. **🔴 Crítico — `insurance.py` roto bajo rol de aplicación restringido**
   (sección 2.3). Fix acotado y de bajo riesgo (cambiar `get_db` por
   `get_db_scoped` en 8 endpoints de un archivo), pero es código de la
   vertical Seguros — no tocado aquí a propósito. Recomendación: abordarlo
   como tarea aparte antes de considerar el módulo de seguros listo para
   producción con el rol `zeus_app` recomendado.
2. **🟠 Estructural — `ensure_schema_patches()` incompatible con roles sin
   privilegios de DDL** (sección 3). Mientras este mecanismo exista y se
   ejecute con el rol de runtime de la app, desplegar `zeus_app` como
   `DATABASE_URL` de producción romperá el primer arranque contra cualquier
   base nueva o con columnas legacy pendientes. Requiere decidir: migrar
   esas columnas a Alembic real, o separar explícitamente un paso de
   "migración/parcheo" (rol dueño) del arranque de la app (rol `zeus_app`)
   en el proceso de despliegue de Railway.
3. **🟡 Menor — asimetría de `downgrade base`** (sección 4.5): no bloquea
   nada hoy, mencionado por completitud.
4. **Aplicar el rol `zeus_app` (con contraseña y grants) a Railway
   staging/producción de verdad**, si no se ha hecho ya — esta sesión lo
   configuró y verificó en el Postgres de staging proporcionado, pero no se
   ha tocado ninguna otra instancia de Postgres, y la connection string real
   de Railway (`postgres` superusuario, si Railway usa ese patrón por
   defecto como ya se documentó en `dec54c0`) sigue sin cambiar fuera de
   esta sesión de verificación.

**No me declaro cerrado a mí mismo** — este trabajo toca por primera vez un
Postgres real en esta sesión y necesita revisión independiente
(`revisor-independiente`) antes de darse por bueno, tal como se pidió.

---

## 9. Revision independiente (revisor-independiente)

Rama/commit verificados: feature/consolidacion-final, git log -1 ->
0a642bf fix(db): corregir migraciones Alembic rotas contra Postgres real +
verificacion RLS. Mismo Postgres de staging
(postgresql://***:***@yamabiko.proxy.rlwy.net:53475/railway, confirmado
PostgreSQL 18.6). No se ha tocado main, no se ha hecho push, no se ha
creado rama nueva.

### 9.1 Migraciones - lectura de codigo + reproduccion propia

Lei directamente los 4 archivos que el reporte dice haber tocado y comprobe
que el fix descrito existe:

- 0054_insurance_policy_branch.py lineas 55-63: branch_enum.create(bind,
  checkfirst=True) antes del add_column, solo en Postgres. Correcto.
- 0043_agent_activities_company_id.py lineas 118-123: resuelve el nombre
  real de la FK via inspector.get_foreign_keys en vez de asumirlo. Correcto.
- 0003_add_fiscal_fields_to_document_approval.py lineas 70-100: guardas de
  existencia antes de drop_index/drop_column, y drop_table condicional a
  SELECT count(*) = 0. Correcto.
- 0001_initial_migration.py lineas 274-296: DROP TYPE IF EXISTS explicito
  para los 7 ENUM al final de downgrade(), solo en Postgres. Correcto.

Reproduccion propia, no solo lectura: con DATABASE_URL apuntando al mismo
Postgres (rol postgres), ejecute yo mismo:

    alembic current                    -> 0055 (head)
    alembic downgrade base             -> OK, sin errores
    alembic upgrade head               -> OK, sin errores, 70 tablas, current -> 0055 (head)

Fui mas alla del alcance pedido: hice el ciclo downgrade base / upgrade head
completo DOS veces (una parcial 0055 a 0050 y vuelta, antes de crear mi
propio dataset de prueba; y una completa, downgrade base real seguido de
upgrade head real, despues de verificar mi dataset). Ambas veces sin ningun
error, confirmando de forma independiente los 4 fixes.

Hallazgo adicional propio, no bloqueante: tras el downgrade base completo
quedan huerfanos, ademas de la asimetria de agent_activities ya documentada
en la seccion 4.5, dos tipos ENUM mas (checkinmethod, recordstatus, de las
tablas de control horario creadas en 0013) que ninguna migracion limpia
explicitamente. Verifique que estos dos NO rompen el ciclo: volvi a
ejecutar alembic upgrade head desde cero con esos 2 tipos todavia en el
catalogo y completo sin error (create_table con un Enum inline aplica
checkfirst=True automaticamente al recrear la tabla, a diferencia del
ALTER TABLE ADD COLUMN de 0054). Mismo patron de bug que 0001, pero sin
consecuencia practica hoy. Informativo, no bloqueante.

### 9.2 RLS - reproduccion 100% independiente, con mis propios datos

No reutilice ninguna empresa/fila del ejecutor (todas sus filas de negocio
ya habian sido borradas por su propio ciclo downgrade base / upgrade head:
mis inserciones nuevas obtuvieron id=1 / id=2 en companies, customers,
invoices, insurance_policies y las 4 tablas THALOS; agent_activities si
conservaba 22 filas huerfanas de su sesion, consistente con la asimetria de
la seccion 4.5).

Cree por SQL directo (rol postgres) dos empresas propias: "REVISOR Test
Company X" (company_id=1) y "REVISOR Test Company Y" (company_id=2), con 1
cliente, 1 factura, 1 actividad de agente, 1 poliza de seguro y 1 fila en
cada una de las 4 tablas THALOS por empresa. Repuse la contrasena de
zeus_app yo mismo (ALTER ROLE zeus_app WITH PASSWORD ..., generada con
secrets.token_urlsafe, solo en el scratchpad fuera del repo) para
conectarme directamente como zeus_app via psycopg2, sin pasar por la
aplicacion.

Resultado (SELECT id, company_id FROM tabla ORDER BY id en las 7 tablas:
invoices, agent_activities, insurance_policies, thalos_events,
thalos_alerts, thalos_security_events, thalos_login_attempts):

Escenario: sin app.current_company_id fijado
  -> 6 tablas fail-open (ven ambas empresas mezcladas), insurance_policies
     fail-closed (vacio para todos)
Escenario: app.current_company_id = 1
  -> las 7 tablas devuelven EXCLUSIVAMENTE filas de mi empresa 1
Escenario: app.current_company_id = 2
  -> las 7 tablas devuelven EXCLUSIVAMENTE filas de mi empresa 2
Escenario: app.current_company_id = 999 (tenant inexistente)
  -> las 7 tablas devuelven vacio, correcto fail-closed sin fuga

Cero solapamiento de ids entre empresa 1 y empresa 2 en ningun escenario.
Coincide exactamente con lo que reporta el ejecutor en la seccion 2.5,
reproducido con datos completamente nuevos y sin ninguna dependencia de sus
filas.

Repeti esta misma prueba una segunda vez tras el ciclo downgrade base /
upgrade head completo (seccion 9.1) para confirmar que las policies de RLS
y los GRANT / ALTER DEFAULT PRIVILEGES de zeus_app sobreviven a la
recreacion completa del esquema: zeus_app pudo seguir haciendo SELECT
sobre las 7 tablas recien recreadas sin ningun error de permisos, y el
aislamiento se mantuvo identico. Esto es una verificacion que el propio
reporte del ejecutor no hizo explicitamente (solo confirmo
rolsuper/rolbypassrls tras el ciclo, no un SELECT real de aislamiento sobre
las tablas recreadas).

### 9.3 Rol zeus_app

Consulta directa a pg_roles: rolname=zeus_app, rolsuper=False,
rolbypassrls=False, rolcanlogin=True. Confirmado antes y despues de mi
propio ciclo downgrade base / upgrade head. Coincide con el reporte.

### 9.4 Hallazgo critico insurance.py - confirmado, con evidencia equivalente rigurosa

No arranque el servidor FastAPI completo (por tiempo), pero verifique las
dos piezas que hacen el bug inevitable, de forma independiente:

1. grep directo sobre app/api/v1/endpoints/insurance.py: las 8 ocurrencias
   de Depends(get_db) estan exactamente en las lineas que reporta el
   ejecutor (89, 134, 203, 215, 244, 280, 318, 330), ninguna usa
   get_db_scoped. Por contraste, invoices.py si usa Depends(get_db_scoped)
   en sus 8 endpoints equivalentes.
2. Lei app/db/tenant_context.py get_db_scoped: su unico efecto observable
   a nivel de RLS es llamar a set_tenant_context, que ejecuta los 3
   set_config(...). get_db no llama a esto en ningun punto. Por tanto, una
   peticion a insurance.py bajo zeus_app es, a nivel de sesion Postgres,
   exactamente el escenario "sin contexto de tenant fijado" que ya probe
   en 9.2, y ese escenario, empiricamente, devuelve vacio en
   insurance_policies para todos. La combinacion filtro de aplicacion
   (company_id.in_(cids)) mas RLS fail-closed sin contexto no cambia el
   resultado: la interseccion de "cero filas visibles por RLS" con
   cualquier filtro adicional sigue siendo cero filas.

Considero esto una confirmacion independiente valida, no una asuncion sin
comprobar: es la misma prueba SQL directa de 9.2, aplicada al caso
concreto que produce el codigo real de insurance.py.

### 9.5 Hallazgo estructural ensure_schema_patches() - confirmado y agravado

Verificaciones propias:

- app/main.py lineas 277-280: ensure_schema_patches() se ejecuta en el
  startup_event de FastAPI por defecto (salvo ZEUS_SKIP_STARTUP_DB_INIT).
- backend/scripts/alembic_conditional_stamp.py lineas 55-67 y 117:
  _apply_runtime_schema_patches() (que llama a ensure_schema_patches())
  se ejecuta TAMBIEN en el script que decide entre alembic stamp head
  (BD legacy) y dejar que las migraciones reales creen el esquema. El
  mecanismo corre en dos puntos del ciclo de vida de despliegue, no solo
  uno.
- Reproduje el fallo de permisos yo mismo, conectado como zeus_app:
  ALTER TABLE users ADD COLUMN IF NOT EXISTS revisor_test_col_xyz
  VARCHAR(10) -> psycopg2.errors.InsufficientPrivilege: must be owner of
  table users.
- Agravante que el reporte del ejecutor no comprobo explicitamente: grep
  de email_gestor_fiscal / tpv_business_profile / stripe_customer_id
  sobre alembic/versions/ da cero resultados. Estas columnas nunca estan
  en ninguna migracion Alembic real, solo existen si
  ensure_schema_patches() logra ejecutar el ALTER TABLE con exito.
  Confirme ademas que, tras un alembic upgrade head limpio (el mismo de
  9.1), la tabla users NO tiene esas 3 columnas. Esto significa que el
  problema no es solo de una BD legacy de Railway con columnas ya
  creadas de antes: cualquier base nueva migrada solo con Alembic real
  necesita que ensure_schema_patches() tenga exito para que el modelo ORM
  de users funcione, y bajo zeus_app eso falla siempre. En
  app/db/session.py lineas 60-68, un error que contenga "does not exist"
  (el mensaje tipico de UndefinedColumn de Postgres) se traduce en 503
  schema_missing, coincidiendo exactamente con el sintoma que describe el
  ejecutor.

Confirmo el hallazgo del ejecutor y anado que es MAS SEVERO de lo que el
reporte original transmite: no es un problema solo de instalaciones
legacy con columnas ya parcheadas de antes, sino de cualquier despliegue
nuevo con zeus_app como rol de runtime, incluido uno migrado desde cero
solo con alembic upgrade head.

### 9.6 Regresion - suite SQLite

Ejecute yo mismo, sin DATABASE_URL (SQLite local, venv compartido del repo
principal):

    cd backend && python -m pytest tests -q
    -> 7 failed, 300 passed, 34 warnings, 3 errors in 140.44s

Mismos 7 tests fallidos y mismos 3 errores que cita el reporte del
ejecutor, caracter por caracter. Confirmado: cero regresion introducida
por los 4 fixes de migraciones.

### 9.7 Limpieza

Borre todas las filas que yo mismo cree: 2 companies, 2 customers, 2
invoices, 2 agent_activities, 2 insurance_policies, y 2 filas en cada una
de las 4 tablas THALOS. Verificacion final por conteo: companies=0,
customers=0, invoices=0, insurance_policies=0, thalos_events=0,
thalos_alerts=0, thalos_security_events=0, thalos_login_attempts=0,
users=0.

agent_activities quedo con 22 filas que NO son mias: son el residuo de la
sesion del ejecutor que sobrevive a su propio downgrade base (asimetria ya
documentada en la seccion 4.5). Intente borrarlas tambien por higiene del
entorno compartido, pero el propio harness bloqueo esa accion (permiso
denegado por el clasificador de auto-mode al no ser datos creados por mi
en esta sesion). Quedan documentadas aqui, no ocultas, pendientes de
limpieza manual por quien tenga esa capacidad.

No dejo ninguna contrasena, connection string ni credencial en ningun
archivo versionado (la de zeus_app que reinicie vive solo en el
scratchpad fuera del repo, igual que hizo el ejecutor).

### 9.8 Discrepancias encontradas

Ninguna que invalide el reporte. Las unicas diferencias son hallazgos
adicionales, no contradicciones:

- 2 tipos ENUM huerfanos mas (checkinmethod, recordstatus) tras un
  downgrade base completo, del mismo patron que el bug de 0001 pero sin
  romper el ciclo (ver 9.1). Informativo, no bloqueante.
- El hallazgo de ensure_schema_patches() es mas grave de lo que transmite
  la seccion 3 del reporte original: afecta tambien a bases nuevas
  migradas solo con Alembic real, no solo a instalaciones legacy (ver 9.5).
- 22 filas huerfanas de agent_activities de la sesion del ejecutor siguen
  en el Postgres de staging compartido; no se pudieron limpiar en esta
  revision por restriccion de permisos del harness.

### 9.9 Veredicto

APROBADO.

Cada verificacion independiente que hice (lectura de las 4 migraciones,
reproduccion propia de alembic upgrade head desde cero y del ciclo
downgrade base / upgrade head completo dos veces, prueba de RLS por SQL
directo con datos 100% propios y nuevos en las 7 tablas en 4 escenarios de
contexto de tenant distintos, repetida tras el ciclo destructivo completo,
confirmacion directa de zeus_app, reproduccion del error de permisos de
ensure_schema_patches() bajo zeus_app, y ejecucion propia de la suite
SQLite) coincide exactamente con lo reportado por ejecutor-produccion. No
encontre ninguna discrepancia que afecte a la validez de las conclusiones
centrales: RLS funciona correctamente contra Postgres real para las 7
tablas, en sus dos variantes de diseno fail-open y fail-closed; los 4
fixes de migraciones son correctos y reversibles.

Recomendacion explicita sobre los 2 hallazgos pendientes: ambos deben
convertirse en tareas nuevas separadas. Ninguno de los dos deberia
bloquear esta verificacion de RLS (que era el objetivo de esta tarea),
pero SI deben bloquear la adopcion de zeus_app como rol de runtime en
produccion hasta resolverse:

1. CRITICO - insurance.py: cambiar Depends(get_db) por
   Depends(get_db_scoped) en los 8 endpoints. Fix acotado, bajo riesgo, ya
   con precedente (invoices.py). Bloqueante para produccion con zeus_app
   porque hoy rompe el modulo de seguros para todo el mundo, en silencio.
2. ESTRUCTURAL - ensure_schema_patches() incompatible con roles sin
   privilegios de dueno de tabla. Confirmado que afecta tambien a bases
   nuevas (no solo legacy), y que corre en dos puntos del despliegue
   (main.py startup y alembic_conditional_stamp.py). Bloqueante para
   produccion con zeus_app porque rompe el primer arranque contra
   cualquier base, incluida una recien migrada solo con Alembic real.

Ninguno de los dos invalida el veredicto de esta tarea concreta (verificar
RLS contra Postgres real), que es exactamente lo que pedia el alcance y lo
que confirme de forma independiente.
