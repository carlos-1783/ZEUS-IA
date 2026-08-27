# AUDIT_JUSTICIA_ESTADO_FINAL.md

Auditoría completa de JUSTICIA (todos los endpoints REST + servicios internos +
ruta de automatización/workflows), en respuesta al hallazgo histórico
"toolkit legal = stub" (`references/agentes.md` de la skill `zeus-produccion`)
y a la confirmación previa (`AUDITORIA_TOTAL_FINAL.md`, sección 1, fila
JUSTICIA) de que `POST /api/v1/justice/contracts/generate` ejecuta lógica
real.

- Rama: `feature/consolidacion-final`
- Punto de partida: commit `bd0ca34`
- Verificación: código leído línea a línea + pruebas reales con `curl` contra
  un servidor Uvicorn local (SQLite aislado, dos tenants reales creados vía
  `POST /api/v1/auth/register`) + suite `pytest`.

## 1. Endpoints REST de JUSTICIA — inventario completo

| Endpoint | Archivo:línea | Lógica real (antes) | Veredicto | Evidencia |
|---|---|---|---|---|
| `GET /api/v1/justice/status` | `justice.py:42-49` → `justice_audit_service.audit_status` | Real (BD), pero exponía `compliance_events` (count global sin tenant) a cualquier usuario | ✅ REAL — ❌→✅ **fuga multi-tenant corregida en este commit** | curl: tenant B veía `compliance_events:2` generados por tenant A antes del fix; tras el fix, `compliance_events:null` + `compliance_events_note` para no-superusuario, valor real solo para superusuario |
| `GET /api/v1/justice/audit` | `justice.py:52-61` → `justice_audit_service.run_real_audit` | Real (sync cross-agent + GDPR + counts), mismo problema de `compliance_events_count` | ✅ REAL — ❌→✅ **misma fuga corregida** | curl con superusuario: `compliance_events_count:4` real; con usuario normal: `null` + nota |
| `GET /api/v1/justice/documents` | `justice.py:64-78` → `justice_audit_service.list_documents` | Real, filtra `LegalDocument.user_id == user.id` | ✅ REAL, aislado | curl: tenant A ve 1 documento propio; tenant B ve `{"documents":[],"count":0}` |
| `GET /api/v1/justice/documents/{id}` | `justice.py:81-96` → `get_document` | Real, filtra por `user_id` + `public_id` | ✅ REAL, aislado | curl: tenant B pidiendo el `document_id` real de tenant A → `404 document_not_found` |
| `POST /api/v1/justice/sign` | `justice.py:99-114` → `signature_service.apply_signature` | Real: SHA256 compuesto, persiste `signature_hash`/`signer_id`/`signed_at`, cambia `status` a `approved` | ✅ REAL | curl: firmó el contrato generado, `db.status` pasó de `draft` a `approved` (confirmado en `GET /documents` posterior) |
| `POST /api/v1/justice/contracts/generate` | `justice.py:117-131` → `contract_generator.generate_contract` | Real: plantilla renderizada, persistida en `legal_documents` con `db_id` | ✅ REAL (ya confirmado en auditoría previa, re-confirmado aquí) | curl: `db_id:1`, contenido markdown real con partes/alcance del request |
| `POST /api/v1/justice/gdpr` | `justice.py:134-142` → `gdpr_engine.run_gdpr_check` | Real: crea `ComplianceEvent` reales según estado de BD del usuario (consentimiento, retención, exposición) | ✅ REAL | curl: `alerts_created:2`, `alert_ids` reales devueltos |
| `GET /api/v1/justice/compliance-events` | `justice.py:145-173` | Real, pero ya gateado a superusuario desde una vuelta previa de auditoría (`AUDIT_THALOS_ESTRUCTURAL.md` sección 3, `test_thalos_v6_estructural_v1.py`) porque `ComplianceEvent` no tiene `company_id` | ✅ REAL + ya mitigado (no tocado en este commit) | curl: usuario normal → `403` con el mensaje de mitigación explícito; test existente `test_justicia_compliance_events_rejects_normal_user` sigue en verde |
| `GET /api/v1/justicia/v1/status` | `justicia_v1.py:20-24` → `justicia_control_layer_v1.global_status_payload` | Real: refleja flags reales de settings (`JUSTICE_REAL_AUDIT_ENABLED`, `JUSTICE_READ_ONLY_MODE`), no hardcodeado | ✅ REAL | curl: `system_default_mode:"REAL"` coincide con `JUSTICE_REAL_AUDIT_ENABLED=true` real de `app/core/config.py:301` |
| `GET /api/v1/justicia/v1/system-audit` | `justicia_v1.py:27-41` → `justice_system_audit_v1.run_system_audit` | Real, estructurado (RRHH/OPS/Workspace con verdicts y `audit_trace` de queries reales) | ✅ REAL — ⚠️ ver hallazgo pendiente D (conteos globales no-tenant en `products`/`inventory_movements`/`time_cost_checkins`) | curl: `audit_trace` con `COUNT(*)` reales, `domain_verdicts` calculados de BD real, no fijos |
| `GET /api/v1/justicia/v1/documents` | `justicia_v1.py:44-59` | Real, mismo aislamiento que `/justice/documents` | ✅ REAL, aislado | Mismo código que el endpoint ya probado arriba |

