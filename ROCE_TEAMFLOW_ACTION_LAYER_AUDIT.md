# ROCE — TeamFlow vs ejecución real | Capa Action Dispatcher

**Rol:** Senior System Architect & Backend Engineer  
**Objetivo:** Confirmar si el teamflow existente cubre ejecución real y definir la capa faltante para acciones persistentes.  
**Regla:** Si algo no existe, se dice explícitamente. Si existe parcialmente, se indica qué falta.

---

## 1. Diagnóstico: TeamFlow vs ejecución real

### Lo que SÍ existe hoy

| Componente | Estado | Ubicación |
|------------|--------|-----------|
| **TeamFlow Engine** | Existe. Define workflows (prelaunch_campaign_v1, invoice_flow_v1, contract_sign_v1, rrhh_onboarding_v1, ads_launch_v1). | `services/teamflow_engine.py` |
| **Escritura de actividad en BD** | Existe. `ActivityLogger.log_activity()` crea filas en `agent_activities`. | `services/activity_logger.py` → modelo `AgentActivity` |
| **Ejecutor de automatización** | Existe. Polling cada N segundos de `AgentActivity` con status `pending`/`in_progress`; llama `run_workspace_task(activity)` → handler. | `services/automation/agent_executor.py` |
| **Handlers reales** | Existen. PERSEO (task_assigned), RAFAEL (task_assigned), JUSTICIA (task_assigned, document_reviewed, compliance_check), AFRODITA (task_assigned), THALOS (security_scan, task_assigned→alerts, backup_created), ZEUS (coordination, task_delegated). | `services/automation/handlers/` + `HANDLER_MAP` en `__init__.py` |
| **Runtime unificado** | Existe. `run_workspace_task` carga memoria, resuelve handler, ejecuta, persiste estado y decision_log. | `services/unified_agent_runtime.py` |
| **API TeamFlow** | Existe. `POST /teamflow/workflows/{workflow_id}/run` → crea N actividades (pending/in_progress) en BD. | `app/api/v1/endpoints/teamflow.py` |
| **Feedback a UI** | Existe. `GET /api/v1/activities/{agent}`, `GET /api/v1/metrics/summary` leen `AgentActivity`. | endpoints activities, metrics |

### Lo que es solo lógico (sin ejecución real)

- **TeamFlow crea actividades** en BD (escritura real), pero muchos **pasos del workflow no tienen handler** asignado en `HANDLER_MAP`. Para esos pasos, `resolve_handler(agent, action_type)` devuelve `None` y `run_workspace_task` devuelve `status: "completed"` con nota *"Actividad '...' completada automáticamente"* **sin ejecutar nada**. Es decir: **simulación de éxito**.
- **Action types de TeamFlow sin handler real (ejemplos):**
  - **invoice_flow_v1:** `invoice_sent`, `qr_capture` → RAFAEL solo tiene `task_assigned`. Resto: simulado.
  - **contract_sign_v1:** `contract_generator`, `document_signed` → JUSTICIA tiene `document_reviewed`/`compliance_check` pero no `contract_generator` ni `document_signed`. Simulado.
  - **rrhh_onboarding_v1:** `contract_creator_rrhh` → AFRODITA solo `task_assigned`. Simulado.
  - **ads_launch_v1:** `image_analyzer`, `ads_campaign_builder` → PERSEO solo `task_assigned`. Simulado.
- **Conclusión:** TeamFlow es **orquestación real** (crea actividades en BD), pero la **ejecución** de muchos pasos es **simulada** porque no hay handler para ese `(agent, action_type)`.

### Resumen diagnóstico

| Afirmación en context | Realidad |
|------------------------|----------|
| `real_execution: false` | **Parcial.** Hay ejecución real para los (agent, action_type) mapeados en HANDLER_MAP (p. ej. PERSEO task_assigned → vídeo/JSON real). El resto se marca "completed" sin hacer nada. |
| `db_activity_write: false` | **Falso.** ActivityLogger y AgentActivity escriben en BD. TeamFlow.run_workflow escribe; el executor actualiza status/details. |
| `action_dispatcher: false` | **Parcial.** El “dispatcher” existe **dentro** del executor: `resolve_handler(agent, action_type)` → handler. No existe como **API** unificada (p. ej. `POST /actions/execute`). |

---

## 2. Arquitectura mínima de la capa Action Dispatcher

