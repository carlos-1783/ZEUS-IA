# AUDIT_FIX_ONBOARDING_WIZARD.md

Ejecutor: ejecutor-produccion
Rama: `feature/fix-onboarding-wizard-real` (creada desde `feature/rediseno-completo` @ `35b0d8e`, repo `C:\Users\Acer\ZEUS-IA`)
Tarea origen: hallazgo confirmado dos veces en `AUDIT_FINAL_COMPLETA.md` secciones 1.2 y 6.1 — el wizard de onboarding nunca se activa para ningún registro estándar.

## 1. Causa raíz confirmada

`backend/app/api/v1/endpoints/auth.py::onboarding_status` (heurística de respaldo, líneas ~594-628 antes del fix) declaraba `setup_completed=True` (con `setup_inferred=True`) en cuanto detectaba:

- `ce_count >= 1` — pero **todo registro nuevo, para cualquier `business_type`**, crea automáticamente en la misma transacción un `CompanyEmployee` placeholder "owner" (`employee_code=f"U{user.id}-OWNER"`, `source="onboarding_owner"`) vía `onboarding_engine.py::_create_owner_employee_and_default_schedules`. Por tanto `ce_count` era `>= 1` desde el instante cero, siempre.
- `tpv_products >= 1 and current_user.tpv_business_profile` — el mismo registro también crea automáticamente entre 1 y 4 productos de catálogo por defecto vía `onboarding_engine.py::_seed_tpv_products` (y en el flujo de alta post-pago, `global_company_bootstrap.py::_ensure_hospitality_products`), y fija `user.tpv_business_profile`. Esta segunda condición **también era siempre verdadera** desde el registro, para los tres `business_type` (`restaurant`, `retail`, `services`), independientemente de la primera.

Es decir: había **dos** condiciones de la heurística, no una, que devolvían falso positivo desde el registro. Arreglar solo `ce_count` (como sugería la descripción original del hallazgo) no habría sido suficiente — el wizard habría seguido sin activarse nunca por la vía de `tpv_products`.

## 2. Investigación de por qué existía la heurística de respaldo (paso obligatorio antes de tocarla)

La heurística se añadió en el commit `6342457` ("fix(onboarding): skip wizard for pilot companies with existing data", 2026-06-12) para no forzar el wizard en empresas piloto/antiguas que ya tenían datos reales sembrados manualmente (`pilot_company=True`, o filas de `company_employees`/`tpv_products` insertadas por scripts como `apply_pilot_company_data.py`). En ese momento **ya existía** el seed automático del owner-placeholder (introducido en `af319194`, 2026-04-06, más de dos meses antes) — por lo que la heurística de "ce_count>=1" nunca fue una señal fiable ni siquiera cuando se escribió: nació ya rota para cualquier alta estándar. No es una regresión reciente, es un defecto de diseño desde el origen del commit que la introdujo.

Conclusión: la heurística de respaldo en sí (Opción 2 del encargo) **sigue siendo necesaria** — hay datos reales de empresas piloto/antiguas que no pasaron por el cuestionario nuevo y deben seguir infiriendo `setup_completed=True`. Eliminarla por completo habría roto esos casos legítimos. Se descarta la Opción 2.

## 3. Fix aplicado (Opción 1, ampliada al TPV)

Archivo: `backend/app/api/v1/endpoints/auth.py`, función `onboarding_status`.

- `ce_count`: en vez de `COUNT(*)` sobre todos los `CompanyEmployee` de la empresa, se cuenta solo los que **no** tienen `source == "onboarding_owner"` (el placeholder). Las filas legítimas (`source="onboarding_profile"` del wizard real, `source="afrodita_rrhh_v1"` de AFRODITA, `source="pilot_seed_json"` de scripts de alta de pilotos, o `source=NULL` de filas antiguas anteriores a que existiera la columna) siguen contando.
- `tpv_products`: se excluyen del conteo los productos con `metadata_.auto_created == True` (la plantilla de catálogo por defecto sembrada por `_seed_tpv_products` / `_ensure_hospitality_products`). Productos añadidos de verdad por el usuario vía `POST /tpv/products` (que no marca `auto_created`) sí cuentan.
- `pilot_company` y `has_profile_data` no se tocan — siguen siendo señales legítimas sin cambios.

