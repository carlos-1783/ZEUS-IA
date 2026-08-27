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

---

## 4. `feature/envio-gestoria`

**Merge-base con HEAD antes del merge**: `97b949a` (parte de `main`,
independiente) → **merge real con 3 conflictos**.

**Conflictos y resolución**:
- `backend/app/core/security.py` — dos bloques en conflicto dentro de
  `get_current_user`:
  1. Línea `audience=claimed_audience` (presente en HEAD, heredada de
     `multi-tenant-bd` vía commit `8e538f1`) vs ausencia de ese parámetro en
     `envio-gestoria`. **Se mantuvo la versión de HEAD** (pasa el audience ya
     validado contra la whitelist, coherente con el bloque de comentarios que
     la calcula justo antes, líneas 271-291, que es idéntico en ambas ramas).
  2. Resolución de `sub` como ID-o-email: ambas ramas implementan el mismo
     fallback (probar como ID, si falla o no encuentra usuario probar como
     email) con variables distintas (`subject` en HEAD, `user_identifier` en
     envio-gestoria). **Se adoptó la versión de envio-gestoria**: es
     ligeramente más robusta porque intenta el fallback a email tanto si
     `int(sub)` lanza excepción COMO si el `id` no existe en BD (la de HEAD
     solo caía a email en el primer caso).
  - **Hallazgo importante**: el bug raíz de audiencia JWT
    ("audience must be a string or None", que rompía `/invoices/`,
    `/products/`, `/customers`) ya estaba resuelto por `multi-tenant-bd`
    (commit `8e538f1`, fusionado en el paso 2) antes de llegar a este paso.
    Es decir, había **dos implementaciones independientes del mismo fix**
    (multi-tenant-bd y envio-gestoria), tal como advertía el encargo. Se
    consolidaron en una sola versión combinada (ver arriba) en vez de dejar
    ambas.
- `backend/app/models/erp.py` (líneas ~45-64) y `backend/app/schemas/erp.py`
  (líneas ~109-125): **mismo fix de enums `values_callable`** implementado
  independientemente en `multi-tenant-bd` Y en `envio-gestoria` (commit
  `cd5f16a`), con comentarios ligeramente distintos pero código idéntico.
  Se fusionó el comentario para dejar constancia de ambos orígenes; el
  código en sí no cambió (ya estaba resuelto desde el paso 2).

**Qué más trae** (`AUDIT_FIX_GESTORIA.md`):
- `invoices.py::create_invoice`: `db.flush()` + `db.expire(invoice, ["items"])`
  antes de `calculate_invoice_totals()` — sin esto, `invoice.items` podía
  verse vacío tras un `db.add(item)` suelto (no
  `invoice.items.append(item)`), devolviendo subtotal/total en 0 pese a
  tener items reales con precio. Auto-mergeado sin conflicto.
- `services/email_service.py`: nuevo `send_email_with_attachments()` — envío
  real de adjuntos (PDF/XLSX) vía SMTP Gmail, SendGrid o Resend (mismo orden
  de prioridad que `send_email()`), con `MIMEMultipart("mixed")` y
  `base64` para Resend. No es un stub: sube el fichero real desde disco
  (`Path(file_path).is_file()` se comprueba antes de adjuntar, lanza
  `FileNotFoundError` si no existe).
- `services/legal_fiscal_firewall.py::_send_to_advisor`: adjunta el fichero
  real generado por RAFAEL (factura PDF / modelo 303 XLSX) si existe; si no,
  cae al resumen JSON en el cuerpo (nunca un email vacío). Antes de enviar,
  comprueba `email_service.is_configured() or is_resend_configured() or
  is_smtp_configured()` y si NINGUNO está configurado, devuelve
  `{"success": False, "status": "email_not_configured", ...}` explícito —
  no finge un envío exitoso.
- `_get_advisor_email`: prioridad real al email configurado por el propio
  usuario (`User.email_gestor_fiscal`/`email_asesor_legal`), con
  `GESTORIA_EMAIL_DEFAULT` solo como fallback de entorno.
- `services/fiscal_db_compat.py`: `table_column_names`/`_table_names`
  reescritos con `sqlalchemy.inspect()` (dialect-agnostic) en vez de SQL
  crudo contra `information_schema.columns` (solo existe en Postgres) — en
  SQLite fallaba siempre en silencio y hacía creer que la tabla
  `document_approvals` no existía.

**Suite de tests tras el merge (con `zeus.db` fresco)**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline)
```
Mismos 7 nombres de fallo, mismos 3 errores. Sin regresión.

**Prueba real (curl, servidor reiniciado con BD fresca, tenants
`tenant1.consolidacion@gmail.com`→company_id 29,
`tenant2.consolidacion@gmail.com`→company_id 30)**:

```
GET /api/v1/invoices/  (con token1, tras el fix de audiencia JWT)
→ 200 {"success":true,"data":[],"total":0, ...}   ← antes daba 401 (ver paso 1)

POST /api/v1/products/  (crear producto real, category="goods")
→ 201, sin LookupError de enum

POST /api/v1/customers  (crear cliente real)
→ 201

POST /api/v1/invoices/  (customer_id=6, 1 item: qty=2, unit_price=100, tax_rate=0.21)
→ 201 {"subtotal":200.0,"tax_amount":0.42,"total":200.42, ...}
  (subtotal y total NO son cero — confirma que el flush+expire hace que
  calculate_invoice_totals() vea los items reales; nota: tax_amount=0.42 en
  vez de 42 es porque el motor divide tax_rate/100 esperando un entero tipo
  "21", no una fracción "0.21" — error de mi payload de prueba, no un bug
  del código)

GET /api/v1/invoices/  (con token2 — aislamiento multi-tenant)
→ 200 {"success":true,"data":[],"total":0, ...}   ← tenant2 NO ve la factura de tenant1

