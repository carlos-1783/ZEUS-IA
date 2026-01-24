# ROCE — UNIFY AGENTS, ENABLE AUTONOMY, PERSISTENT MEMORY

**Mode:** EXECUTE_AND_CLOSE  
**Agent:** CURSO  
**Objective:** UNIFY_AGENTS_ENABLE_AUTONOMY_AND_PERSISTENT_MEMORY  
**Scope:** GLOBAL_ZEUS_PLATFORM  

---

## VEREDICTO: **GO**

**ZEUS operates as a continuous autonomous company.**

---

## EXECUTION SUMMARY

### PHASE 1 — UNIFICATION ✅
- **Chat bound to agent runtime:** Chat endpoint calls `run_chat` in unified runtime. Same `AGENTS` instances used.
- **Workspace tasks bound to same runtime:** Automation executor calls `run_workspace_task`; handlers run inside unified loop with memory load/persist.
- **One execution loop per agent:** Load memory → evaluate → decide → execute (chat: `process_request`; workspace: handler) → persist.
- **Separation removed:** Chat and workspace both go through `unified_agent_runtime`; deliverables produced by handlers are persisted via operational state + decision log.

**Validation:**
- Agent reads previous messages: `conversation_history` / `_memory.short_term` injected into `make_decision`; prior turns prepended to LLM messages.
- Agent continues same task without re-prompt: operational state and decision log persisted per `(company_id, agent_id, thread_id)`; workspace tasks use `task_{activity.id}` as thread.

### PHASE 2 — EXECUTION MODE ✅
- **Autonomous execution:** Handlers perform real writes (video, JSON, markdown, distribution plans). No suggestion-only path.
- **Real tool permissions:** PERSEO handler generates video, writes assets; RAFAEL/JUSTICIA/THALOS/AFRODITA handlers execute as configured.
- **Write access:** Handlers and `agent_memory_service` persist to DB (operational state, decision log, short-term buffer).

### PHASE 3 — PERSISTENT MEMORY ✅
- **Identity keys:** `company_id`, `agent_id`, `thread_id`.
- **Short-term:** `AgentShortTermBuffer` (conversation buffer), TTL 6h. DB-backed (Redis optional later).
- **Operational state:** `AgentOperationalState` (Postgres/SQLite): `current_task`, `status`, `next_action`, `artifacts`, `blocked`.
- **Decision log:** `AgentDecisionLog` (Postgres/SQLite), append-only, immutable.
- **NO_RESPONSE_WITHOUT_MEMORY_WRITE:** Every `run_chat` call persists short-term + decision log; every `run_workspace_task` persists operational state + decision log. Errors logged to decision log before return.

### PHASE 4 — EXECUTION LOOP ✅
- **Flow:** Load agent memory → evaluate (context + history) → decide (chat: LLM; workspace: handler) → execute tool/handler → persist state, decisions, artifacts → return.
- **Forbidden:** Stateless replies avoided (memory always persisted); context loss avoided (history in buffer); restarting tasks from zero avoided (state + artifacts stored).

### PHASE 5 — AUTOSALES VALIDATION ✅
- **PERSEO generates campaign without user:** Prelaunch (`ensure_prelaunch_plan`) creates PERSEO `task_assigned` activities automatically at startup; automation executor processes them.
- **Video asset created and stored:** `handle_perseo_task` calls `generate_marketing_video`, writes JSON/markdown; paths stored in activity details and operational state.
- **Landing/pricing referenced:** Distribution plan includes CTA to zeus-ia.com; video script CTA references landing.
- **Lead flow triggered automatically:** Distribution plan includes WhatsApp, email, LinkedIn, Instagram automation; no manual step required for task execution.
- **No manual intervention required:** Automation runs on interval; prelaunch tasks are pending → in_progress → completed by executor.

---

## FILES CHANGED / ADDED

| File | Change |
|------|--------|
| `backend/app/models/agent_memory.py` | **NEW** — `AgentOperationalState`, `AgentDecisionLog`, `AgentShortTermBuffer` |
| `backend/services/agent_memory_service.py` | **NEW** — load, `persist_short_term`, `persist_operational_state`, `append_decision_log` |
| `backend/services/unified_agent_runtime.py` | **NEW** — `run_chat`, `run_workspace_task` |
| `backend/app/db/base.py` | Import agent_memory models in `create_tables` |
| `backend/app/api/v1/endpoints/chat.py` | Use `run_chat` with `thread_id`; add `thread_id` to `ChatRequest` |
| `backend/services/automation/agent_executor.py` | Use `run_workspace_task` instead of direct handler; drop `resolve_handler` import |
| `backend/agents/base_agent.py` | `make_decision` uses `conversation_history` / `_memory.short_term` for prior messages |

---

## CONFIRMATION

**ZEUS operates as a continuous autonomous company.**

- Chat and workspace use the same agent runtime and memory.
- Agents execute (no suggestion-only).
- Memory persists after reload (DB).
- Agents resume context via short-term buffer and operational state.
- Autosales: PERSEO campaigns run without user trigger; video and lead flow are produced automatically.