Por qué esta opción y no la 2: preserva el comportamiento correcto para cuentas piloto/antiguas con datos reales (verificado en el punto 5), es un cambio quirúrgico de una sola función/endpoint, y usa columnas (`source`, `metadata_.auto_created`) que **ya existían y ya se poblaban** en el código — no requiere migración Alembic nueva.

Diff completo: `git diff 35b0d8e..HEAD -- backend/app/api/v1/endpoints/auth.py`.

## 4. Reproducción del bug ANTES del fix (curl real, servidor local, sqlite `backend/zeus.db`)

Servidor: `venv` compartido, `uvicorn app.main:app --host 127.0.0.1 --port 8123`, código en `35b0d8e` (sin el fix).

```
POST /api/v1/auth/register  {"email":"onbbug003@example.com", ..., "business_type":"restaurant"}
→ 201 {"user_id":51,"company_id":31,...}

POST /api/v1/auth/login  username=onbbug003@example.com
→ 200 access_token=...

GET /api/v1/auth/onboarding/status  (Bearer token)
→ 200 {
    "questionnaire_completed": false,
    "operational_profile_completed": false,
    "setup_completed": true,      <-- FALSO POSITIVO
    "setup_inferred": true,
    "validation": {"checks": {"tpv_products": 4, "company_employees_count": 1, ...}}
  }
```

Confirmado: el usuario nunca vio el cuestionario ni el perfil, y aun así `setup_completed=true`. Coincide exactamente con el hallazgo de `AUDIT_FINAL_COMPLETA.md`.

## 5. Verificación DESPUÉS del fix (mismo servidor, código con el fix, cuentas nuevas)

a) **Restaurant, justo tras registro** (`onbfix001@example.com`, company_id=29):
`setup_completed:false, setup_inferred:false, tpv_products:4, company_employees_count:1` — correcto.

b) **Services, justo tras registro** (`onbfix002@example.com`, company_id=30):
`setup_completed:false, setup_inferred:false, tpv_products:1, company_employees_count:1` — correcto (confirma que el fix cubre los dos `business_type` mencionados en el hallazgo).

c) **Misma cuenta que en el punto 4 (`onbbug003`, company_id=31), releída con el fix, sin tocar los datos**:
`setup_completed:false, setup_inferred:false` — mismo dato, distinto resultado según el código, confirma que el fix es la causa del cambio (no un efecto de datos distintos).

d) **Completar de verdad el proceso** (`onbfix001`, vía `POST /onboarding/profile` con empleado real, horario y `email_gestor_fiscal`):
`setup_completed:true, setup_inferred:false, questionnaire_completed:true, operational_profile_completed:true, rafael_email_ready:true` — el wizard real sí lo marca `true`, y no por inferencia sino por completitud real.

e) **No-regresión — empresa marcada `pilot_company=true`** (`onbbug003`/company_id=31, tras marcarla piloto):
`setup_completed:true, setup_inferred:true, pilot_company:true` — sigue funcionando sin pasar por cuestionario, como se diseñó.

f) **No-regresión — empresa con un empleado REAL preexistente (no el placeholder)**, simulando una cuenta antigua/pilota con datos reales pero `source=NULL` (fila anterior a que existiera la columna `source`), sobre `onbfix002`/company_id=30:
`setup_completed:true, setup_inferred:true, questionnaire_completed:false` — la heurística de respaldo sigue protegiendo el caso legítimo que motivó su creación en el commit `6342457`.

g) **Multi-tenant**: cada consulta a `/onboarding/status` deriva la empresa exclusivamente del `UserCompany` del propio `current_user` (no hay parámetro de tenant en la URL ni en el body). Los tres tenants de prueba (company_id 29, 30, 31) devolvieron siempre sus propios datos (`company_name`, conteos, banderas) sin cruce entre ellos — no hay vector de fuga entre empresas en este endpoint ni en el fix (el fix no añade ninguna query nueva sin filtrar por `company_id`/`user_id`, solo cambia el criterio de conteo dentro del mismo `company_id`/`user_id` ya usado).