## 2. Servicios internos que usa JUSTICIA

| Servicio | Veredicto | Detalle |
|---|---|---|
| `services/contract_generator.py` | ✅ REAL | Plantillas reales, persiste `LegalDocument`, versiona por usuario |
| `services/signature_service.py` | ✅ REAL | Hash SHA256 real, persiste firma y cambia estado del documento |
| `services/gdpr_engine.py` | ✅ REAL — ⚠️ hallazgo pendiente C | Chequeos reales de consentimiento/retención/exposición scopeados por `user_id`; el chequeo de PII en logs THALOS (líneas 98-111) consulta `ThalosEvent` SIN filtrar por tenant (cuenta global) |
| `services/justice_audit_service.py` | ✅ REAL — ❌→✅ fuga corregida en este commit | Ver hallazgo 1 (compliance_events count global) |
| `services/justice_system_audit_v1.py` | ✅ REAL — ⚠️ hallazgo pendiente D | `emp_count` SÍ se scopea por `company_ids` del usuario (línea 156-166); `prod_count`/`mov_count`/`checkin_count` (vía `_safe_count`) NO se scopean — inconsistencia dentro de la misma función |
| `services/justice_cross_agent_v1.py` | ✅ REAL, YA CORREGIDO en una vuelta previa | Comentario explícito en el código (líneas 44-62) documenta que ya se migró a filtrar `ThalosAlert` por `company_id` del usuario tras `AUDIT_THALOS_ESTRUCTURAL.md` paso 4; `except Exception: pass` silencioso en 4 bloques (líneas 79-80, 93-94, 113-114, 129-130) — swallowing sin log, ver hallazgo pendiente E |
| `services/justicia_control_layer_v1.py` | ✅ REAL | Metadata (`execution_mode`, `ui_badge`) calculada de flags reales de `settings`, no hardcodeada |
| `services/automation/handlers/justicia.py::handle_justicia_task` | ❌→✅ **CORREGIDO en este commit** | Ver sección 3 |

## 3. Hallazgo principal encontrado y corregido: stub vivo en la ruta de automatización

El endpoint REST (`/justice/contracts/generate`) ya era real, pero **existía
una segunda vía**, no cubierta por la auditoría previa, que seguía siendo un
stub puro: `services/automation/handlers/justicia.py::handle_justicia_task`.

Esta función es el handler real ejecutado por
`services/automation/agent_executor.py` (`AgentAutomationExecutor`, worker de
fondo) cuando `teamflow_engine.py` (motor de workflows en producción, no un
script de demo) dispara para JUSTICIA los pasos `document_reviewed` /
`compliance_check` / `task_assigned` — por ejemplo:
- `contract_sign_v1` → paso `gdpr_validation` (`compliance_check`)
- `invoice_flow_v1` → paso `legal_stamp` (`document_reviewed`, descrito como
  "Firmar digitalmente PDF y archivar en expediente legal", expected_output
  "PDF firmado + hash auditado")
- `pre_launch_v1` → paso `legal_review` (`document_reviewed`)

**Antes** (`git show bd0ca34:backend/services/automation/handlers/justicia.py`):
devolvía SIEMPRE el mismo texto fijo de política de privacidad y términos de
servicio (`_privacy_policy()`, `_terms_of_service()`), sin leer ni escribir
nada en base de datos, escribía a ficheros locales efímeros
(`storage/outputs/justicia/*.json`) — el problema conocido de persistencia en
Railway — y reportaba `"docs_generated": 3` fijo sin importar la actividad ni
el usuario. Exactamente el patrón "toolkit legal = stub" que la auditoría de
`contracts/generate` había dado por cerrado, pero que seguía vivo aquí.

**Corregido en este commit**: `handle_justicia_task` ahora:
1. Resuelve el usuario real de la actividad (`activity.user_email`/`user_id`).
2. Ejecuta `services.gdpr_engine.run_gdpr_check` real (persiste
   `ComplianceEvent` reales).
