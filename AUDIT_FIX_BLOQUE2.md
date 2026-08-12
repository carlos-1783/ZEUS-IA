# AUDIT_FIX_BLOQUE2 — Cierre del aislamiento multi-tenant a nivel de BD

Rama: `feature/multi-tenant-bd` (creada desde `main`, independiente de
`feature/fix-seguridad-critica`/Bloque 1 — no se mezclan). 7 commits
atómicos, uno por tarea. No se hizo merge ni push a `main`.

Contexto de riesgo: hay demo en vivo delante de Catalana Occidente y
Santalucía en septiembre — este bloque se trató como el de mayor prioridad
posible por eso mismo.

---

## Tarea 1 — `company_id` real en `AgentActivity` + `/metrics/dashboard`

**Qué se hizo**: columna `company_id` (FK `companies.id`, nullable) añadida
al modelo `AgentActivity`. Migración Alembic 0043 (crea la tabla completa si
no existe, o solo añade la columna si ya existe vía `create_all()` — caso
real de este proyecto). Parche idempotente adicional en
`ensure_schema_patches()` porque en el despliegue real de Railway,
`scripts/alembic_conditional_stamp.py` hace `alembic stamp head` sin
ejecutar las migraciones la primera vez que detecta `users` sin
`alembic_version` — ese parche es, en la práctica, la vía que sí garantiza
la columna en instalaciones ya existentes. `ActivityLogger.log_activity()`
infiere `company_id` automáticamente del usuario (mismo patrón que
`crm_office_service.primary_company_id`) sin tocar los ~30 call sites
existentes. `GET /api/v1/metrics/dashboard`: añadido `current_user` +
filtro por `company_ids_for_user`, con fallback a filas legacy sin
`company_id` ligadas al mismo usuario por email.

**Cómo se probó**: arranque real (SQLite), backfill idempotente ejecutado
dos veces sin duplicar, dos empresas registradas con actividad real —
inspección directa de `agent_activities` confirmó 4 filas para company_id=1
(solo user1@) y 4 para company_id=2 (solo user2@), 6 filas globales sin
company_id invisibles para ambos. Sin token → 401.

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline, sin
cambios).

---

## Tarea 2 — `User.role` / `UserCompany.role` a valores controlados

**Qué se hizo**: `CheckConstraint` en ambos modelos. `users.role`: `'owner'
| 'employee'`. `user_companies.role`: `'company_admin' | 'member' |
'owner'`. Migración 0044 vía `batch_alter_table` (segura en SQLite —
recrea la tabla — y Postgres — ALTER normal), con normalización defensiva
de cualquier valor NULL/fuera de rango antes de aplicar el constraint.

**Decisión de negocio documentada** (la pedida explícitamente por la
tarea): el grep inicial en `app/` y `services/` solo encontró
`'company_admin'`/`'member'` para `user_companies.role`. Al correr la suite
completa con esos 2 valores, **33 tests fallaron** con `CHECK constraint
failed` — 9 suites de tests crean `UserCompany` con `role="owner"` de forma
consistente en sus fixtures (`test_zeus_core_closure_v1.py`,
`test_zeus_final_closure_v2.py`, `test_zeus_full_real_flow_v3.py`,
`test_zeus_phase_2_audit.py`, `test_zeus_total_system_closure_v1.py`,
`test_afrodita_real_execution_v1.py`, `test_thalos_safe_v1.py`,
`test_thalos_workspace_writer_v1.py`, `test_time_cost_engine_v1.py`). Se
trató como valor real del dominio (no un typo aislado) y se incluyó en el
constraint.

**Cómo se probó**: migración aplicada sobre copia de BD existente (datos
preservados: 3 usuarios, 2 user_companies intactos). `INSERT`/`UPDATE` con
rol inválido rechazado por SQLite en BD migrada y BD nueva. Registro/login
reales sin errores.

**Resultado tests**: primera pasada (2 valores) → 33 failed (regresión real,
diagnosticada); segunda pasada (3 valores) → 7 failed/214 passed/2
skipped/3 errors, baseline restaurado.

---

## Tarea 3 — Naming engañoso `PayrollDraft.company_id` / `AutomationReadiness.company_id`

**Decisión de negocio** (verificada en código, no asumida, como pedía la
tarea): se renombraron las columnas a `owner_user_id` (PayrollDraft) y
`user_id` (AutomationReadiness) — **no** se cambió la FK a `companies.id`
real. Evidencia de que la FK a `users.id` ya era la correcta:
- `services/payroll_assistant_service.py` y
  `services/automation/handlers/zeus_payroll_draft.py` resuelven el valor
  con `user.id` y consultan la tabla `users`, nunca `companies`.
- `services/automation/handlers/zeus_automation_readiness.py` ya lo
  admitía en su propio comentario: *"Resolver company_id (user_id)"*.

