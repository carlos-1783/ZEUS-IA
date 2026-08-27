# Consolidación final — ZEUS IA núcleo

Rama: `feature/consolidacion-final` (worktree `.claude/worktrees/consolidacion-final`)
Punto de partida: `main` @ `97b949a4fc650a6b0dc1f38c75bb4d21c10059ac`
Baseline de tests establecido ANTES de cualquier merge (backend, `pytest tests -q`):

```
7 failed, 214 passed, 2 skipped, 30 warnings, 3 errors in 107.76s
```

Fallos/errores preexistentes (nombres, para comparar tras cada merge):
- `tests/test_basic.py::test_config_loading`
- `tests/test_justicia_control_layer_v1.py::test_default_flags_simulated`
- `tests/test_perseo_autofix_v2.py::test_audit_includes_ai_modules`
- `tests/test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`
- `tests/test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`
- `tests/test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`
- `tests/test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`
- `tests/test_app.py::test_health_check` (ERROR)
- `tests/test_app.py::test_root_endpoint` (ERROR)
- `tests/test_app.py::test_favicon` (ERROR)

Entorno de pruebas reales: servidor `uvicorn` local sobre `backend/zeus.db` (sqlite),
puerto 8123, arrancado en background durante toda la sesión de consolidación.
Dos tenants de prueba creados vía `/api/v1/auth/register`:
- `tenant1.consolidacion@gmail.com` / `TestPass123!` → user_id 96, company_id 57
- `tenant2.consolidacion@gmail.com` / `TestPass123!` → user_id 97, company_id 58

---

## 1. `feature/fix-seguridad-critica`

**Merge-base con HEAD antes del merge**: `97b949a` (idéntico al HEAD de
`consolidacion-final` en ese momento) → **fast-forward puro, sin conflictos**.

**Qué trae** (`AUDIT_FIX_BLOQUE1.md`, 4 fixes):
- `GET /api/v1/metrics/dashboard` ahora exige `Depends(get_current_active_user)`
  y filtra las `AgentActivity` por `user_email == current_user.email` (antes:
  sin auth, agregado global de todos los usuarios).
- Todos los endpoints de `app/api/v1/endpoints/google.py` (`/calendar/event`,
  `/calendar/events`, `/gmail/send`, `/gmail/inbox`, `/drive/upload`,
  `/drive/files`, `/sheets/create`, `/sheets/write`, `/sheets/read`, `/status`)
  ahora exigen `Depends(get_current_active_user)`.
- Verificación real de pago Stripe (`stripe.PaymentIntent`/`Checkout Session`)
  antes de activar la cuenta en onboarding.
- `GET /api/v1/invoices/` filtra por `company_ids_for_user(db, current_user)`
  (tenant real), antes IDOR total (cualquier usuario veía todas las facturas).

**Verificación (código)**: confirmado leyendo
`backend/app/api/v1/endpoints/metrics.py:14-19` (Depends real + filtro por
usuario), `backend/app/api/v1/endpoints/google.py` (10 endpoints, todos con
`Depends(get_current_active_user)`), y
`backend/app/api/v1/endpoints/invoices.py:107-133` (`list_invoices` usa
`crm_svc.company_ids_for_user` para construir el filtro `Invoice.company_id.in_(...)`).

**Prueba real (curl, servidor local puerto 8123)**:

```
curl http://127.0.0.1:8123/api/v1/metrics/dashboard
→ 401 {"detail":"No se pudieron validar las credenciales"}

curl http://127.0.0.1:8123/api/v1/metrics/dashboard -H "Authorization: Bearer $TOKEN1"
→ 200 {"success":true,"total_interactions":4, ...}

curl http://127.0.0.1:8123/api/v1/google/status
→ 401 {"detail":"No se pudieron validar las credenciales"}
```

**Hallazgo colateral (NO introducido por este merge, preexistente)**: al probar
`GET /api/v1/invoices/` CON token válido, el servidor devuelve `401` con
`JWTError: audience must be a string or None` (ver log de
`app.core.security`). Es el mismo bug de audiencia JWT en `python-jose` que el
encargo describe como pendiente de arreglo en varias ramas distintas
(`fix-jwt-audience-y-tenant-invoices`, incluida como ancestro de
`checkout-publico-fix`, paso 6). Por tanto en este punto de la consolidación
**no se puede probar end-to-end con token real** el filtro de `invoices`, pero
sí se confirmó (a) que sin token da 401 y (b) que el código del filtro por
`company_id` es real y no un stub — quedará verificado end-to-end tras el
merge del paso 6, donde se repetirá la prueba con los mismos dos tenants.