3. Lee documentos pendientes reales vía
   `services.justice_audit_service.list_pending_documents_grouped` /
   `list_documents`, scopeados al usuario.
4. Si el payload de la actividad trae `document_id`, aplica firma real
   (`services.signature_service.apply_signature`) — cubre parcialmente el
   caso "legal_stamp" de `invoice_flow_v1` cuando el motor de workflows
   propaga ese dato (ver hallazgo pendiente A: no verificado que lo haga
   siempre).
5. Si no puede resolver el usuario, falla explícito (`status: "failed"`,
   `real_execution: False`) — nunca simula éxito.

**Prueba real end-to-end** (no solo unit test): con el servidor corriendo,
se generó un contrato real con `tenanta.justicia@gmail.com`
(`db_id:1`, `document_id: b1e50bac-...`), se encoló una actividad real vía
`POST /api/v1/activities/log` (`agent_name:"JUSTICIA"`,
`action_type:"compliance_check"`, `activity_id:20`), y se invocó el handler
directamente contra esa actividad real:

```json
{
  "status": "completed",
  "details_update": {
    "automation": {
      "gdpr_issues": [{"type": "missing_consent", "message": "..."}],
      "pending_documents": {"total_pending": 0, ...},
      "recent_legal_documents": [
        {"id": "b1e50bac-...", "type": "contract", "status": "approved", ...}
      ],
      "signature": null, "signature_error": null,
      "summary": "Revisión legal real: 1 hallazgo(s) GDPR, 0 documento(s) pendiente(s) de aprobación."
    },
    "real_execution": true, "data_origin": "database"
  }
}
```

El handler encontró y devolvió el contrato REAL de ese usuario, no el texto
fijo de siempre — confirma que la corrección lee BD de verdad, scopeada por
usuario, no simula nada.

Tests nuevos: `backend/tests/test_justicia_automation_handler_real_v1.py` (5
tests: ya no hay boilerplate fijo, refleja documentos reales, falla honesto
sin usuario, firma real cuando hay `document_id`, reporta error de firma sin
crashear).

## 4. Hallazgo secundario encontrado y corregido: fuga multi-tenant en conteo agregado

`services/justice_audit_service.py::audit_status` y `::run_real_audit`
exponían `db.query(func.count(ComplianceEvent.id)).scalar()` — el conteo
GLOBAL de `compliance_events` de TODAS las empresas — a cualquier usuario
autenticado normal, vía `GET /api/v1/justice/status` y
`GET /api/v1/justice/audit`. `ComplianceEvent` no tiene `company_id` (tabla
deliberadamente global, según el propio comentario en
`services/justice_cross_agent_v1.py:44-62`), y el listado completo
(`GET /api/v1/justice/compliance-events`) ya estaba gateado a superusuario
por esa misma razón desde una vuelta previa de auditoría — pero el COUNT
agregado en `/status` y `/audit` se había quedado sin ese mismo gate.

**Confirmado empíricamente con dos tenants reales** (no solo lectura de
código): se generó un `POST /justice/gdpr` con `tenanta.justicia@gmail.com`
(creó 2 `ComplianceEvent` reales), y `tenantb.justicia@gmail.com` (tenant
distinto, sin ninguna actividad propia) veía `"compliance_events": 2` en su
propio `GET /justice/status` — es decir, un usuario podía inferir cuánta
actividad de cumplimiento tiene OTRA empresa en la plataforma.

**Corregido**: mismo criterio que el endpoint de listado ya gateado — el
conteo real solo se devuelve a superusuarios; para usuarios normales se
devuelve `null` + `compliance_events_note` explicando el motivo (nunca se
inventa un número falso ni se omite la explicación en silencio).

**Prueba real repetida tras el fix**: tenant B → `"compliance_events": null`
+ nota; el mismo usuario A promovido a superusuario (flip directo en BD para
la prueba) → `"compliance_events": 2` (status) / `4` (audit, tras un segundo
ciclo de sync) — el valor real solo aparece para quien tiene privilegio.

Tests nuevos:
`backend/tests/test_justicia_compliance_events_tenant_isolation_v1.py` (3
tests unitarios sobre `audit_status`/`run_real_audit`).

No se tocó `GET /api/v1/justice/compliance-events` (ya estaba correctamente
gateado) ni el modelo `ComplianceEvent` (añadirle `company_id` real requeriría
una migración Alembic + backfill, fuera del alcance mínimo de este fix).

## 5. Hallazgos NUEVOS documentados, NO corregidos en este commit (fuera de alcance)