GET /api/v1/invoices/2  (con token2, factura creada por tenant1)
→ 403 {"detail":"No tienes permiso para acceder a esta factura"}
```

**Qué NO se pudo verificar**: el envío real de email a la gestoría
(SMTP/SendGrid/Resend) end-to-end, porque este entorno de pruebas no tiene
ninguna credencial de email configurada (`SENDGRID_API_KEY`,
`RESEND_API_KEY`, `SMTP_HOST`/`SMTP_USER` — todas `not set`). Se confirmó
por lectura de código que `_send_to_advisor` comprueba la configuración
antes de intentar enviar y devuelve un error honesto
(`status: email_not_configured`) en vez de fingir éxito — pero no se pudo
ejercer la ruta de éxito real contra un proveedor de email de verdad.

**Commit de esta fusión**: `merge: feature/envio-gestoria + verificacion`

---

## 5. `feature/hallazgos-visuales`

**Merge-base con HEAD antes del merge**: `97b949a` (parte de `main`,
independiente) → **merge automático sin conflictos** (estrategia `ort`).

**Qué trae** (`AUDIT_FIX_VISUALES.md`):
- `frontend/src/components/DashboardProfesional.vue`: el bloque de
  reintentos (100ms/500ms/1000ms tras montar) referenciaba
  `shouldShowTPV.value`/`shouldShowControlHorario.value`/`shouldShowAdmin.value`,
  variables que no existían en ningún sitio del componente — lanzaba
  `ReferenceError` en cuanto se construía el objeto del `console.log`, ANTES
  de llegar a llamar a `updateModulesForSuperuser()`. Los 3 reintentos
  llevaban muertos desde siempre. Se reemplazó por `showModule('tpv')` /
  `showModule('control_horario')` / `showModule('admin')` (la función real
  que decide visibilidad).
- Mismo archivo: `onMounted` ahora comprueba `!authStore.user` (no
  `!authStore.isAuthenticated`) antes de llamar a `initialize()` —
  `isAuthenticated` solo indica que hay token, no que `user` esté cargado.
- `frontend/src/router/index.js`: nuevo guard en `beforeEach` que fuerza
  `await authStore.initialize()` si la ruta requiere auth y `authStore.user`
  todavía no está poblado — antes, en una recarga directa a una ruta
  protegida, el guard de rol (`isAdmin`/`isEmployee`/`modules`) se evaluaba
  con `user=null` y expulsaba a superusuarios reales de `/admin`, `/tpv`, etc.
- `AfroditaOpsPanel.vue` / `AfroditaToolsPanel.vue` /
  `afrodita_workspace_api.ts`: mensajes de estado tipo `"SYSTEM ERROR — base
  de datos no disponible."` / `"NO EXECUTION"` (debug técnico en inglés,
  visible al usuario final) sustituidos por mensajes en español orientados
  al usuario; el detalle técnico se mueve a `console.warn`.

**Suite de tests tras el merge (backend, con `zeus.db` fresco)**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline — esta rama es 100% frontend)
```

**Prueba real (navegador, Chrome vía Claude Browser)**: se detectó que el
worktree no tenía `frontend/node_modules` instalado — se ejecutó
`npm install` (901 paquetes, ~5 min) antes de poder arrancar el dev server.
Al arrancar `npm run dev`, el puerto 5173 por defecto resultó estar ocupado
por un proceso de **otra sesión de agente en paralelo** en este mismo host
(`.claude/worktrees/agent-a9f8f12f24d0bc95c`, confirmado vía
`wmic process ... get CommandLine`) — no se tocó ese proceso. Se sirvió el
frontend de este worktree en un puerto aislado (5199) y, solo para esta
verificación, se relajó temporalmente (sin commitear, revertido con
`git checkout` después) la CSP de `frontend/index.html` y
`BACKEND_CORS_ORIGINS` de `backend/app/core/config.py` para permitir ese
puerto de prueba.

- Login real con `tenant1.consolidacion@gmail.com` contra un backend en
  `:8000` (mismo `zeus.db`) → dashboard carga correctamente.
- `read_console_messages` tras cargar el dashboard: **sin ningún
  `ReferenceError: shouldShowTPV is not defined`** (antes del fix, este
  mismo flujo lo disparaba 3 veces, confirmado en un intento previo contra
  el dev server equivocado — ver nota abajo). Único ruido en consola:
  peticiones de "liveness check" hardcodeadas a `localhost:5173` (polling
  de salud del backend, no relacionado con este fix) y un 404 puntual.
- Nota metodológica: un primer intento de login se hizo por error contra el
  proceso del OTRO agente en el puerto 5173 (código pre-merge de otro
  worktree) y sí mostró el `ReferenceError` — eso confirmó que el bug
  reproduce en código viejo y que la verificación real debía hacerse contra
  ESTE worktree, no contra el puerto compartido.

**Qué NO se pudo verificar**: el guard de rehidratación del router
(`beforeEach`) en un escenario de recarga directa (F5) a una ruta protegida
con superusuario — no se probó ese caso concreto por límite de tiempo; sí
se confirmó por lectura de código que la condición
`requiresAuth && authStore.isAuthenticated && !authStore.user` es correcta
y coherente con `stores/auth.ts`.

**Commit de esta fusión**: `merge: feature/hallazgos-visuales + verificacion`

---

## 6. `feature/checkout-publico-fix`

**Advertencia del encargo**: esta rama traía consigo `AUDIT_FIX_*` internos
que solo constaban en un `CICLO_PRODUCCION.md` nunca comiteado a git, así
que se trató con MENOS confianza — cada fix se re-verificó en vivo, no se
asumió nada por el número de "ciclos aprobados".

**Merge-base con HEAD antes del merge**: `97b949a` (parte de `main`,
independiente de todo lo anterior) → **merge real con 6 conflictos** en
`agents.py`, `google.py`, `invoices.py`, `metrics.py`, `onboarding.py` y
`KpiAgentsView.vue`.

**Conflictos y resolución** (criterio: versión más completa/robusta, nunca
la más simple):

1. **`metrics.py` (`get_dashboard_metrics`)**: HEAD (RLS vía `get_db_scoped`
   + `company_ids_for_user` + bypass superusuario explícito) vs.
   checkout-publico-fix (filtro simple por `user_email`, sin RLS). **Se
   mantuvo HEAD íntegro** — ya incorpora todo lo que aportaba la versión más
   simple y más.

2. **`agents.py` (`GET /status`)**: aquí, al revés, **se adoptó la versión
   de checkout-publico-fix**. HEAD (heredado de `limpieza-simulacion`)
   calculaba el estado real pero SIN NINGÚN aislamiento por tenant/usuario
   ("NO requiere autenticación... agregados a nivel de todo el sistema").
   checkout-publico-fix exige auth y filtra por `user_email` (salvo
   superusuario), documentando explícitamente la limitación de que
   `agent_activities` no tiene `company_id` propio. Además añade un tercer
   estado `"offline"` (HEAD solo distinguía online/idle) y el campo
   `"scope"` en la respuesta. Esta fue la resolución más importante de
   seguridad de este merge: sin ella, cualquier usuario autenticado habría
   podido ver el conteo de actividad de TODAS las empresas del sistema.

3. **`google.py`**: conflicto trivial de orden de imports — se mantuvo HEAD.

4. **`invoices.py`**: se detectó que checkout-publico-fix ya había
   introducido un helper `_invoice_tenant_scope()` (sin conflicto, mergeado
   limpio) que HEAD todavía no usaba consistentemente. Se resolvió
   reutilizando ese helper también en `list_invoices` (antes duplicaba la
   misma condición `or_/and_` inline) y se eliminó un bloque de
   comprobación de permisos redundante en `get_invoice_or_404` (la
   comprobación ya la hace el filtro de la query — dejarla no aportaba
   nada, solo dos formas de expresar lo mismo). **Cambio de comportamiento
   verificado**: acceder a la factura de otro tenant por ID ahora responde
   `404` en vez de `403` (el query ya no la encuentra) — es una postura de
   seguridad más conservadora (no revela que el recurso existe), verificado
   con curl real más abajo.

5. **`onboarding.py` (verificación de pago Stripe)**: HEAD tenía
   `_verify_stripe_payment_completed` (solo comprobaba `status ==
   'succeeded'`). checkout-publico-fix trae `_verify_stripe_payment_intent`,
   sustancialmente más completa: además de comprobar el estado, **compara
   el importe realmente cobrado en Stripe contra el precio del plan
   declarado** (`PRICING_PLANS`), rechazando con 402 si no coinciden —
   cierra exactamente el fraude de "pagar el plan barato y declarar el
   caro" que el PaymentIntent público (ver más abajo) hace posible si no
   se comprobara. Manejo de errores más granular
   (`stripe.error.InvalidRequestError` vs `StripeError` genérico) y logging
   estructurado. **Se adoptó íntegramente la versión de
   checkout-publico-fix**, eliminando la de HEAD.

6. **`KpiAgentsView.vue`**: ninguna versión era estrictamente superior —
   HEAD mostraba más métricas reales (uptime, decisiones de hoy, última
   actividad) pero solo distinguía online/idle; checkout-publico-fix tenía
   mejor UX de carga (6 agentes visibles desde el primer render con estado
   "Cargando…" en vez de lista vacía) y manejaba el estado "offline". **Se
   combinaron ambas**: lista inicial con placeholders + métricas reales de
   HEAD + `statusLabel()` con los 4 estados de checkout-publico-fix.

**Hallazgo de higiene de migraciones (bloqueante, corregido antes de
commitear)**: el merge trajo `alembic/versions/0043_products_company_id_
tenant_isolation.py` con `revision = "0043"`, **duplicando literalmente**
el ID de `0043_agent_activities_company_id.py` (ya mergeado en el paso 2,
con la cadena 0043→0044→0045→0046→0047 ya aplicada). Dos archivos con el
mismo `revision` es un error duro de Alembic (colisión de identificador),
no detectado por el merge automático de git porque son ficheros distintos.
**Se renombró** el fichero y su cabecera a `0048`, con
`down_revision = "0047"` (encadenado tras el head real de esta rama), sin
tocar la lógica de `upgrade()`/`downgrade()` (ya era idempotente: comprueba
columnas existentes antes de añadirlas). Verificado con un script de
análisis estático de todo `alembic/versions/`: **48 revisiones, una sola
cabeza (`0048`), cero IDs duplicados**.

**Qué más trae**:
- `POST /api/v1/integrations/stripe/checkout/payment-intent` (nuevo,
  público, sin sesión): crea un PaymentIntent real en Stripe para el alta
  de un cliente nuevo. El importe se calcula SIEMPRE en el servidor desde
  `PRICING_PLANS` según el `plan` recibido — el cliente no puede mandar un
  `amount` propio. Rate-limit dedicado y estricto en
  `security_middleware.py` (`public_checkout_payment_intent`, 10
  req/ventana) para esta ruta pública sensible.
- `POST /api/v1/activities/log`: ahora ignora cualquier `user_email` del
  payload que no coincida con `current_user.email`, salvo superusuario —
  antes cualquier usuario podía registrar actividad falsamente atribuida a
  otro email.
- `create_payment` en `invoices.py`: corregido `payment_in.method` (atributo
  inexistente en el schema, `AttributeError` garantizado) →
  `payment_in.payment_method`.
- `products.py`: mismo patrón de conversión explícita de Enum
  (`ModelProductCategory[product_in.category.name]`) que en
  `invoices.py`/`create_invoice`, mergeado limpio sin conflicto.

**Suite de tests tras el merge (con `zeus.db` fresco)**:
```
7 failed, 214 passed, 2 skipped, 3 errors  (idéntico al baseline; esta rama tampoco añade tests backend nuevos)
```

**Prueba real (curl, servidor reiniciado con el código YA fusionado —
nota: se detectó y corrigió un servidor de prueba obsoleto que seguía
sirviendo el código de un merge anterior; ver "lección" abajo):**

```
POST /api/v1/integrations/stripe/checkout/payment-intent  (plan inválido)
→ 400 {"detail":"Plan 'no-existe' no válido. Planes válidos: [...]"}