## 6. Tests automatizados añadidos

Archivo: `backend/tests/test_onboarding_registration.py`.

- Se corrigió el dominio de email de prueba (`example.test` → `example.com`) en `_register_payload` y en `email_gestor_fiscal` del test de perfil: `example.test`/`.local` son dominios reservados que el validador de pydantic (`EmailStr`) rechaza, por lo que **los dos tests existentes de este archivo se saltaban en silencio (`pytest.skip`) y nunca llegaban a ejecutar un registro real** — el propio archivo de test tenía un defecto que ocultaba la cobertura real del bug.
- `test_register_restaurant_creates_user_company_and_login`: añadida aserción explícita `setup_completed is False` y `setup_inferred is False` justo tras el registro (antes solo comprobaba `questionnaire_completed`).
- Nuevo `test_owner_placeholder_alone_does_not_infer_setup_completed`: repro directa del hallazgo (registro → status → `setup_completed` debe ser `False` con placeholder+producto auto-creado presentes).
- Nuevo `test_real_employee_without_questionnaire_still_infers_setup_completed`: no-regresión — inserta un `CompanyEmployee` real (`source=None`) directamente en BD y confirma que `setup_completed` sigue infiriéndose `True` sin cuestionario.
- `test_questionnaire_endpoint_completes_and_flips_flag` (antes parte de `test_register_restaurant_creates_user_company_and_login`): se separó en un test propio marcado `@pytest.mark.xfail` porque, al arreglar el dominio de email y ejecutarse por primera vez de verdad, expuso un bug preexistente y no relacionado con este fix (ver sección 7). Separarlo evita que un hallazgo fuera de alcance oculte o bloquee la cobertura del fix real de esta tarea.

## 7. Hallazgo NUEVO descubierto (fuera de alcance de esta tarea, no corregido aquí)

`POST /api/v1/auth/onboarding/questionnaire` devuelve **500** incluso en un registro+login recién creados, en este entorno de pruebas:

```
sqlalchemy.exc.InvalidRequestError: Object '<User at ...>' is already attached to session 'N' (this is 'N-1')
```

Traza: `onboarding_engine.py::apply_questionnaire_answers` línea 417 (`db.add(user)`) falla porque `current_user` fue cargado por `get_current_active_user` usando `app.core.auth.get_current_user` → `app.db.base.get_db` (sesión A), mientras que el endpoint `onboarding_questionnaire` recibe su propio `db` inyectado desde `app.db.session.get_db` (sesión B, distinta). El `except` de `auth.py::onboarding_questionnaire` (línea 513, `db.add(current_user)`) repite el mismo error sin capturarlo, y el endpoint responde 500 sin control.

Esto es **exactamente el mismo patrón de causa raíz** que el commit `ca2e7fe` (ya en la base de esta rama) corrigió para `update-advisor-emails`/`toggle-authorization`: dos `get_db` distintos (`app.db.base` vs `app.db.session`) conviviendo en el código, sin unificar. El propio mensaje de commit de `ca2e7fe` ya advertía: *"unificar ahí el get_db compartido queda documentado como pendiente de mayor alcance, fuera de esta auditoría"*. Este hallazgo confirma que el problema de fondo sigue latente y afecta como mínimo también a `onboarding_questionnaire`.

Impacto: la vía de finalización real del wizard por `/onboarding/questionnaire` está rota (devuelve 500) para una cuenta recién registrada. La vía alternativa `/onboarding/profile` (que sí actualiza `operational_profile_completed`/`questionnaire_completed` y no pasa por el mismo camino de código) **sí funciona** — fue la que usé para verificar el punto 5.d de este informe. Por tanto el wizard SÍ puede completarse de verdad hoy (vía `/onboarding/profile`), pero el endpoint específico `/onboarding/questionnaire` necesita el mismo tipo de fix que `ca2e7fe`.

No se corrigió aquí porque:
- Es un bug distinto, en una ruta distinta, no relacionado con la heurística `setup_completed` que era el encargo de esta tarea.
- Mezclar ambos arreglos en el mismo commit violaría la regla de "un cambio, una rama, un commit atómico" de la skill `zeus-produccion`.