Cambiar la FK a `companies.id` real habría exigido reescribir esta lógica
de negocio sin que el modelo lo pidiera; renombrar es la corrección mínima
y correcta al problema real (un nombre engañoso, no una FK mal apuntada).

**Qué se hizo**: renombre de columna + todos los usos directos del atributo
ORM actualizados (`payroll.py`, `payroll_assistant_service.py`,
`automation_readiness_service.py`, `admin_account_service.py`,
`scripts/purge_users_by_email.py`). Las claves del payload JSON de
automatización (`payload.get("company_id")`) se dejaron intactas — son un
contrato externo, no el naming de la columna. Migración 0045 vía
`batch_alter_table` + parche de arranque para instalaciones existentes.

**Cómo se probó**: migración aplicada sobre copia de BD existente, rename
confirmado en el schema. Arranque + registro + login + `GET
/api/v1/payroll/drafts` → 200 tras el rename.

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline).

---

## Tarea 4 — Migraciones Alembic reales para las 9 tablas restantes

**Qué se hizo**: migración 0046 con `create_table` (solo si la tabla no
existe ya) para `agent_operational_state`, `agent_decision_log`,
`agent_short_term_buffer`, `automation_readiness`, `payroll_drafts`,
`zeus_events`, `zeus_alerts`, `zeus_automations`, `zeus_automation_logs`
(las 9 que quedaban de las 10 originales — `agent_activities` ya se resolvió
en la Tarea 1). En instalaciones existentes es un no-op (las tablas ya
están, solo quedan versionadas); en Postgres/SQLite limpios, las crea.

**Cómo se probó**: se eliminaron manualmente las 9 tablas de una copia de
una BD ya migrada y se corrió `alembic upgrade head` → las 9 se recrearon
correctamente con su esquema completo (columnas, índices, FKs).

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline).

**Hallazgo nuevo documentado, no arreglado (fuera de alcance de esta
tarea)**: `alembic upgrade head` desde una SQLite genuinamente vacía sigue
fallando en la migración `0003` (`document_approvals` no existe todavía)
porque el histórico completo de migraciones de este proyecto asume que
`create_all()` ya corrió antes. No se intentó arreglar esa cadena completa
(reescribir migraciones 0001-0042 es un proyecto en sí mismo); solo se
documenta como candidato para una sesión futura.

---

## Tarea 5 — Relación ORM `Invoice.customer` ↔ `Customer.invoices`

**Qué se hizo**: se investigó el "error de importación circular" original y
se confirmó que **no existía tal problema**: ni `customer.py` ni `erp.py`
se importan entre sí (ambas relaciones usan referencias por string,
resueltas de forma perezosa por el registry de SQLAlchemy), y
`create_tables()` en `app/db/base.py` ya importa ambas clases explícitamente
antes de que se configure ningún mapper. Se reactivó la relación en ambos
lados sin tocar la estructura de imports.

**Cómo se probó**: NO con un script aislado (que sí reproduce un error
distinto — `NameError: name 'UserCompany' is not defined` — si no se
importan todos los modelos primero, confirmando por qué alguien pudo creer
que era un problema de import), sino importando la app real completa
(`import app.main`) y creando un `Customer` + `Invoice` reales:
`invoice.customer.name` y `customer.invoices` funcionan en ambos sentidos.
Esto además arregla de raíz el `AttributeError` que el Bloque 1 documentó en
`get_invoice_or_404` (`joinedload(Invoice.customer)` fallaba porque el
atributo no existía).

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline).

---

## Tarea 6 — Bug de audience-lista en `app/core/security.py`

**Dos causas raíz encontradas y corregidas** (la segunda no estaba en el
hallazgo original, pero sin arreglarla `/invoices/` seguía 100% roto):

1. **La nombrada en el hallazgo**: `jose.jwt.decode()` exige que `audience`
   sea un único string — a diferencia de PyJWT (usado en
   `app/core/jwt_auth.py`), que sí acepta listas. El código pasaba
   directamente `settings.JWT_AUDIENCE` (lista de 3 valores posibles) y
   jose lo rechazaba siempre. Fix: se lee el `aud` que reclama el propio
   token (sin verificar todavía), se confirma que esté en la lista de
   audiencias válidas, y ese valor único es el que se verifica de verdad
   contra la firma.
2. **Encontrada al verificar que el fix de arriba dejara el endpoint
   REALMENTE funcional**: con el bug de audience corregido, la función
   seguía fallando el 100% de las veces porque buscaba `User.email ==
   payload.get("sub")`, pero el `sub` real que emite el login es el ID
   numérico del usuario como string (ej. `"2"`), no un email. Fix: mismo
   fallback que ya usa la implementación que sí funciona
   (`app/core/auth.py`) — probar como ID primero, si no es numérico tratarlo
   como email.