Objetivo: un único punto de entrada para “ejecutar una acción” (desde UI o desde TeamFlow), con intención parseada, permisos y escritura auditable en BD.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              UI / Cliente                                │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │  POST /actions/execute  { "intent" | "workflow_id" | "action_type", "payload", ... }
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Intent Parser (nuevo)                                                   │
│  - Si llega workflow_id → delega a TeamFlow.run_workflow (ya existe).   │
│  - Si llega action_type + agent + payload → crea 1 AgentActivity o       │
│    ejecuta síncrono según policy.                                        │
│  - Si llega "intent" texto → (opcional) NLU → action_type + payload.     │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Permission Layer (nuevo o ampliar auth)                                 │
│  - Comprobar que current_user puede ejecutar (agent, action_type).        │
│  - Ej: solo superuser para invoice_sent; todos para task_assigned.       │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Action Dispatcher (nuevo API, lógica ya existe en executor)             │
│  - Crear AgentActivity (status pending/in_progress) vía ActivityLogger.  │
│  - Opción A: encolar y devolver activity_id (ejecución async por        │
│    AgentAutomationExecutor como hoy).                                    │
│  - Opción B: ejecutar en el request run_workspace_task(activity) y       │
│    devolver resultado (sync).                                            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Activity Writer (ya existe)                                              │
│  - ActivityLogger.log_activity() / AgentActivity en BD.                  │
│  - Executor actualiza status, details, metrics al terminar.              │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Execution Result Feedback to UI (ya existe)                              │
│  - GET /activities/{agent}, GET /metrics/summary.                        │
│  - Opcional: WebSocket o polling corto para “activity_id completed”.     │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Intent Parser:** No existe como tal. Hoy la “intención” es implícita: (1) UI llama `POST /teamflow/workflows/{id}/run`, o (2) chat, o (3) prelaunch crea actividades. Falta un componente que acepte `action_type + agent + payload` (o en el futuro `intent` texto) y decida si crear actividad o ejecutar sync.
- **Action Dispatcher:** La lógica de “resolver handler y ejecutar” está en el executor; falta exponerla como API (`POST /actions/execute`) con política sync/async.
- **Permission Layer:** No existe por acción. Solo auth (get_current_user). Falta “puede ejecutar (agent, action_type)”.

---

## 3. Endpoints y payloads propuestos

### 3.1 POST /actions/execute (nuevo)

Unificar “ejecutar una acción” con trazabilidad en BD.

**Request (ejemplo):**

```json
{
  "agent": "PERSEO",
  "action_type": "task_assigned",
  "payload": { "brand": "ACME", "channel": "linkedin" },
  "sync": false
}
```

- `sync: false` → crea `AgentActivity` (pending/in_progress), responde con `activity_id`; el executor existente la procesa.
- `sync: true` → crea actividad, llama a `run_workspace_task(activity)` en el request, actualiza actividad, devuelve resultado en la respuesta.

**Response (async):**

```json
{
  "success": true,
  "activity_id": 123,
  "status": "pending",
  "message": "Activity queued for execution"
}
```

**Response (sync):**

```json
{
  "success": true,
  "activity_id": 123,
  "status": "completed",
  "result": { "status": "completed", "notes": "...", "details_update": { ... } }
}
```

### 3.2 POST /activity/write (nuevo, opcional)

Para que la UI u otro servicio registre una actividad **sin** ejecutar handler (solo auditoría).

**Request:**

```json
{
  "agent_name": "ZEUS",
  "action_type": "manual_note",
  "action_description": "Revisión manual de campaña",
  "details": { "campaign_id": "x" },
  "status": "completed"
}
```

**Response:** `{ "success": true, "activity_id": 124 }`

- Sería un wrapper fino sobre `ActivityLogger.log_activity()` con validación y permisos.

### 3.3 Ya existentes (sin cambios)

- `POST /teamflow/workflows/{workflow_id}/run` → crea N actividades (sigue siendo el flujo “workflow completo”).
- `GET /api/v1/activities/{agent}?days=7` → feedback a UI.
- `GET /api/v1/metrics/summary` → métricas.

---

## 4. Esquema de base de datos (activity)

La tabla relevante ya existe: **agent_activities**. No hace falta una tabla nueva `activity_log` si se usa esta como registro auditable de acciones.

**Esquema actual (resumen):**

| Campo | Tipo | Uso |
|-------|------|-----|
| id | PK | Identificador único |
| agent_name | string | PERSEO, RAFAEL, … |
| action_type | string | task_assigned, invoice_sent, … |
| action_description | text | Descripción legible |
| details | JSON | Payload, resultados, contexto |
| status | string | pending, in_progress, completed, failed |
| metrics | JSON | Métricas opcionales |
| user_email | string | Actor/tenant |
| created_at, completed_at | datetime | Auditoría |
| priority | string | low, normal, high, critical |
| visible_to_client | bool | Si la UI puede mostrarla |

