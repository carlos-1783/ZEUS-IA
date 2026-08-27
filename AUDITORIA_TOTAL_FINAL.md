# AUDITORÍA TOTAL FINAL — feature/fix-thalos-shield-real (revisión independiente)

**Rol**: revisor-independiente (solo lectura, sin permiso de Edit/Write sobre código).
**Rama auditada**: `feature/fix-thalos-shield-real`, commit `e6c9717` (confirmado con
`git branch --show-current` y `git log -1` al iniciar; `git status` limpio).
**Worktree**: `C:\Users\Acer\ZEUS-IA\.claude\worktrees\agent-a9f8f12f24d0bc95c`.
**Backend usado para todas las pruebas en vivo**: proceso `uvicorn app.main:app`
en `127.0.0.1:8020` (PID 29292), confirmado que sirve ESTE worktree inyectando
un registro marcador (`MarkerCheck ABC123`, company_id 1952) vía API y
verificándolo acto seguido directamente en `backend/zeus.db` de este worktree.
DB: SQLite local (`backend/zeus.db`), alembic `current` = `0047 (head)` = `alembic
heads` → sin migraciones pendientes.
**Nota de continuidad**: esta ejecución es la continuación, en la misma sesión,
de un intento anterior de esta misma auditoría que fue cortado por límite de
sesión. El repo seguía limpio (`git status` sin cambios, sin
`AUDITORIA_TOTAL_FINAL.md`) al empezar esta vuelta — se confirma que no había
nada guardado. El scratchpad de la sesión conservaba artefactos de trabajo
previo (tokens, scripts de exploit) que se han reutilizado como PUNTO DE
PARTIDA pero cuyos resultados se han vuelto a ejecutar/confirmar en esta
vuelta, no se han dado por buenos sin repetir la prueba.

---
## 1. Los 6 agentes — input real → proceso real → output real → log real

Metodología: llamadas curl reales contra el backend en vivo, con tokens de
usuarios creados por mí en esta sesión (Tenant A = `revisor.marker.abc123@test.com`,
company_id 1952; superusuario = `revisor.super.rev1@test.com`), verificación
cruzada en `backend/zeus.db` y en `agent_activities`.