**Hallazgo nuevo documentado, no tocado**: `get_current_user()` en este
archivo tiene ~390 líneas, con una segunda mitad de código muerto/
inalcanzable (después del primer `return`/`raise` que ya cubre todos los
casos) que repite el mismo patrón de bug de audience sin corregir. No se
toca porque nunca se ejecuta (confirmado leyendo el flujo de control) —
candidato a limpieza en una sesión futura.

**Cómo se probó**: end-to-end por HTTP real. `GET /api/v1/invoices/` y
`/api/v1/products/` sin token → 401 (igual que antes); CON token válido →
200 con datos reales (antes: 401 con CUALQUIER token, incluso uno
perfectamente válido).

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline).

---

## Tarea 7 — Row Level Security en PostgreSQL

**Qué se hizo**: migración 0047 — `ENABLE` + `FORCE ROW LEVEL SECURITY` en
`invoices`, `agent_activities`, `companies`, `users` (solo Postgres, no-op
en SQLite). Nuevo módulo `app/db/tenant_context.py` con `set_tenant_context()`
(fija `app.current_company_id`/`current_user_id`/`current_user_email` como
variables de sesión Postgres vía `set_config(..., true)` — alcance a la
transacción actual, se resetea sola, segura con connection pooling) y
`get_db_scoped()` (reemplazo drop-in de `Depends(get_db)` que además fija
ese contexto). Se migraron a `get_db_scoped` los endpoints que este mismo
bloque dejó tenant-aware: `metrics.py` (`/dashboard`) y **todos** los de
`invoices.py` — como esta rama parte de `main` (sin el fix de tenant a nivel
de aplicación del Bloque 1), aquí RLS pasa a ser la protección real para
`/api/v1/invoices/*`, no solo defensa en profundidad.

**Diseño deliberado "fail-open cuando no hay contexto"**: cada policy
permite ver todas las filas si nadie estableció el contexto de tenant para
esa transacción (igual que antes de esta migración), y solo filtra de
verdad cuando el contexto SÍ está fijado. Esto significa que activar RLS
**no puede romper ningún código que no use `get_db_scoped` explícitamente**
— ni workers de fondo, ni scripts, ni Alembic, ni los ~300 endpoints que no
se tocaron en este bloque.

**⚠️ LIMITACIÓN IMPORTANTE — léase antes de confiar en esto para la demo**:
no había PostgreSQL ni Docker disponibles en este entorno de desarrollo
(solo SQLite local). **No fue posible ejecutar ni verificar las policies de
RLS contra un PostgreSQL real.** Lo que sí se verificó:
- Sintaxis SQL revisada a mano contra el patrón estándar documentado de
  Postgres RLS (`ENABLE`/`FORCE ROW LEVEL SECURITY`, `CREATE POLICY ...
  USING (...)`, `current_setting(..., true)`, `set_config(..., true)`).
- El diseño fail-open confirmado por lectura de código: ninguna ruta de
  autorización actual depende de que RLS bloquee nada.
- Arranque completo + registro + login + `/invoices/` + `/metrics/dashboard`
  funcionando sin ningún cambio de comportamiento en SQLite (no-op
  confirmado).
- Suite completa (226 tests) sin regresiones.

Lo que **NO** se verificó: que las policies compilen sin error de sintaxis
contra un PostgreSQL real, ni que efectivamente bloqueen el acceso cruzado
entre tenants como se espera.

**Recomendación explícita antes de la demo de septiembre**: aplicar esta
migración contra una base de datos de staging en Postgres (idealmente un
clon de la de Railway) y confirmar manualmente, con dos usuarios de dos
empresas distintas, que ninguno puede ver facturas ni actividad de agentes
de la otra — antes de dar esto por cerrado para producción.

**Resultado tests**: 7 failed/214 passed/2 skipped/3 errors (baseline).

---

## Resumen de riesgo por tarea

| # | Tarea | Confianza | Verificado contra Postgres real |
|---|---|---|---|
| 1 | company_id en AgentActivity | Alta | No (solo SQLite) |
| 2 | CHECK constraint roles | Alta | No (solo SQLite, pero patrón portable estándar) |
| 3 | Rename company_id engañoso | Alta | No (solo SQLite) |
| 4 | Migraciones tablas faltantes | Alta | No (solo SQLite) |
| 5 | Relación Invoice↔Customer | Alta | N/A (no depende de dialecto) |
| 6 | Bug audience JWT | Alta | N/A (no depende de dialecto) |
| 7 | Row Level Security | **Media — sin verificar contra Postgres real** | **No — ver limitación arriba** |

Todas las migraciones (0043-0047) usan patrones ya probados en este repo
(`create_table` condicional, `batch_alter_table`, parches idempotentes en
`ensure_schema_patches()`) excepto la Tarea 7, que es funcionalidad
Postgres-específica sin precedente en el repo y sin entorno disponible para
probarla end-to-end.

**No se tocó**: `zeus_core.py`, `zeus_agents.py`, ni nada de la vertical de
seguros, tal como pedía el alcance de este bloque.

**No se hizo merge ni push a `main`.**