POST /api/v1/integrations/stripe/checkout/payment-intent  (plan "startup", real Stripe API)
→ 200 {"success":true,"payment_intent_id":"pi_3U8wi0RkVIjZaYJn1W10pAV4",
        "client_secret":"...", "amount":394, "currency":"eur",
        "status":"requires_payment_method"}
  (PaymentIntent REAL en Stripe test-mode, amount=394€ = 197+197 del plan
  startup — confirma que Stripe SÍ está configurado en este entorno y que
  la llamada es real, no simulada)

POST /api/v1/onboarding/create-account  (plan "enterprise", usando el
payment_intent_id de arriba, que nunca se completó)
→ 402 {"detail":"El pago no se ha completado (estado en Stripe:
        'requires_payment_method'). No se puede crear la cuenta sin un
        pago confirmado."}
  (confirma que la verificación de pago real bloquea correctamente;
  no se pudo completar un pago de prueba real con tarjeta en este
  entorno para forzar además la rama específica de "importe no coincide
  con el plan" — verificado solo por lectura de código para ese caso
  concreto)

GET /api/v1/invoices/{id}  (tenant2 pide la factura de tenant1 por ID)
→ 404 {"detail":"Invoice with ID 2 not found"}   ← antes daba 403, ahora 404
GET /api/v1/invoices/{id}  (tenant1 pide su propia factura)
→ 200, datos completos correctos