**Suite de tests tras el merge**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline; esta rama no añade tests nuevos)
```
Mismos 7 nombres de fallo, mismos 3 errores. Sin regresión.

**Commit de esta fusión**: `merge: feature/fix-seguridad-critica + verificacion`

---

## 2. `feature/multi-tenant-bd`

**Merge-base con HEAD antes del merge**: `97b949a` (la rama parte de `main`
directamente, no de `fix-seguridad-critica`) → **merge real con 1 conflicto**.

**Conflicto**: `backend/app/api/v1/endpoints/metrics.py`, función
`get_dashboard_metrics`. Ambas ramas tocaron el mismo bloque: la versión de
`fix-seguridad-critica` (HEAD) filtraba por `user_email` únicamente; la de
`multi-tenant-bd` añade `get_db_scoped` (RLS real vía sesión Postgres) +
filtro por `company_id` con `crm_svc.company_ids_for_user` + bypass explícito
de superusuario. **Se resolvió a favor de `multi-tenant-bd` íntegramente**
(más completa: tenant real por empresa, no solo por email, y con capa RLS de
más profundidad) — se eliminó la versión de `fix-seguridad-critica` como
duplicada. `invoices.py` (también tocado por ambas) fusionó limpio en
automático: cambia `Depends(get_db)` → `Depends(get_db_scoped)` en los 8
endpoints del router.

**Qué más trae** (`AUDIT_FIX_BLOQUE2.md`):
- RLS real en Postgres (`alembic/versions/0047_row_level_security.py`):
  `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY` en `invoices`,
  `agent_activities`, `companies`, `users`. Guardado por `_is_postgres()` —
  no-op en SQLite (confirmado leyendo el migration file, líneas 55-119).
- `app/db/tenant_context.py` (nuevo): `get_db_scoped` fija
  `app.current_company_id` vía `set_config` a nivel de transacción Postgres;
  no-op fuera de Postgres (`if db.bind.dialect.name != "postgresql": return`).
- `values_callable=lambda x: [e.value for e in x]` en los `Enum` de
  `app/models/erp.py` (Product.category/status, InventoryMovement.movement_type,
  Invoice.invoice_type/status, Payment.payment_method/status) — corrige que
  SQLAlchemy insertaba `.name` (mayúsculas) en vez de `.value` (minúsculas)
  contra Postgres real. **Esta es una de las varias implementaciones
  independientes del bug de enum ERP** que el encargo advertía — se mantiene
  aquí y se comparará con la de `fix-enum-serialization-erp` en el paso 4.
- Reordenado `inventory_movements`/`invoices` en
  `0001_initial_migration.py` (la FK de movements a invoices se creaba antes
  de que existiera la tabla `invoices`; nunca se había ejecutado
  `upgrade()` completo contra una Postgres vacía hasta este bloque).
- `POST /api/v1/activities/log` ahora exige `Depends(get_current_active_user)`
  (antes: sin auth).
- Botón "Admin" en `OlymposDashboard.vue` ahora condicionado a
  `v-if="authStore.isAdmin"` (antes: visible para cualquier usuario).

**Regresión detectada y su causa real (no es un bug del merge)**: al correr
la suite justo después del merge, apareció una falla nueva,
`tests/test_afrodita_ops_real_v1.py::test_warehouse_summary`, con
`LookupError: 'GOODS' is not among the defined enum values`. Investigado:
la causa NO es el código fusionado, sino que el fichero `backend/zeus.db`
(sqlite local, no versionado, reutilizado durante toda la sesión de
consolidación) ya tenía filas de `products` escritas por ejecuciones
anteriores de la suite (baseline + merge 1) con el esquema ANTERIOR
(`category` guardada como `'GOODS'`, mayúsculas, comportamiento por defecto
de SQLAlchemy `Enum` sin `values_callable`). Al aplicar `values_callable`
(minúsculas), esas filas antiguas dejan de ser legibles. Se confirmó
borrando `backend/zeus.db` y volviendo a correr la suite completa desde
cero: vuelve exactamente al baseline. **Se documenta como hallazgo de
higiene de entorno de test, no como bug de producción** — en Postgres real
la migración 0001 nunca se había ejecutado antes de este bloque (según su
propio changelog), así que no hay datos preexistentes en mayúsculas que
migrar.

**Suite de tests tras el merge (con `zeus.db` fresco)**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline)
```
Mismos 7 nombres de fallo, mismos 3 errores. Sin regresión real.

**Prueba real (curl, servidor reiniciado con BD fresca, tenants recreados:
`tenant1.consolidacion@gmail.com`→company_id 29,
`tenant2.consolidacion@gmail.com`→company_id 30)**:

```
GET /api/v1/metrics/dashboard  (con token1)
→ 200 {"success":true,"total_interactions":4, ...}

POST /api/v1/activities/log  (sin token)
→ 401 {"detail":"No se pudieron validar las credenciales"}
```

**Qué NO se pudo verificar**: las policies RLS de Postgres en vivo (este
entorno solo tiene SQLite disponible localmente; el guard `_is_postgres()`
hace que el código sea no-op aquí, así que no hay forma de ejercer la
policy real sin una instancia Postgres). Tampoco se verificó con Playwright
el botón Admin oculto para usuario no-admin (verificado solo por lectura de
código: `v-if="authStore.isAdmin"`).

**Commit de esta fusión**: `merge: feature/multi-tenant-bd + verificacion`

---

## 3. `feature/limpieza-simulacion`

**Merge-base con HEAD antes del merge**: `97b949a` (parte de `main`,
independiente de los bloques 1/2, tal como decía su propio doc) → **merge
automático sin conflictos** (`git merge` usó estrategia `ort`, cero marcas de
conflicto).

**Qué trae** (`AUDIT_FIX_BLOQUE3.md`):
- Eliminado el orquestador ZEUS legacy simulado y su UI muerta:
  `backend/app/api/v1/endpoints/zeus_core.py` (-378 líneas),
  `backend/app/core/zeus_agents.py` (-773 líneas),
  `frontend/src/views/{Dashboard,DashboardHolographic,ZeusCore}.vue`,
  `frontend/src/components/{DashboardMetric,SystemStatusBadge,Zeus3D,ZeusHologram3D}.vue`.
- `GET /api/v1/agents/status` reescrito para devolver datos reales derivados
  de `agent_activities` (uptime, `decisions_today`, `last_activity` por
  agente) en vez de valores fijos.
- `backend/app/middleware/thalos_login_audit_middleware.py`: el parseo del
  body de login estaba roto — asumía JSON pero `/auth/login` usa
  `application/x-www-form-urlencoded` (OAuth2PasswordRequestForm), así que
  `json.loads()` fallaba silenciosamente y `email` quedaba siempre vacío;
  ningún login real se auditaba nunca. Se añadió parseo con `parse_qs` para
  form-urlencoded.
- Ruta `/dashboard` duplicada eliminada de `frontend/src/router/index.js`
  (había dos definiciones de rutas /dashboard y /zeus-core apuntando a
  componentes legacy); `KpiAgentsView.vue` conectado a datos reales.

**Suite de tests tras el merge (con `zeus.db` fresco)**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline)
```
Mismos 7 nombres de fallo, mismos 3 errores. Sin regresión.

**Prueba real (curl + SQL directo, servidor reiniciado con BD fresca,
tenants recreados: `tenant1.consolidacion@gmail.com`→company_id 1,
`tenant2.consolidacion@gmail.com`→company_id 2)**:

```
GET /api/v1/agents/status  (con token1)
→ 200, payload real con 6 agentes, decisions_today/decisions_last_30d/
  uptime/last_activity calculados de agent_activities (no valores fijos:
  ZEUS CORE decisions_today=9, PERSEO=2, THALOS=2, RAFAEL/JUSTICIA/AFRODITA=0
  porque no tuvieron actividad en esta sesión de pruebas)

POST /api/v1/auth/login  con password incorrecta (tenant1)
→ 401 {"detail":"Incorrect email or password"}

SELECT * FROM thalos_login_attempts:
(1, 'tenant1.consolidacion@gmail.com', '127.0.0.1', 1, '2026-08-27 05:20:09...')  [éxito]
(2, 'tenant2.consolidacion@gmail.com', '127.0.0.1', 1, '2026-08-27 05:20:11...')  [éxito]
(3, 'tenant1.consolidacion@gmail.com', '127.0.0.1', 0, '2026-08-27 05:20:20...')  [fallo]
```
Confirma que los 3 intentos de login reales (2 éxito + 1 fallo) quedaron
auditados end-to-end por THALOS — antes de este fix quedaban en 0 filas
porque el parseo del body fallaba siempre.

**Router frontend**: confirmado por lectura de código que solo queda una
definición de `/dashboard` en `frontend/src/router/index.js` (antes había
dos, una a `Dashboard.vue` legacy y otra — vía `OlymposDashboard`). No se
verificó con navegador/Playwright por límite de tiempo de esta sesión;
verificación solo de código + grep.

**Commit de esta fusión**: `merge: feature/limpieza-simulacion + verificacion`