Recomendación: nueva tarea para `ejecutor-produccion` — aplicar a `onboarding_questionnaire`/`apply_questionnaire_answers` el mismo patrón de re-fetch de `current_user` en la sesión `db` propia del endpoint que ya se usó en `ca2e7fe`, o (mejor, de mayor alcance) unificar `app.db.base.get_db` y `app.db.session.get_db` en un único proveedor de sesión para todo el backend.

## 8. Regresión — suite de tests backend

Baseline (código sin el fix, mismo venv compartido, `pytest tests -q`):
```
7 failed, 214 passed, 2 skipped, 3 errors  (107.14s)
```
Fallos: `test_config_loading`, `test_default_flags_simulated`, `test_audit_includes_ai_modules`, `test_default_mode_is_simulation_for_heuristic_modules`, `test_backup_requires_execution_and_backup_flags`, `test_build_metadata_origin_mock`, `test_monitoring_cycle_respects_flags`. Errores: 3× `test_app.py` (`NameError: TestClient`). Todos preexistentes y no relacionados con onboarding.

Con el fix aplicado (antes de tocar el archivo de tests): mismo resultado exacto, `7 failed, 214 passed, 2 skipped, 3 errors` (148.64s) — el fix del endpoint por sí solo no cambia ningún resultado de la suite existente.

Con el fix + los tests nuevos/corregidos de `test_onboarding_registration.py` (`pytest tests -q`, corrida completa final):
```
7 failed, 218 passed, 1 xfailed, 35 warnings, 3 errors  (281.35s)
```
Mismos 7 tests fallando que en el baseline (`test_config_loading`, `test_default_flags_simulated`, `test_audit_includes_ai_modules`, `test_default_mode_is_simulation_for_heuristic_modules`, `test_backup_requires_execution_and_backup_flags`, `test_build_metadata_origin_mock`, `test_monitoring_cycle_respects_flags`) y mismos 3 errores (`test_app.py`, `NameError: TestClient`) — ninguno relacionado con onboarding, ninguno nuevo. `passed` sube de 214 a 218 (+4: los 2 tests que antes se saltaban en silencio ahora se ejecutan de verdad y pasan, más 2 tests nuevos de este fix). `skipped` baja de 2 a 0. Aparece `1 xfailed` (el hallazgo de la sección 7, documentado, no cuenta como fallo). **Ninguna prueba que antes pasaba ahora falla: no hay regresión.**

## 9. Qué NO se pudo verificar

- No hay entorno de staging/producción real (Railway) accesible desde este agente; toda la verificación es contra `sqlite:///./zeus.db` local (venv compartido), que es el mismo comportamiento por defecto que usa la suite de tests del repo.
- No se probó el flujo de alta post-pago/Stripe (`POST /onboarding/create-account` → `global_company_bootstrap.py`) de extremo a extremo con un webhook de Stripe real (requiere credenciales de Stripe de prueba no disponibles en este entorno). Se revisó el código estáticamente: ese endpoint no crea `CompanyEmployee`, por lo que el fix de `ce_count` no le afecta; si crea productos "auto_created" en negocios `hospitality`, y esos también quedan correctamente excluidos por el fix de `tpv_products` aplicado en `onboarding_status` (la exclusión es genérica por `metadata_.auto_created`, no específica de `onboarding_engine.py`).
- No se disparó el envío real de email a RAFAEL/gestor fiscal (SendGrid devolvió 401 en este entorno — credenciales de prueba no configuradas, visible en el log del servidor); no es parte del alcance de esta tarea.

## 10. Pendiente

- Hallazgo de la sección 7 (bug de doble sesión en `/onboarding/questionnaire`) — pendiente de nueva tarea, no corregido en esta rama.
- Confirmar con el usuario si procede además desactivar/parametrizar el seed automático del `CompanyEmployee` "owner" y el producto de catálogo por defecto en el registro (hoy siguen creándose siempre; este fix solo corrige que dejen de contar como señal de "wizard completado", no elimina el propio seed, que sigue siendo intencional para tener el dashboard operativo desde el primer minuto).