GET /api/v1/agents/status  (sin token) → 401
GET /api/v1/agents/status  (con token tenant1) → 200, "scope":"company"
GET /api/v1/agents/status  (con token tenant2) → 200, "scope":"company"
Verificado por SQL directo sobre agent_activities: tenant1 y tenant2 tienen
2 filas cada uno con su propio user_email (de su bootstrap de registro) —
coincidencia de conteo (2 y 2), pero filas DISTINTAS; no hay fuga de datos
entre tenants.
```

**Lección operativa de esta sesión (documentada para transparencia)**: al
probar este merge, la primera ronda de curl contra `/checkout/payment-intent`
devolvió `405 Method Not Allowed` — la causa no fue el código fusionado,
sino que el servidor de pruebas en el puerto 8123 llevaba corriendo desde
el paso 4 (código de ANTES de este merge) y nunca se había reiniciado. Se
mató el proceso y se arrancó uno nuevo; con eso, la ruta apareció y
respondió correctamente. Se deja constancia porque el mismo patrón podría
inducir un falso negativo en cualquier verificación futura si no se
reinicia el servidor tras cada merge.

**Commit de esta fusión**: `merge: feature/checkout-publico-fix + verificacion`

---

## 7. `feature/fix-onboarding-wizard-real`

**Hallazgo de planificación**: esta rama (841 commits) resultó tener como
ancestros `feature/facturacion-tpv-real`, `feature/onboarding-facturacion` y
`feature/rediseno-completo` — las mismas que el encargo esperaba encontrar
como ancestros de `feature/fix-thalos-shield-real` en el paso 8. Es decir,
el árbol real diverge de la suposición del encargo: ambas ramas grandes
comparten esa base común pero cada una añadió trabajo distinto encima. Se
verificó con `git merge-base --is-ancestor` en ambas direcciones: NO es
ancestro de `fix-thalos-shield-real` (son ramas hermanas divergentes, no
una contenida en la otra). Se documenta aquí y se confirmará en los pasos
9-12 si de verdad quedan como no-ops tras este merge.

**Merge-base con HEAD antes del merge**: `97b949a` → **merge real con 3
conflictos**: `backend/app/db/base.py`, `backend/app/models/company.py`,
`frontend/src/views/kpi/KpiAgentsView.vue`.

**Conflictos y resolución**:
- **`db/base.py`**: el diff de git intercaló de forma confusa DOS funciones
  completamente distintas (`_migrate_company_type_column` de HEAD y
  `_migrate_invoice_tpv_sale_link` de esta rama) porque ambas usan el mismo
  patrón de código (`inspect(engine)` + `is_postgres` + añadir columna) en
  la misma posición relativa al ancestro común. Se reconstruyeron ambas
  funciones completas por separado, leyendo con cuidado qué fragmento de
  cada bloque en conflicto pertenecía a cuál función, y se mantuvieron
  ambas íntegras (aditivo, no son alternativas de lo mismo). Verificado con
  `py_compile` y listando `grep '^def _migrate'` para confirmar que las 17
  funciones de parcheo de esquema siguen presentes y ninguna quedó
  truncada a mitad.
- **`models/company.py`**: import de `sqlalchemy` — HEAD necesitaba
  `CheckConstraint` (para el `ck_user_companies_role` de multi-tenant-bd),
  esta rama necesitaba `Text` (para `iban_encrypted`, de
  onboarding-facturacion). **Se importaron ambos**, no es una alternativa.

**Hallazgo de higiene de migraciones (bloqueante, corregido antes de
commitear)**: el merge trajo TRES ficheros más con IDs de revisión Alembic
duplicados: `0043_insurance_policies_claims.py` (colisión con
`0043_agent_activities_company_id.py`), `0044_invoice_tpv_sale_link.py`
(colisión con `0044_role_check_constraints.py`) y
`0045_company_billing_fields.py` (colisión con
`0045_fix_misleading_company_id_naming.py`). Los tres formaban su propia
cadena interna consistente (0042→0043→0044→0045). **Renumerados en bloque**
a `0049`, `0050`, `0051`, encadenados tras el head real `0048` (ver paso 6),
sin tocar lógica. Verificado con el mismo script de análisis estático:
**51 revisiones, una sola cabeza (`0051`), cero IDs duplicados**.

**Qué trae** (además de arrastrar como ancestros `facturacion-tpv-real`,
`onboarding-facturacion` y `rediseno-completo` completos):
- **El fix específico de esta rama** (`AUDIT_FIX_ONBOARDING_WIZARD.md`):
  la heurística `setup_completed` en `GET /onboarding/status` contaba como
  "señal de onboarding completado" el `CompanyEmployee` placeholder
  (`source="onboarding_owner"`) y los productos TPV de plantilla
  (`metadata_.auto_created=True`) que el registro estándar crea SIEMPRE
  para CUALQUIER alta nueva — daba `setup_completed=True` inmediatamente
  tras el registro, sin que el usuario abriera el wizard. Ahora excluye
  explícitamente esas filas auto-generadas del conteo.
- Vertical Seguros completa (`insurance.py`, modelo/schema `Insurance{Policy,Claim}`,
  migración 0049 con RLS fail-closed nativo) — fuera del alcance normal de
  esta skill (`zeus-produccion` no cubre verticales), pero llega como
  ancestro obligatorio de esta rama según el encargo; se revisó solo
  superficialmente (auth real + filtro de tenant por `company_ids_for_user`
  confirmado por lectura de código, sin pruebas end-to-end por estar fuera
  del alcance del núcleo).
- `app/core/crypto.py` (cifrado Fernet de IBAN) y `app/core/validators_es.py`
  (enmascarado de IBAN) — el IBAN de facturación nunca se devuelve en claro.
- Rediseño visual completo (`zeus-light-system.css`, tema claro con
  variables `--zeus-*`) — aplicado también a `KpiAgentsView.vue` en la
  resolución del conflicto (se combinó con la lógica de datos reales que
  ya tenía HEAD, adaptando colores de los 4 estados de pill al tema claro).

**Hallazgo importante para el cierre final (documentado, NO corregido en
este paso por estar fuera del alcance de esta rama, según su propia
auditoría)**: `POST /auth/onboarding/questionnaire` devuelve **500** por un
bug de doble sesión SQLAlchemy (`db.add(user)` sobre un `User` ya adjunto a
otra sesión — `onboarding_engine.py:417` y `auth.py:513` usan dos
proveedores `get_db` distintos, mismo patrón que ya se corrigió en
`update-advisor-emails`/`toggle-authorization` pero no aquí). Existe un
test `xfail` explícito para esto
(`test_questionnaire_endpoint_completes_and_flips_flag`). **Esto significa
que, aunque el falso positivo de `setup_completed=True` inmediato ya está
cerrado, completar el cuestionario DE VERDAD todavía no funciona vía API**
— se confirma con curl real más abajo y se retoma en el cierre final de
este documento (hallazgo crítico 4 del encargo).

**Suite de tests tras el merge (con `zeus.db` fresco)**:
```
7 failed, 218 passed, 1 xfailed, 3 errors
```
Sube de 214→218 `passed` (esta rama añade tests propios), y aparece 1
`xfailed` nuevo (el bug de doble sesión de arriba, marcado explícitamente
como fuera de alcance). Los `2 skipped` del baseline desaparecen — uno de
ellos pasó a `xfailed` con el marcador explícito. Mismos 7 nombres de
fallo y mismos 3 errores que el baseline; sin regresión.

**Prueba real (curl, servidor reiniciado con BD fresca)**:

```
POST /api/v1/auth/register  (usuario nuevo, business_type=restaurant)
→ 201, user_id=2, company_id=1

GET /api/v1/auth/onboarding/status  (inmediatamente tras registro, con token real)
→ {"setup_completed": false, "setup_inferred": false,
   "questionnaire_completed": false,
   "checks": {"tpv_products": 4, "has_tpv_profile": true,
              "company_employees_count": 1, ...}}
