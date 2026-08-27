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
