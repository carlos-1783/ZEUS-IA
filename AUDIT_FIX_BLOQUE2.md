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

---

## Tarea adicional — Bug de guardado en "Configuración inicial ZEUS" (onboarding)

Reportado tras cerrar las 7 tareas: el formulario de onboarding (3 pasos)
fallaba al pulsar "Finalizar configuración" con "No se pudo guardar la
configuración".

**Hipótesis a descartar primero (pedida explícitamente)**: que el fix de
Stripe del Bloque 1 en `/api/v1/onboarding/create-account` estuviera
bloqueando este flujo. **Descartada con evidencia**: el formulario llama a
`POST /api/v1/auth/onboarding/profile`, un endpoint completamente distinto.
Además esta rama parte de `main` y no incluye el fix de Stripe del Bloque 1
(vive sin mergear en `feature/fix-seguridad-critica`) — no había nada de
Stripe que pudiera interferir aquí.

**Causa real** (reproducida en el navegador contra la BD SQLite local real
del usuario, leyendo la consola del backend):
```
sqlite3.OperationalError: no such column: companies.company_type
sqlite3.OperationalError: no such column: company_employees.tpv_pin_hash
```
Ambas columnas existen en los modelos y tienen migración Alembic (0022 y
0019) pero nunca tuvieron parche de arranque en `ensure_schema_patches()`
— mismo patrón de deuda técnica que el resto de este bloque. Cualquier
query ORM sobre `Company`/`CompanyEmployee` rompía.

**Fix**: `_migrate_company_type_column()` y
`_migrate_company_employees_tpv_pin_hash()` en `app/db/base.py`, mismo
patrón que el resto de parches de este archivo.

**Verificado**: reproducido el error contra copia exacta de la BD real del
usuario; con el fix, `onboarding_status()` y `onboarding_profile()`
ejecutan sin error; verificado además en el navegador real, con la cuenta
real del usuario, contra sus datos reales ya corregidos — 3 pasos,
"Finalizar configuración" → `POST /onboarding/profile` → 200 OK →
`/dashboard`. Datos de prueba descartados tras la verificación; la BD local
del usuario quedó restaurada a su estado original (el fix vive en el
código, se autoaplica en el próximo arranque). Suite completa: 7 failed/214
passed/2 skipped/3 errors — sin regresiones.

Commit: `bf418ca`.

---

## Tarea adicional — Auditoría del menú lateral (sidebar): opción "Administrador"

**1. Dónde se decide qué se muestra.** Dos sitios distintos deciden la
visibilidad del botón de administración, con criterios diferentes:

- `frontend/src/components/DashboardProfesional.vue:27-35` (el dashboard
  real que ven los usuarios por defecto — confirmado en la auditoría
  original, `firstPersonMode` por defecto renderiza este componente):
  ```
  v-if="!isEmployee && (authStore.isAdmin || authStore.user?.is_superuser)"
  ```
  `authStore.isAdmin` está definido en `frontend/src/stores/auth.ts:106`
  como `computed(() => !!user.value?.is_superuser)` — es decir, la
  condición completa equivale a `is_superuser` (la segunda mitad es
  redundante, pero no está mal). **Depende del rol real** (`is_superuser`
  del usuario autenticado), no de `role` ("owner"/"employee") ni de
  `UserCompany.role` ("company_admin") — un owner de empresa cliente NO
  cumple esta condición.

- `frontend/src/views/OlymposDashboard.vue:208-211` (la vista 2D "Olimpo",
  parte del mismo componente padre pero solo se renderiza si
  `firstPersonMode === false`): el botón `⚙️ ADMIN` **no tenía ningún
  `v-if`** — se mostraba a cualquier usuario autenticado, sin comprobar rol.
  Hallazgo aparte: `firstPersonMode` es `const firstPersonMode = ref(true)`
  ([OlymposDashboard.vue:299](frontend/src/views/OlymposDashboard.vue))
  **sin ningún setter en toda la base de código** (grep exhaustivo) — la
  vista 2D con el botón sin proteger es código inalcanzable hoy, no hay
  forma de que un usuario real llegue a verlo con la UI actual.

En ambos casos, la navegación (`goToAdmin()`) es un simple
`router.push('/admin')` sin comprobación propia — toda la protección real
recae en el guard global del router y en el backend.

**2. Prueba con usuario real no-superuser de una empresa cliente.** Creada
cuenta de prueba (`sidebar.test.companyA@example.com`, registro normal,
`is_superuser=0`, `role='owner'`) y logueada en el navegador real:
- Sidebar de `DashboardProfesional.vue`: **NO aparece "Administrador"**
  (solo Panel, Analíticas, CRM oficina, Ajustes) — correcto.
- Navegación manual forzada a `http://localhost:5173/admin`: redirige
  automáticamente de vuelta al dashboard (guard en
  `frontend/src/router/index.js:514-517`:
  `if (to.meta.requiresSuperuser && !authStore.isAdmin) next(...)`, y la
  ruta `/admin` está declarada con `meta: { requiresSuperuser: true }` en
  `router/index.js:204-210`).
- Backend directo con curl y el token real de esa cuenta:
  ```
  GET /api/v1/admin/stats    -> 403 {"detail":"El usuario no tiene suficientes privilegios"}
  GET /api/v1/admin/customers -> 403
  ```
  Confirmado que los 11 endpoints de `backend/app/api/v1/endpoints/admin.py`
  (10 funciones, dos de ellas registradas en dos rutas) usan
  `Depends(get_current_active_superuser)` — ninguno se salta la
  comprobación.

**3. Veredicto: NO es el hallazgo crítico.** Un cliente normal (owner de
empresa, no superusuario) no ve la opción, y si fuerza la URL o llama a la
API directamente, es rechazado tanto en frontend (redirect) como en
backend (403 real) — el backend nunca confía solo en ocultar el botón, ya
lo hacía bien antes de este audit. Esto corresponde al **punto 4** de la
tarea (menor gravedad), no al punto 3.

**4. Fix aplicado igualmente** (por consistencia y para que no se convierta
en un problema real si `firstPersonMode` llega a ser togglable en el
futuro): añadido `v-if="authStore.isAdmin"` al botón `⚙️ ADMIN` de
`OlymposDashboard.vue`, mismo criterio que `DashboardProfesional.vue`.

Verificado en el navegador tras el cambio: login con la cuenta de prueba,
sidebar sigue sin mostrar "Administrador", sin errores nuevos en consola
(el único error de consola presente, `shouldShowTPV is not defined` en
`DashboardProfesional.vue:586/598/610`, es preexistente y no relacionado
con este cambio — no se toca, fuera de alcance de esta tarea).

Commit: pendiente de esta misma sesión.

---

## Tarea adicional — Prueba de RLS contra PostgreSQL real (Bloque 2, cierre pendiente)

**Bloqueada**: el usuario indicó que proporcionaría la connection string de
un Postgres de prueba de Railway, pero el mensaje llegó con el placeholder
sin rellenar (`[PEGA AQUÍ LA DATABASE_URL...]`) y, en un segundo intento,
con la plantilla de formato de Railway sin sustituir
(`postgresql://USER:PASSWORD@HOST:PORT/DATABASE`). No se ha podido ejecutar
ninguna migración ni prueba contra Postgres real todavía. **La Tarea 7 (RLS)
sigue sin verificar contra Postgres real** — no se da por cerrada. Pendiente
de que el usuario aporte la cadena de conexión real (host/usuario/
contraseña reales de la pestaña "Connect" de Railway) para continuar.

**No se hizo merge ni push a `main`.**