| Agente | Endpoint probado | Resultado real observado | Log verificado |
|---|---|---|---|
| ✅ ZEUS (orquestador) | `POST /api/v1/zeus-core/leads` | `{"success":true,"lead_id":49,"lead_score":10.0,"customer_priority":"low","next_best_action":"nurture"}` (HTTP 200). Confirmado en `crm_leads` (`id=49, company_id=1952, owner_user_id=2449, lead_score=10.0`) — persistencia real, scoring real, `company_id` correcto (tenant A). | `agent_activities`: 331 filas `ZEUS` + 204 `ZEUS CORE` |
| ⚠️ ZEUS legacy stub | `POST /api/v1/zeus/execute` `{"agent":"THALOS","command":"SCAN"}` | HTTP 500: `2 validation errors for ZeusResponse — agent / timestamp Field required`. El stub legacy de `app/core/zeus_agents.py` no solo es "hardcodeado" (ya documentado) sino que además **crashea** con esta rama de código (bug de Pydantic, no solo simulación). Sigue montado y accesible en producción. | N/A (crashea antes de loggear) |
| ✅ PERSEO | `GET /api/v1/perseo/v2/status` | `"perseo_v2_enabled": false, "execution_mode": "SIMULATED", "writes_enabled": false` — el propio sistema declara honestamente su modo simulado, no oculta el estado. | — |
| ✅ PERSEO (fallo honesto) | `POST /api/v1/perseo/v2/ads/create` `{"platform":"google","name":"Test Revisor","budget":100,"objective":"traffic"}` | HTTP 403 `{"detail":"writes_enabled false"}` — falla explícito, no éxito falso, en la capa v2 actual. | `agent_activities`: 35 filas `PERSEO` |
| ⚠️ PERSEO (placeholder histórico NO resuelto de raíz) | Código: `backend/services/perseo_ads_engine_v2.py:66-81` (`create_google_campaign`) | Con `_google_configured()==False` (caso real de este entorno, sin credenciales Google Ads) devuelve honestamente HTTP 503 `google_ads_not_configured` — mejora real frente a lo documentado en `agentes.md`. **Pero si `_google_configured()` fuera `True`** (credenciales presentes), el mismo código sigue devolviendo `{"success": true, "campaign_id": None, "simulated": False, "message": "Google Ads API client not installed — campaign persisted locally only"}` **sin llamar nunca a la API real de Google** — éxito falso con `simulated:false` que sigue siendo el hallazgo histórico, solo que ahora enmascarado por un guard que en este entorno concreto (sin credenciales) no deja verlo en vivo. No se pudo forzar el branch "configurado" sin fijar variables de entorno del sistema (fuera de alcance de un rol de solo lectura). | — |
| ✅ RAFAEL | `POST /api/v1/rafael-fiscal/model-303/generate` `{"year":2026,"quarter":2}` | HTTP 422 `{"detail":"No hay datos financieros en el periodo (facturas ni gastos)."}` — consulta real a BD (no hay facturas en ese periodo para el tenant), falla controlado, no simulado. | `agent_activities`: 76 filas `RAFAEL` |
| ✅ JUSTICIA | `POST /api/v1/justice/contracts/generate` | HTTP 200, `{"document_id":"2d1bd7bd-...","db_id":1,"version":1,"status":"draft","content_preview":"# CONTRATO..."}` — documento real generado y persistido (`db_id=1`). `GET /api/v1/justice/status` confirma `"compliance_events":181,"justice_real_audit_enabled":true,"execution_mode":"REAL"`. | `agent_activities`: 1 fila `JUSTICIA` (bajo, pero no cero) |
| ✅ AFRODITA | `GET /api/v1/afrodita/rrhh/v1/status` | `{"execution_mode":"SIMULATED","writes_enabled":false,"db_connected":true,...}` — estado real y honesto de los flags de ejecución (por defecto en `false` en este entorno, igual que PERSEO/THALOS). | `agent_activities`: 576 filas `AFRODITA` |

**Conclusión Sección 1**: los 6 agentes tienen endpoint propio, ejecutan lógica
real contra BD y registran actividad verificable. El hallazgo histórico de
PERSEO/Google Ads sigue sin resolverse de raíz (solo se añadió un guard de
"no configurado" que oculta el problema en el caso común, no lo elimina). El
stub legacy de `/api/v1/zeus/execute` sigue montado y ahora además crashea con
un error 500 no controlado en vez de devolver el placeholder falso silencioso
documentado previamente — sigue siendo deuda técnica viva, ahora peor (error
no controlado en vez de simulación silenciosa).

---

## 2. THALOS — fix estructural (repetición independiente de exploits)

### 2.1 Migración de esquema (company_id en tablas THALOS)

- `alembic current` → `0047 (head)`, igual que `alembic heads` → sin desfase.
- `backend/alembic/versions/0046_thalos_tables_company_id.py` añade
  `company_id` a `thalos_events`, `thalos_alerts`, `thalos_login_attempts`
  (`thalos_security_events` ya lo tenía desde 0030).
- Confirmado en vivo contra `backend/zeus.db` (no solo leyendo la migración):

```
thalos_events            company_id presente: True
thalos_alerts            company_id presente: True
thalos_login_attempts    company_id presente: True
thalos_security_events   company_id presente: True
```

- `0047_thalos_row_level_security.py` (RLS) solo aplica políticas reales en
  Postgres; en este entorno (SQLite) no se puede verificar la policy en vivo
  — limitación ya reconocida en el propio commit `e6c9717` ("RLS-vs-Postgres-real"
  queda como tarea aparte). No se puede dar por bueno el RLS sin una BD Postgres
  real; queda como verificación pendiente, no como "aprobado".