Siguiendo la regla de no tocar silenciosamente algo fuera del alcance de la
tarea, estos quedan documentados para decisión explícita, no arreglados aquí:

**A. `invoice_flow_v1` → paso `legal_stamp` puede no firmar nunca de verdad.**
El paso usa `action_type="document_reviewed"` (→ `handle_justicia_task`) pero
su descripción/`expected_output` prometen "PDF firmado + hash auditado" — solo
firma de verdad si el payload de la actividad incluye `document_id` (mi fix
lo soporta de forma oportunista), y no se ha verificado que
`teamflow_engine.py` propague ese dato entre pasos dependientes en este
workflow. Requiere decisión: ¿cambiar el `action_type` de ese paso a
`document_signed` (el handler ya 100% real), o verificar/arreglar el
mecanismo de paso de `document_id` entre pasos del motor de workflows?
Archivo: `backend/services/teamflow_engine.py:152-160`.

**B. `SIMULATED_HANDLER_ACTIONS` (zeus_core_guard_v1.py:34-43) está
desactualizado, cruza varios agentes, no solo JUSTICIA.** Marca
`"contract_generator"`/`"invoice_sent"` como simulados aunque sus handlers
actuales (`handle_contract_generator`, `handle_invoice_sent`) ya son reales;
NO marca `"document_reviewed"`/`"compliance_check"` (antes 100% stub en
JUSTICIA) ni `"task_assigned"` (compartido por ZEUS/PERSEO/RAFAEL/JUSTICIA/
AFRODITA — confirmado que el handler genérico de RAFAEL,
`services/automation/handlers/rafael.py::handle_rafael_task`, es el mismo
patrón de plantilla fija que tenía JUSTICIA). Esta etiqueta solo se usa
cuando `ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED=true` (no activo por defecto), así
que hoy es de bajo impacto operativo, pero es información falsa si algún día
se activa esa capa de auditoría. Requiere una auditoría dedicada
cross-agente, fuera del alcance de esta tarea (solo JUSTICIA).

**C. `gdpr_engine.run_gdpr_check` — chequeo de PII en logs sin scope de
tenant.** Líneas 98-111: consulta `ThalosEvent` con `message ilike '%email%'`
SIN filtrar por `company_id`, aunque `ThalosEvent.company_id` ya existe en el
modelo (nullable a propósito). Severidad baja — no se expone contenido ni
conteo en la respuesta, solo dispara un flag booleano-ish si CUALQUIER
tenant tiene logs recientes con "email" — pero es inconsistente con el
resto del propio archivo, que sí scopea todo lo demás por `user.id`. Arreglo
trivial (filtrar por `company_id` del usuario, mismo patrón que
`justice_system_audit_v1.py` usa para `company_employees`), no aplicado aquí
para no mezclar un segundo hallazgo de aislamiento en el mismo commit sin
pruebas dedicadas.

**D. `justice_system_audit_v1.run_system_audit` — conteos globales
inconsistentes dentro de la misma función.** `emp_count` (RRHH) SÍ se scopea
por `company_ids` del usuario (líneas 156-166); `prod_count`/`mov_count`
(OPS, vía `_safe_count`, líneas 222-241) y `checkin_count` (líneas 189-199)
NO se scopean — cuentan productos/movimientos/fichajes de TODAS las
empresas. Expone volumen de negocio de otras empresas (aunque solo como
número agregado, sin detalle) a cualquier usuario autenticado que llame
`/justicia/v1/system-audit` o `/justice/audit`. Requiere decisión de producto:
¿este "system audit" debe ser per-tenant (como el resto de JUSTICIA) o es
intencionalmente una herramienta de diagnóstico de plataforma que debería
en su lugar gatearse a superusuario (como se hizo con
`compliance-events`)? No corregido aquí porque toca el dominio AFRODITA/ERP,
no solo JUSTICIA, y cualquiera de las dos soluciones cambia el contrato de
la respuesta.

**E. `except Exception: pass` silencioso en `justice_cross_agent_v1.py`**
(líneas 79-80, 93-94, 113-114, 129-130). No relanza, no registra log — un
fallo real en la sincronización de ThalosAlert/CompanyEmployee/PerseoJob/
Expense queda invisible. Bajo impacto (la función ya es best-effort por
diseño, y `sync_cross_agent_events` no es la única fuente de verdad), pero
no cumple estrictamente el punto del checklist "manejo de errores real, no
`try/except: pass`". No corregido aquí para no mezclar con los dos fixes
principales de este commit.

## 6. Veredicto sobre el hallazgo histórico "toolkit legal = stub"