```
Confirma el fix: pese a tener 4 productos TPV auto-creados y 1 empleado
auto-creado (exactamente las señales que antes disparaban el falso
positivo), `setup_completed` queda en `false` — el usuario nuevo SÍ ve el
cuestionario en vez de saltárselo.

```
POST /api/v1/auth/onboarding/questionnaire  (con employees_count/uses_tpv/business_hours completos)
→ 500 {"detail":"Error interno del servidor. El servicio sigue activo; reintenta."}
```
Confirma en vivo el bug documentado (log del servidor:
`sqlalchemy.exc.InvalidRequestError: Object '<User at ...>' is already
attached to session '31' (this is '30')`) — coincide exactamente con el
diagnóstico de `AUDIT_FIX_ONBOARDING_WIZARD.md`.

**Commit de esta fusión**: `merge: feature/fix-onboarding-wizard-real + verificacion`

---

## 8. `feature/fix-thalos-shield-real`

**Merge-base con HEAD antes del merge**: `35b0d8e` (mismo punto de
divergencia que `fix-onboarding-wizard-real`, confirmado que NO es
ancestro ni descendiente de esa rama — son hermanas divergentes desde ese
commit). 7 vueltas de fix documentadas en `AUDIT_FIX_THALOS_SHIELD.md`
(2455 líneas) + `AUDIT_THALOS_ESTRUCTURAL.md` (fix de raíz, 1408 líneas) +
`AUDITORIA_TOTAL_FINAL.md` (537 líneas, auditoría final independiente).

**Merge real con 4 conflictos**:

1. **`activities.py`** (mismo bloque que en el paso 6): ambas ramas
   arreglaron independientemente el mismo endpoint `POST /activities/log`
   sin auth. Se combinaron los dos docstrings de contexto de seguridad (el
   de HEAD explica el gate de superusuario en el propio endpoint; el de
   esta rama explica por qué el executor asíncrono de THALOS es la
   superficie de ataque real) y se mantuvo la lógica de HEAD
   (`effective_user_email` con excepción para superusuario), ya que la
   defensa real contra el abuso vive en los handlers de THALOS v1 (gate de
   superusuario ahí, no solo en este endpoint) — confirmado leyendo el
   propio docstring de esta rama.
2. **`zeus_core.py` / `zeus_agents.py`** (conflicto modify/delete): esta
   rama invirtió trabajo real en estos ficheros legacy (delegar
   THALOS.SHIELD/SCAN/BLOCK en servicios reales, gate de superusuario para
   THALOS.SCAN) — pero `feature/limpieza-simulacion` (paso 3) ya los había
   borrado por ser código muerto: **confirmado de nuevo aquí** que
   `app/api/v1/__init__.py` NO registra `zeus_core.router` en ninguna
   ruta (solo `zeus_core_v2.router` bajo `/zeus-core`, que no importa
   `zeus_agents.py`). Es decir, ningún endpoint HTTP alcanzable ejecuta ese
   código, con o sin el fix. **Se mantuvo el borrado** (`git rm`) — el
   trabajo real de esta rama sobre código muerto no cambia el
   comportamiento en producción.
3. **`db/tenant_context.py`** (conflicto add/add): esta rama creó su
   propia copia del mismo módulo (multi-tenant-bd, ya fusionado en el
   paso 2, no estaba disponible cuando se escribió esta rama) para
   extender RLS a las 4 tablas de logs de THALOS. Se mantuvo la
   implementación de HEAD (`crm_svc.primary_company_id`, ya usada y
   probada por `invoices.py`/`metrics.py`/`agents.py`) — verificado que
   `services.workspace_deliverables.primary_company_id_for_user` (la
   versión de esta rama) es **funcionalmente idéntica** (mismo query,
   mismo `order_by`, solo difiere un `int()` de más) antes de descartarla,
   para no perder ningún matiz de comportamiento. Se fusionaron ambos
   docstrings (documentan el mismo mecanismo aplicado a dos familias de
   tablas distintas: ERP/CRM y logs de THALOS).

**Hallazgo de higiene de migraciones (bloqueante, corregido antes de
commitear)**: la rama trae `0046_thalos_tables_company_id.py` y
`0047_thalos_row_level_security.py`, colisionando con
`0046_missing_tables_create_all_only.py` y `0047_row_level_security.py`
(ya mergeados en el paso 2). **Renumerados** a `0052`/`0053`, encadenados
tras el head real `0051` (paso 7). Verificado: **53 revisiones, una sola
cabeza (`0053`), cero duplicados**.

**Hallazgo de higiene de tests (corregido antes de correr la suite)**: dos
ficheros de test nuevos de esta rama importan directamente de
`app.core.zeus_agents` / `app.api.v1.endpoints.zeus_core` (los módulos
muertos borrados en el punto 2) y rompían la RECOLECCIÓN completa de la
suite (`2 errors during collection`, pytest se detiene sin ejecutar NADA):
- `test_zeus_agents_thalos_real_v1.py` (254 líneas, 8 tests): el 100% de
  sus tests ejercitan exclusivamente `zeus_agents.zeus_manager` (código
  muerto). **Eliminado por completo** — no cubre ninguna ruta alcanzable.
- `test_zeus_core_scan_superuser_gate_v1.py` (115 líneas, 5 tests): mezcla
  3 tests del `zeus_core.py` muerto con 2 tests de
  `thalos_v1.thalos_v1_execute` (endpoint REAL, montado). **Se editó** para
  eliminar solo los 3 tests y el import de código muerto, conservando los
  2 tests reales del gate de superusuario de `thalos_v1_execute`.

Esta es una decisión de diseño explícita, no un intento de esconder una
regresión: el código bajo test no es alcanzable por ningún cliente HTTP
real en este estado del árbol (confirmado en el punto 2), así que un test
que lo cubra no protege nada en producción.

**Qué trae** (además de re-confirmar que `vertical-seguros`,
`facturacion-tpv-real`, `onboarding-facturacion`, `rediseno-completo`,
`rediseno-frontend-fase1` y `auditoria-real-nucleo` son ancestros — se
comprobará explícitamente en los pasos 9-12 que ya no aportan nada nuevo):
- 7 vueltas de mitigación de THALOS.SCAN/BLOCK/SHIELD: gates de
  superusuario en `thalos_v1.py::thalos_v1_execute`,
  `workspaces.py` (log_monitor), `justice.py` (compliance-events),
  handlers de automatización (`services/automation/handlers/thalos*.py`).
- Fix de raíz (no solo mitigación): migración `0052` añade `company_id`
  real a `thalos_events`/`thalos_alerts`/`thalos_login_attempts` (con
  backfill best-effort documentado con honestidad — reconoce
  explícitamente qué filas NO se pueden atribuir a una empresa real, p.ej.
  intentos de fuerza bruta con emails inventados) y `0053` añade RLS real
  (Postgres) a las 4 tablas, reutilizando `get_db_scoped`.
- `services/justice_cross_agent_v1.py::sync_cross_agent_events`: filtra
  ahora por tenant (antes filtraba eventos de todas las empresas).

**Suite de tests tras el merge (con `zeus.db` fresco, tras arreglar la
recolección)**:
```
7 failed, 288 passed, 1 xfailed, 3 errors
```
Sube de 218→288 `passed` (+70, la mayoría de los tests nuevos de esta
rama: `test_thalos_v5_exhaustive_sweep_v1.py`,
`test_thalos_v6_estructural_v1.py`, `test_thalos_v7_legacy_gate_v1.py`,
`test_workspaces_thalos_log_monitor_superuser_gate_v1.py`,
`test_thalos_company_id_structural_v1.py`,
`test_thalos_v1_execute_block_tenant.py`, y los 2 tests conservados de
`test_zeus_core_scan_superuser_gate_v1.py`). Mismos 7 nombres de fallo,
mismo xfail, mismos 3 errores del baseline. Sin regresión.

**Prueba real (curl, servidor reiniciado con BD fresca, tenants
`tenant1.consolidacion@gmail.com`→company_id 1,
`tenant2.consolidacion@gmail.com`→company_id 2)**:

```
POST /api/v1/thalos/v1/execute  {"action":"detect_suspicious_activity"}  (usuario normal, no superusuario)
→ 403 {"detail":"detect_suspicious_activity (THALOS.SCAN) requiere
        privilegios de superusuario (mitigación interina: el motor
        subyacente audita actividad global sin filtrar por empresa hasta
        que se migre el esquema)."}
```
Confirma en vivo el gate de superusuario del hallazgo más grave de esta
rama.

**Qué NO se pudo verificar**: el fix de raíz completo (RLS real de las 4
tablas de THALOS contra Postgres, migraciones 0052/0053) — mismo motivo
que el resto de RLS de esta consolidación: solo hay SQLite disponible en
este entorno, y el propio docstring de la migración ya advierte
explícitamente que no se verificó contra Postgres real durante su
desarrollo tampoco. Queda pendiente de verificación contra staging antes
de producción, tal como el propio fichero recomienda.

**Commit de esta fusión**: `merge: feature/fix-thalos-shield-real + verificacion`

---

## 9-12. `feature/vertical-seguros`, `feature/facturacion-tpv-real`, `feature/onboarding-facturacion`, `feature/rediseno-completo`

Tal como advertía el propio encargo para el caso de `fix-thalos-shield-real`
(y como se documentó explícitamente en los pasos 7 y 8 de este informe: la
relación real de ancestría no coincidía con la suposición inicial, pero el
resultado es el mismo), estas 4 ramas ya eran ancestros de
`feature/consolidacion-final` antes de llegar a este punto — arrastradas
como base común de `feature/fix-onboarding-wizard-real` (paso 7) y
`feature/fix-thalos-shield-real` (paso 8), que divergieron cada una por su
lado a partir de ellas.

**Verificado explícitamente, no asumido**:
```
git merge-base --is-ancestor feature/vertical-seguros HEAD        → YA ES ANCESTRO
git merge-base --is-ancestor feature/facturacion-tpv-real HEAD    → YA ES ANCESTRO
git merge-base --is-ancestor feature/onboarding-facturacion HEAD  → YA ES ANCESTRO
git merge-base --is-ancestor feature/rediseno-completo HEAD       → YA ES ANCESTRO
```

Y confirmado ejecutando `git merge --no-edit` real sobre cada una (tal como
pedía el encargo, sin saltarlas por la sola inspección de ancestría):
```
git merge feature/vertical-seguros        → "Already up to date."
git merge feature/facturacion-tpv-real    → "Already up to date."
git merge feature/onboarding-facturacion  → "Already up to date."
git merge feature/rediseno-completo       → "Already up to date."
```

Ningún commit nuevo, ningún conflicto, ninguna verificación adicional
necesaria — su contenido ya quedó incorporado (y ya verificado donde
aplicaba) al fusionar `feature/fix-onboarding-wizard-real` en el paso 7.

(`feature/iva-duplicado` es solo documentación, sin código — no se
fusiona, según indicaba el propio encargo.)

---

# Cierre — verificación de los 4 hallazgos críticos

Verificación final, en la rama consolidada completa (`feature/consolidacion-final`,
tras las 12 fusiones), con servidor reiniciado desde cero, BD SQLite fresca
y tenants nuevos creados en esta misma sesión de cierre. Cotejado contra la
evidencia "antes" documentada en `AUDITORIA_TOTAL_FINAL.md` (auditoría
independiente sobre `feature/fix-thalos-shield-real` en solitario, antes de
esta consolidación) donde el código no ha cambiado desde entonces.

## 1. `GET /api/v1/metrics/dashboard` — auth + aislamiento por tenant

**Antes** (`AUDITORIA_TOTAL_FINAL.md`, sección 3, en `fix-thalos-shield-real`
sin fusionar con `fix-seguridad-critica`/`multi-tenant-bd`): sin token → 200,
`total_interactions:1995` (agregado global); con token de un tenant
cualquiera → **la misma respuesta byte a byte**. Sin auth, sin aislamiento.

**Después** (esta rama consolidada, verificado ahora):
```
GET /api/v1/metrics/dashboard  (sin token)
→ 401 {"detail":"No se pudieron validar las credenciales"}

GET /api/v1/metrics/dashboard  (token tenant1, company_id=1)
→ 200 {"total_interactions":4, ...}

GET /api/v1/metrics/dashboard  (token tenant2, company_id=2)
→ 200 {"total_interactions":4, ...}
```
Verificado por SQL directo sobre `agent_activities` que NO es coincidencia
de agregado global: la tabla tiene **13 filas totales**
(`company_id=1` → 4 filas de tenant1; `company_id=2` → 4 filas de tenant2;
5 filas de sistema/`admin@zeus-ia.com` sin company_id), y cada tenant ve
únicamente sus propias 4, no las 13.

**Veredicto: CERRADO.**

## 2. `GET /api/v1/invoices/`, `/products/`, `/customers` — funcionan con token válido y filtran por tenant

**Antes** (bug de audiencia JWT en `python-jose`, documentado en al menos 3
ramas distintas — `multi-tenant-bd`, `envio-gestoria`,
`checkout-publico-fix`/`fix-jwt-audience-y-tenant-invoices` — y confirmado
en vivo por esta sesión en el paso 1 de esta consolidación, antes de que se
fusionara el fix): `401 audience must be a string or None` con CUALQUIER
token válido. `list_invoices` tampoco filtraba por `company_id` en absoluto
(IDOR total).

**Después** (esta rama consolidada, verificado ahora con dos tenants
reales, `final.tenant1@gmail.com`→company_id 1,
`final.tenant2@gmail.com`→company_id 2):
```
GET /api/v1/invoices/   (sin token) → 401
GET /api/v1/invoices/   (token tenant1) → 200 {"data":[], "total":0}
GET /api/v1/products/   (token tenant1) → 200 {"data":[], "total":0}
GET /api/v1/customers   (token tenant1) → 200 {"data":[], "total":0}

# Se crean producto+cliente+factura reales para tenant1 (POST reales, 201 cada uno)

GET /api/v1/invoices/   (token tenant2) → 200 {"data":[], "total":0}   ← NO ve la factura de tenant1
GET /api/v1/products/   (token tenant2) → 200 {"data":[], "total":0}   ← NO ve el producto de tenant1
GET /api/v1/customers   (token tenant2) → 200 {"data":[], "total":0}   ← NO ve el cliente de tenant1
GET /api/v1/invoices/   (token tenant1) → 200 {"data":[{...factura real, total:60.5...}], "total":1}
```

**Veredicto: CERRADO** (bug de audiencia JWT resuelto; aislamiento por
`company_id` real y verificado en las 3 rutas).

## 3. `GET/POST /api/v1/google/*` — autenticación real en los 9+1 endpoints

**Antes**: ningún endpoint de `google.py` tenía `Depends` de autenticación
— accesibles sin token por cualquiera.

**Después** (los 9 endpoints del hallazgo original + `/status`, probados
sin token):
```
GET  /api/v1/google/calendar/events  → 401
POST /api/v1/google/calendar/event   → 401
POST /api/v1/google/gmail/send       → 401
GET  /api/v1/google/gmail/inbox      → 401
POST /api/v1/google/drive/upload     → 401
GET  /api/v1/google/drive/files      → 401
POST /api/v1/google/sheets/create    → 401
POST /api/v1/google/sheets/write     → 401
POST /api/v1/google/sheets/read      → 401
GET  /api/v1/google/status           → 401
```
Los 10 endpoints exigen autenticación real.

**Veredicto: CERRADO.**

## 4. Heurística de onboarding — falso positivo de `setup_completed`

**Antes** (`AUDITORIA_TOTAL_FINAL.md`, sección 4, reproducido en vivo por
el revisor independiente): registro nuevo (`business_type=restaurant`) →
`GET /onboarding/status` inmediato da `setup_completed:true`,
`setup_inferred:true`, pese a `questionnaire_completed:false` y
`operational_profile_completed:false` — el usuario nunca respondió nada,
pero el sistema ya lo consideraba "configurado" porque el propio registro
auto-siembra productos TPV y un empleado placeholder.

**Después** (esta rama consolidada, registro 100% nuevo en esta sesión de
cierre, `final.onboard@gmail.com`, `business_type=restaurant`):
```
GET /api/v1/auth/onboarding/status  (inmediatamente tras registro)
→ {"checks": {"tpv_products": 4, "has_tpv_profile": true,
              "company_employees_count": 1, ...},
   "questionnaire_completed": false,
   "operational_profile_completed": false,
   "setup_completed": false,
   "setup_inferred": false}
```
Mismas señales que antes disparaban el falso positivo (4 productos TPV,
perfil TPV activo, 1 empleado) — ahora correctamente excluidas del cálculo
porque son auto-generadas por el registro, no evidencia real de onboarding
completado. El falso positivo inmediato **ya no ocurre**.

**Matiz que impide cerrar el hallazgo al 100%** (documentado también en el
paso 7 de este informe, con su propia auditoría independiente en
`AUDIT_FIX_ONBOARDING_WIZARD.md`): completar el cuestionario DE VERDAD vía
`POST /api/v1/auth/onboarding/questionnaire` sigue dando **500** por un bug
de doble sesión SQLAlchemy preexistente y ya documentado (`db.add(user)`
sobre un `User` adjunto a otra sesión — mismo patrón que el ya corregido en
`update-advisor-emails`/`toggle-authorization`, pero no aplicado aquí),
confirmado de nuevo ahora mismo en esta rama consolidada:
```
POST /api/v1/auth/onboarding/questionnaire  (employees_count/uses_tpv/business_hours completos)
→ 500 {"detail":"Error interno del servidor. El servicio sigue activo; reintenta."}
```
Es decir: el bloqueo original (falso positivo inmediato que impedía siquiera
plantearse completar el cuestionario) está resuelto, pero el camino "feliz"
de completarlo de verdad todavía no funciona por un bug distinto,
preexistente y fuera del alcance de la tarea que se pidió corregir en
`feature/fix-onboarding-wizard-real` (su propia auditoría lo señala
explícitamente como pendiente para una tarea nueva, no como motivo de
devolución de esa tarea).

**Veredicto (antes de la sección 5): PARCIALMENTE CERRADO.** El hallazgo
original exacto (falso positivo inmediato, bloqueaba el acceso al
cuestionario manual mostrando la cuenta como "ya configurada") estaba
cerrado. Quedaba abierto un hallazgo distinto y ya documentado (bug de
doble sesión en el endpoint del cuestionario) que impedía validar
end-to-end el camino de completar el onboarding manualmente vía API. **Ver
sección 5 más abajo: este segundo hallazgo ya está corregido y verificado
— veredicto final actualizado a CERRADO.**

---

## 5. Fix del hallazgo 4 (segunda parte) — 500 en `POST /onboarding/questionnaire`

**Causa raíz exacta** (mismo patrón de doble sesión SQLAlchemy ya
diagnosticado y corregido para `document_approval.py` en `ca2e7fe`, y ya
señalado como pendiente en la sección 4 de arriba y en
`AUDIT_FIX_ONBOARDING_WIZARD.md`): `current_user`, inyectado por
`get_current_active_user` (que usa `app.db.base.get_db`), pertenece a una
sesión SQLAlchemy distinta de la `db: Session = Depends(get_db)`
(`app.db.session.get_db`) propia del endpoint. Dos puntos concretos
mutaban ese objeto y luego lo pasaban a `db`:

- `backend/services/onboarding_engine.py:407` (antes del fix, ahora
  desplazado tras el re-fetch) — `apply_questionnaire_answers()` hacía
  `user.employees = body.employees_count`, `user.tpv_config = ...` y
  `db.add(user)` sobre el `user` recibido tal cual, sin re-obtenerlo de
  `db`. `db.add()` sobre un objeto ya adjunto a *otra* sesión lanza
  `sqlalchemy.exc.InvalidRequestError` inmediatamente.
- `backend/app/api/v1/endpoints/auth.py` (bloque fallback de
  `onboarding_questionnaire`, antigua línea 513) — repetía exactamente el
  mismo patrón sobre `current_user`. Al no estar esa línea protegida por
  ningún `try/except` propio (solo el `db.commit()` posterior lo estaba) y
  al ser el segundo/tercer `except` del mismo `try` código muerto
  (`except Exception` ya había capturado todo antes), la excepción escapaba
  sin control hasta el middleware `uncaught_exception_guard`
  (`backend/app/main.py:116-128`), que la convertía en el 500 genérico
  observado: `{"detail":"Error interno del servidor. El servicio sigue
  activo; reintenta."}`.

**Fix aplicado** (mismo patrón exacto que `ca2e7fe`, sin inventar uno
nuevo): re-obtener el `User` a través de la propia sesión `db` antes de
mutarlo, en los dos sitios donde ocurre la causa raíz:

- `backend/services/onboarding_engine.py:385` (dentro de
  `apply_questionnaire_answers`):
  `user = db.query(User).filter(User.id == user.id).first() or user`
- `backend/app/api/v1/endpoints/auth.py:504` (dentro del bloque fallback de
  `onboarding_questionnaire`):
  `current_user = db.query(User).filter(User.id == current_user.id).first() or current_user`

No se tocó `app/core/auth.py` ni `app/db/base.py` — la unificación de raíz
de `get_current_user` sigue pendiente como decisión de mayor alcance (igual
que se señaló en `ca2e7fe`), fuera del alcance de este fix puntual.

**Verificado en vivo, antes y después del fix, en esta misma rama
(`feature/consolidacion-final`), backend propio en SQLite
(`backend/zeus.db`, recreado en cada arranque vía `create_tables()`),
venv compartido:**

Antes del fix (`git stash` temporal para reproducir el estado sin el
parche), registro 100% nuevo (`preonb_1787821718@example.com`), login,
`POST /auth/onboarding/questionnaire` con los tres campos exigidos por el
schema (`employees_count`, `uses_tpv`, `business_hours`):
```
HTTP 500
{"detail":"Error interno del servidor. El servicio sigue activo; reintenta."}
```

Después del fix, registro 100% nuevo distinto
(`postonb_1787821846@example.com`):
```
POST /api/v1/auth/onboarding/questionnaire
→ HTTP 200
{"success":true,"company_id":2,"message":"Cuestionario guardado correctamente",
 "fallback_mode":false,"warnings":[]}

GET /api/v1/auth/onboarding/status  (llamada independiente, inmediatamente después)
→ HTTP 200
{"questionnaire_completed":true, "setup_completed":true,
 "existing_questionnaire":{"employees_count":3,"uses_tpv":true,
   "business_hours":"L-V 9:00-18:00","completed_at":"2026-08-27T09:10:59..."}}
```
`fallback_mode:false` confirma que el fix corrige la ruta *principal*
(`apply_questionnaire_answers`), no solo el fallback — antes del fix, ambas
rutas fallaban en cascada (la primaria lanzaba `InvalidRequestError`, caía
al fallback, que repetía el mismo error sin protección).

Casos de error controlados (sin regresión de auth):
```
POST sin token                              → 401 "No se pudieron validar las credenciales"
POST con body incompleto (falta business_hours) → 422 (validación Pydantic, no 500)
```

**Aislamiento multi-tenant**, verificado con un segundo tenant nuevo
(`postonb2_1787821880@example.com`, `business_type=retail`):
```
POST /onboarding/questionnaire (tenant2, employees_count=7, uses_tpv=false,
  business_hours="L-D 8:00-20:00") → 200
GET /onboarding/status (tenant2) → questionnaire_completed:true,
  existing_questionnaire con SUS propios valores (7, false, "L-D 8:00-20:00")
```
Confirmado además por **SQL directo** sobre `zeus.db`: `users.employees` =
3 para el usuario del tenant 1 y 7 para el del tenant 2;
`users.tpv_config` con `tables_enabled`/`products_enabled` en `true`/`false`
respectivamente; `companies.metadata` con un `onboarding_questionnaire`
completo e independiente por empresa (id 2 vs id 3) — ningún tenant
sobreescribe ni ve los datos del otro.

**Regresión — suite completa** (`pytest tests -q`, venv compartido):
antes de este fix (documentado en la sección de cierre de arriba y en el
resumen ejecutivo): `7 failed, 288 passed, 1 xfailed, 3 errors`. Después
del fix: **`7 failed, 289 passed, 3 errors`** — mismos 7 fallos
preexistentes (mismos nombres, no relacionados: flags de
simulación de THALOS/JUSTICIA, `test_config_loading`, `test_audit_includes_ai_modules`),
mismos 3 errores preexistentes (`TestClient` no importado en
`test_app.py`), **sin regresiones**. El único cambio es que
`tests/test_onboarding_registration.py::test_questionnaire_endpoint_completes_and_flips_flag`
pasó de estar marcado `xfail(strict=False)` (documentando este mismo bug
como conocido) a pasar limpiamente de verdad — se retiró el marcador
`@pytest.mark.xfail` de ese test en este mismo commit, ya que mantenerlo
habría dejado una anotación de "bug conocido" incorrecta en el código tras
corregirlo.

**Qué no se pudo verificar**: el comportamiento contra PostgreSQL real (RLS
de multi-tenant) — este entorno solo tiene SQLite disponible, igual que el
resto de esta consolidación (ver nota de RLS en el resumen ejecutivo).

**Veredicto actualizado del hallazgo 4: CERRADO.** Tanto el falso positivo
original de `setup_completed` como el 500 de doble sesión en
`POST /onboarding/questionnaire` están corregidos y verificados end-to-end
con curl real, dos tenants nuevos y SQL directo. No me declaro a mí mismo
"listo para producción" — corresponde a `revisor-independiente` confirmar
esto de forma independiente antes de considerar la consolidación cerrada.

---

# Resumen ejecutivo de la consolidación

**12 ramas fusionadas** en `feature/consolidacion-final` (partiendo de
`main`@`97b949a`), en el orden especificado, con verificación real
(curl/SQL, no solo lectura de código) después de cada una:

1. `fix-seguridad-critica` — fast-forward, sin conflictos.
2. `multi-tenant-bd` — 1 conflicto (metrics.py, se quedó la versión RLS).
3. `limpieza-simulacion` — sin conflictos.
4. `envio-gestoria` — 3 conflictos (bug JWT/enum ya resuelto por el paso 2,
   consolidado en una sola versión).
5. `hallazgos-visuales` — sin conflictos en backend; 1 conflicto de estilos
   en frontend (paso 7).
6. `checkout-publico-fix` — 6 conflictos + 1 colisión de migración Alembic
   corregida (0043→0048).
7. `fix-onboarding-wizard-real` (841 commits, trae como ancestros
   `facturacion-tpv-real`/`onboarding-facturacion`/`rediseno-completo`) — 3
   conflictos + 3 colisiones de migración corregidas (→0049-0051).
8. `fix-thalos-shield-real` (7 vueltas de auditoría) — 4 conflictos + 2
   colisiones de migración corregidas (→0052-0053) + 2 ficheros de test
   rotos por depender de código muerto (uno eliminado, otro editado).
9-12. `vertical-seguros`, `facturacion-tpv-real`, `onboarding-facturacion`,
   `rediseno-completo` — confirmados como no-ops (ya ancestros vía el
   paso 7), sin cambios.

**Migraciones Alembic**: la cadena final tiene **53 revisiones, una sola
cabeza (`0053`), cero IDs duplicados** — se encontraron y corrigieron
**3 colisiones distintas de numeración** (6 pares de ficheros con el mismo
`revision` generados por ramas paralelas que nunca se vieron entre sí),
todas renumeradas preservando la lógica original y documentando el motivo
del cambio en cada docstring.

**Estado final de la suite de tests** (backend, SQLite local, tras la
sección 5 — fix del 500 de doble sesión en `/onboarding/questionnaire`):
```
7 failed, 289 passed, 3 errors
```
Frente al baseline inicial (`7 failed, 214 passed, 2 skipped, 3 errors`):
+75 tests pasando netos, mismos 7 fallos preexistentes (mismos nombres en
todo momento), mismos 3 errores preexistentes (`TestClient` no importado en
`test_app.py`). El `xfail` que documentaba el bug de doble sesión del
onboarding (hallazgo 4) se retiró en la sección 5 al corregirse ese bug de
raíz — el test pasa limpiamente ahora. **Ninguna regresión real en ningún
punto de la consolidación** — cada vez que apareció un fallo nuevo se
investigó su causa (dos veces fue higiene del entorno de pruebas: datos de
un esquema de enum anterior en el `zeus.db` compartido, y en otra un
proceso de otro agente ocupando el mismo puerto — ninguna de las dos era
una regresión real de código).

**Multi-tenant**: verificado explícitamente con dos tenants reales en cada
paso relevante (dashboard, invoices, products, customers, agents/status) —
en todos los casos un tenant no ve datos del otro, confirmado con curl real
y, donde hizo falta, con SQL directo sobre la base de datos.

**RLS de Postgres**: implementado (multi-tenant-bd + fix-thalos-shield-real,
diseño fail-open coherente en ambos) pero **no verificable en este
entorno** — solo hay SQLite disponible aquí, ambas ramas lo documentan
honestamente como pendiente de verificación contra un Postgres real antes
de confiar en ello en producción.

**Veredicto sobre los 4 hallazgos críticos**: **4 de 4 cerrados por
completo** (`metrics/dashboard`, `invoices/products/customers`, `google.py`,
y heurística de onboarding — este último en dos partes: el falso positivo
original de `setup_completed`, cerrado en la sección 4, y el 500 de doble
sesión SQLAlchemy en `POST /onboarding/questionnaire` que ese cierre
descubrió como hallazgo nuevo, corregido y verificado end-to-end en la
sección 5).

**No me declaro "listo para producción"** — esto lo decide el usuario, y
corresponde a una revisión independiente antes de tocar `main`. No se ha
hecho ningún merge a `main` ni ningún push en ningún momento de esta
consolidación.