Si en el futuro se exige **solo** “log de auditoría” sin mezclar con cola de ejecución, se podría añadir una tabla `action_audit_log` (id, activity_id FK, event_type, payload, created_at) y escribir en ambas. Para la capa mínima, **usar solo `agent_activities`** es suficiente y evita duplicar estado.

---

## 5. Flujo exacto: UI → Intent → Dispatcher → DB → UI

1. **UI** llama `POST /actions/execute` con `agent`, `action_type`, `payload`, `sync`.
2. **Intent Parser (nuevo):**  
   - Si llegara `workflow_id`, redirigir a `teamflow_engine.run_workflow` (como hoy).  
   - Con `action_type` + `agent`: validar y pasar al siguiente paso.
3. **Permission Layer (nuevo):** Comprobar que `current_user` puede ejecutar `(agent, action_type)`. Si no, 403.
4. **Action Dispatcher:**  
   - Crear `AgentActivity` vía `ActivityLogger.log_activity(..., status="pending" o "in_progress")`.  
   - Si `sync`: llamar `run_workspace_task(activity)`, actualizar actividad (status, details, metrics), commit.  
   - Si no sync: commit y devolver `activity_id`; el **AgentAutomationExecutor** existente procesará la actividad en el siguiente ciclo.
5. **Activity Writer:** Ya es el mismo `ActivityLogger` + modelo `AgentActivity` (BD).
6. **Feedback a UI:**  
   - Sync: resultado en la respuesta de `POST /actions/execute`.  
   - Async: UI usa `GET /activities/{agent}` o polling por `activity_id` hasta `status in (completed, failed)`.

Flujo actual sin nuevo endpoint:

- UI → `POST /teamflow/workflows/{id}/run` → TeamFlow crea N actividades → Executor (polling) las procesa → UI consulta `GET /activities`.

El nuevo flujo añade una vía **acción única** sin cambiar el flujo de workflows.

---

## 6. Implementación incremental sin romper el sistema actual

Sí, se puede hacer incremental.

1. **Fase 1 (solo API + dispatcher)**  
   - Añadir `POST /actions/execute` que: valide `agent` + `action_type`, cree una sola `AgentActivity` (pending/in_progress) y, si `sync=true`, llame a `run_workspace_task(activity)` y devuelva el resultado.  
   - No tocar TeamFlow ni el executor. El executor seguirá consumiendo las mismas actividades (las creadas por TeamFlow y las creadas por este endpoint).

2. **Fase 2 (permisos)**  
   - Añadir Permission Layer: tabla o config (agent, action_type) → roles permitidos; en `POST /actions/execute` comprobar después de parsear.  
   - Opcional: mismo chequeo en el executor antes de ejecutar (evitar ejecución por cambio de rol tras encolar).

3. **Fase 3 (Intent Parser opcional)**  
   - Si se quiere soportar `intent` en lenguaje natural, añadir un paso previo que mapee intent → `agent` + `action_type` + `payload` y luego usar el mismo flujo de Fase 1.

4. **Fase 4 (POST /activity/write)**  
   - Endpoint fino sobre `ActivityLogger.log_activity` para escritura explícita de actividades “manuales” o de auditoría.

No es necesario modificar `run_workspace_task`, ni los handlers, ni el modelo `AgentActivity`. Solo añadir capa HTTP + permisos y reutilizar executor y ActivityLogger.

---

## 7. Resumen ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| ¿TeamFlow es solo lógico? | No. TeamFlow **escribe** actividades en BD (real). Muchos **pasos** no tienen handler y se marcan “completed” sin ejecutar nada (simulación). |
| ¿Hay escritura real en BD? | Sí. ActivityLogger + AgentActivity. |
| ¿Hay ejecución real? | Sí para los (agent, action_type) en HANDLER_MAP; el resto se simula como completado. |
| ¿Existe Action Dispatcher? | Como lógica sí (resolve_handler + executor); como **API** unificada no. |
| ¿Qué falta para “acciones persistentes y auditables”? | (1) API `POST /actions/execute`, (2) Permission Layer por (agent, action_type), (3) opcional Intent Parser y `POST /activity/write`. |
| ¿Se puede implementar sin romper lo actual? | Sí. Añadir endpoint(s) y capa de permisos; reutilizar executor y ActivityLogger. |

Este documento es la base técnica para decidir la implementación de la capa Action Dispatcher y el uso de `agent_activities` como registro único de actividades y auditoría.