### 2.2 Exploit de handlers de automatización (`services/automation/handlers/thalos.py`)

Reejecuté en vivo (no reutilicé el resultado pegado en ningún informe previo)
el script de exploit con tenants 100% nuevos generados con UUID aleatorio en
esta sesión:

```
=== TENANT A: atacante NO superusuario ===
BACKUP (attacker): blocked superuser_required_for_global_audit
SECURITY_SCAN (attacker): blocked superuser_required_for_global_audit
ALERTS (attacker): blocked superuser_required_for_global_audit

=== TENANT B: superusuario real (tenant distinto de A) ===
BACKUP (admin): completed   (1 fichero de backup creado y verificado, luego borrado por el propio test)
SECURITY_SCAN (admin): completed
ALERTS (admin): completed
```

Los 3 handlers (`handle_thalos_backup`, `handle_thalos_security_scan`,
`handle_thalos_alerts`) bloquean correctamente al atacante no-superusuario y
permiten el control positivo con un tenant superusuario distinto. **Hallazgo
de higiene (no bloqueante, ya conocido)**: en `backend/storage/backups/`
quedaban 2 ficheros huérfanos de una sesión de pruebas anterior
(`zeus_backup_20260826T173026Z.db`, `...173027Z.db`, timestamps que coinciden
con la creación de `AuditCo A/B` de la Vuelta 7) — confirma lo ya documentado
en el commit `e6c9717` sobre "higiene de tests que generan backups reales".
No se han borrado estos ficheros porque este rol no tiene permiso de
escritura/limpieza.

### 2.3 Spoofing de `company_id` en endpoints REST

- Los 7 endpoints de `backend/app/api/v1/endpoints/thalos.py`
  (`/status`, `/events`, `/alerts`, `/alerts/{id}/resolve`, `/audit`,
  `/monitor`, `/logs/ingest`) y los de `thalos_v1.py` (`/status`, `/events`,
  `/alerts`, `/audit`) exigen `is_superuser` antes de tocar las tablas
  globales sin `company_id` fiable. Probado en vivo:

```
Tenant A (no superuser) -> /thalos/status, /thalos/audit, /thalos/alerts,
/thalos/events, /thalos/v1/status, /thalos/v1/events, /thalos/v1/alerts,
/thalos/v1/audit  => 403 en los 8
Superuser          -> los mismos endpoints => 200 en los 4 comprobados
```

- Spoofing de `company_id` en el body de `POST /thalos/v1/execute`: con la
  configuración por defecto de este entorno (`THALOS_EXECUTION_ENABLED=false`)
  la ruta corta ANTES de llegar a la validación de `company_id` (devuelve
  `"status":"blocked","reason":"REAL_ACTIVE required..."` tanto si Tenant A
  manda `company_id:1954` — de Tenant B — como si manda el suyo propio,
  1952). Para no dar por bueno un gate que en la práctica es inalcanzable con
  los flags actuales, probé la función real de aislamiento
  (`services/workspace_deliverables.py:190 user_has_company_access`)
  directamente contra la sesión de BD real:

```
A -> own company 1952: True
A -> company B 1954 (SPOOF attempt): False
super -> company A 1952: True
super -> company B 1954: True
```

  Confirma que el gate de aislamiento SÍ funciona a nivel de lógica, aunque
  hoy esté detrás de un segundo gate (flags de ejecución) que lo hace no
  observable end-to-end vía HTTP en este entorno.

**Conclusión Sección 2**: los 3 exploits repetidos (handlers de automatización,
gates de superusuario en REST, aislamiento de `company_id`) siguen bloqueados.
Confirmo el cierre de la Vuelta 7 tal como está documentado en el commit
`e6c9717`, con dos matices que NO son bloqueantes pero deben quedar
explícitos: (a) el RLS de Postgres no se puede verificar sin una BD Postgres
real; (b) persisten ficheros de backup huérfanos de pruebas anteriores.