**Parcialmente cerrado antes de esta sesión** (solo confirmado en la capa
REST directa, `POST /api/v1/justice/contracts/generate`). **Cerrado del todo
en esta sesión** para las DOS vías de ejecución de JUSTICIA que existen en el
código:

1. La vía REST directa (`justice.py`/`justicia_v1.py`) — ya era 100% real,
   re-confirmada aquí endpoint por endpoint con `curl` contra un servidor
   real y dos tenants reales.
2. La vía de automatización/workflows (`teamflow_engine.py` →
   `HANDLER_MAP["JUSTICIA"]["document_reviewed"/"compliance_check"]` →
   `handle_justicia_task`) — ERA un stub puro (texto fijo, sin BD, métrica
   inventada) y se corrigió en este commit a lógica real (GDPR real +
   documentos pendientes reales + firma real oportunista), con fallo
   explícito si no hay usuario resoluble.

Además se descubrió y corrigió una fuga de aislamiento multi-tenant
(conteo agregado de `compliance_events`) no relacionada con "simulación"
pero sí con la regla de aislamiento estricto de la skill.

Quedan 5 hallazgos nuevos, distintos y documentados (sección 5) que
requieren decisión explícita del usuario/auditor — ninguno es del tipo
"toolkit legal = stub" (todos parten de lógica real ya existente, con gaps
de scope de tenant o de etiquetado de metadatos), por lo que no bloquean el
cierre del hallazgo histórico original, pero sí deberían registrarse como
tareas nuevas de `auditor-priorizador`.

## 7. Regresión — suite completa

Baseline de la rama `feature/consolidacion-final` (antes de este commit):
`7 failed, 292 passed, 34 warnings, 3 errors` (confirmado ejecutando la
suite antes de tocar código).

Tras los cambios de este commit (2 archivos de producción modificados + 2
archivos de test nuevos, 8 tests nuevos):

```
7 failed, 300 passed, 34 warnings, 3 errors in 179.63s
```

Los mismos 7 failed / 3 errors que el baseline (pre-existentes, no
relacionados con JUSTICIA — `test_basic.py`, `test_perseo_autofix_v2.py`,
`test_thalos_control_layer_v1.py`, `test_thalos_safe_v1.py`,
`test_justicia_control_layer_v1.py::test_default_flags_simulated` (falla
por el mismo motivo que antes de este commit — no relacionado con los
cambios de esta sesión: espera flags simulados por defecto y el entorno de
test ya trae `JUSTICE_REAL_AUDIT_ENABLED=true`), `test_app.py`). Cero
regresiones; +8 tests nuevos en verde.

## 8. Comandos de verificación usados (evidencia reproducible)

```bash
# Suite completa
cd backend && venv/Scripts/python.exe -m pytest tests -q

# Servidor real
DATABASE_URL="sqlite:///./zeus_justicia_audit_test.db" \
  venv/Scripts/python.exe -m uvicorn app.main:app --port 8811

# Dos tenants reales
curl -X POST http://127.0.0.1:8811/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"email":"tenanta.justicia@gmail.com","password":"TestPass123","full_name":"Tenant A Owner","phone":"600111222","company_name":"Empresa A Justicia","business_type":"services"}'
curl -X POST http://127.0.0.1:8811/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"email":"tenantb.justicia@gmail.com","password":"TestPass123","full_name":"Tenant B Owner","phone":"600333444","company_name":"Empresa B Justicia","business_type":"services"}'

# Login (form-encoded, no JSON)
curl -X POST http://127.0.0.1:8811/api/v1/auth/login -d "username=tenanta.justicia@gmail.com&password=TestPass123"

# Endpoints reales (con Authorization: Bearer <token>)
curl http://127.0.0.1:8811/api/v1/justice/status
curl -X POST http://127.0.0.1:8811/api/v1/justice/contracts/generate -d '{"parties":["Empresa A","Cliente X"],"scope":"consultoria"}'
curl -X POST http://127.0.0.1:8811/api/v1/justice/sign -d '{"document_id":"<id>","signer":"Tenant A Owner"}'
curl -X POST http://127.0.0.1:8811/api/v1/justice/gdpr -d '{"systems":["whatsapp"]}'
curl http://127.0.0.1:8811/api/v1/justice/documents
curl http://127.0.0.1:8811/api/v1/justice/documents/<id>          # 404 desde otro tenant
curl http://127.0.0.1:8811/api/v1/justice/compliance-events        # 403 para no-superusuario
curl http://127.0.0.1:8811/api/v1/justicia/v1/status
curl http://127.0.0.1:8811/api/v1/justicia/v1/system-audit
curl http://127.0.0.1:8811/api/v1/justice/status                   # sin token -> 401
```
