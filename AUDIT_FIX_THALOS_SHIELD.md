# AUDIT_FIX_THALOS_SHIELD.md

Fix del hallazgo THALOS.SHIELD/SCAN/BLOCK simulado (capa legacy stub) +
aislamiento multi-tenant en `POST /api/v1/zeus/execute`.

- Rama: `feature/fix-thalos-shield-real`, creada desde `feature/rediseno-completo`
  (commit `35b0d8e`) en el repo `C:\Users\Acer\ZEUS-IA`, trabajada en el
  worktree `C:\Users\Acer\ZEUS-IA\.claude\worktrees\agent-a9f8f12f24d0bc95c`.
- No se tocó `main`. No se hizo push a ningún remoto.

## 1. Qué se encontró (confirmado de nuevo, no solo leído)

Reproducido en vivo antes de tocar código (`backend/app/core/zeus_agents.py`,
clase `ThalosAgent._execute_command`, líneas ~355-410 antes del fix):

```
THALOS.SHIELD -> encryption_status: "activo", jwt_oauth2: "configurado",
                 threats_blocked: 0   (siempre, literal, sin consultar nada)
THALOS.SCAN   -> vulnerabilities_found: 0, security_score: "100%" (siempre)
THALOS.BLOCK  -> blocked_ips: ["192.168.1.100", "10.0.0.50"] (siempre,
                 ignorando por completo el `data` recibido)
```

El endpoint que lo expone, `POST /api/v1/zeus/execute`
(`backend/app/api/v1/endpoints/zeus_core.py`), estaba autenticado
(`get_current_active_user`) pero no resolvía ni filtraba por tenant: dos
usuarios de empresas distintas obtenían exactamente la misma respuesta
(hardcodeada), sin ningún dato ni verificación por empresa.

Investigación previa al fix (según lo pedido) sobre el workspace REAL de
THALOS: existen servicios reales y ya probados en producción que el stub
legacy ignoraba por completo:
- `app/core/crypto.py` — estado real de `FIELD_ENCRYPTION_KEY` (cifrado de
  datos sensibles en reposo).
- `app/core/config.py` — `SECRET_KEY` real, con detección explícita del
  valor de desarrollo (`dev_default_secret...`).
- `services/thalos_security_engine.py::scan_logs` — escaneo real de
  `agent_activities` + `thalos_login_attempts`, ya usado por
  `POST /thalos/v1/execute` (action=`detect_suspicious_activity`) y
  `POST /thalos/v1/monitor`.
- `services/thalos_executor.py::block_user` — bloqueo real de una cuenta de
  usuario (no de una IP), con flags de seguridad
  (`THALOS_EXECUTION_ENABLED`, `THALOS_AUTO_BLOCK`), salvaguardas
  (`PROTECTED_EMAILS`, superusuarios) y logging real
  (`ActivityLogger` + `ThalosSecurityEvent`).
- `workers/thalos_worker.py::worker_status()` — estado real del worker de
  monitorización 24/7 (antes el stub afirmaba `monitoring_24_7: True` fijo,
  sin comprobar si el worker está vivo).

## 2. Qué se cambió

### `backend/app/core/zeus_agents.py`

- `ThalosAgent` ahora tiene `self.db` / `self.company_id`, inyectados por
  `ZeusAgentManager.execute_zeus_command` justo antes de despachar un
  comando `THALOS.*` y limpiados (`= None`) en un `finally` justo después,
  para no dejar sesión de BD ni tenant "pegados" al agente singleton entre
  peticiones de usuarios distintos.
- `THALOS.SHIELD` (`_shield`): ya no devuelve valores fijos.
  - `encryption_status` se deriva de si `FIELD_ENCRYPTION_KEY` está
    configurada de verdad (misma fuente que `app/core/crypto.py`):
    `"activo"` / `"fallback_dev_no_valido_para_produccion"` (solo fuera de
    producción) / `"no_configurado"`.
  - `jwt_oauth2` se deriva de si `SECRET_KEY` es distinta del valor de
    desarrollo por defecto: `"configurado"` /
    `"clave_por_defecto_no_apta_produccion"`.
  - `monitoring_24_7` refleja `workers.thalos_worker.worker_status()["running"]`
    real, no `True` fijo.
  - `threats_blocked` es un `COUNT(*)` real sobre `thalos_security_events`
    (`action_taken = 'block_user'`), **filtrado por `company_id` del
    tenant del usuario autenticado**. Si no hay sesión de BD, se declara
    `"no_disponible"` (`threats_blocked_source: "sin_sesion_bd"`). Si hay
    sesión pero no se pudo resolver el tenant del usuario, se declara
    `"no_disponible"` (`threats_blocked_source: "tenant_no_resuelto_para_el_usuario"`)
    en vez de sumar el conteo global de todas las empresas (evita fuga
    entre tenants a través de esta métrica).
  - `status` pasa a `"degraded"` (en vez de `"success"` fijo) si cifrado o
    JWT no están realmente configurados para producción — ya no hay falso
    éxito.
- `THALOS.SCAN` (`_scan`): delega en el motor real
  `services.thalos_security_engine.scan_logs(db, hours, company_id)`, el
  mismo que usa la capa REST real (`/thalos/v1/execute`,
  `action=detect_suspicious_activity`). Sin `db` inyectada, devuelve un
  error explícito (`scan_result: "no_disponible"`), nunca un `0` inventado.
- `THALOS.BLOCK` (`_block`): ya no devuelve IPs fijas ignorando `data`.
  - Si se pide bloqueo por IP (`data.ip`/`data.ip_address`) sin
    `user_email`, responde `status: "not_implemented"` explícito
    (`blocked_ips: []`) — el sistema real no bloquea por IP, solo por
    cuenta de usuario, y eso se declara en vez de simularse.
  - Si se da `user_email`, delega en
    `services.thalos_executor.block_user(db, user_email, company_id=...)`,
    el mismo ejecutor real que usa `/thalos/v1/execute`. Respeta
    `THALOS_EXECUTION_ENABLED`/`THALOS_AUTO_BLOCK` (por defecto `false` en
    este entorno: la respuesta es `dry_run`/`executed: false`, nunca un
    falso "IPs bloqueadas").
- `ZeusAgentManager.execute_zeus_command(command, data, db=None, company_id=None)`:
  firma extendida (retrocompatible, ambos parámetros opcionales) para poder
  inyectar contexto real solo en la rama `THALOS.*`; el resto de agentes
  (ZEUS/PERSEO/JUSTICIA/RAFAEL/ANALISIS/IA) no se tocan.

### `backend/app/api/v1/endpoints/zeus_core.py`

- `POST /execute` ahora resuelve el tenant del usuario autenticado con
  `services.workspace_deliverables.primary_company_id_for_user(db, current_user)`
  (la misma función que ya usa la capa REST real de THALOS en
  `thalos_v1.py`) y lo pasa junto con `db` a
  `zeus_manager.execute_zeus_command(...)`. Antes, `db` se recibía como
  dependencia pero nunca se usaba y ningún comando se filtraba por tenant.

### `backend/tests/test_zeus_agents_thalos_real_v1.py` (nuevo)

6 tests que fijan el comportamiento correcto como regresión:
- Sin `db`: `SHIELD` declara `"no_disponible"` (no inventa cifras) y
  `encryption_status`/`jwt_oauth2` solo pueden tomar valores reales
  conocidos (no el literal fijo de antes).
- Con `db` y dos tenants (`company_a`, `company_b`) con eventos reales
  distintos: `threats_blocked` es 1 para A y 0 para B — aislamiento
  verificado a nivel de test, y el singleton queda limpio (`db`/`company_id`
  vuelven a `None`) tras la llamada.
- `SCAN` delega en `thalos_security_engine.scan_logs` real; sin `db`, error
  explícito.
- `BLOCK` nunca devuelve las IPs fijas del hallazgo original
  (`blocked_ips == []` siempre; regresión directa del hallazgo).
- `BLOCK` con email real respeta `THALOS_EXECUTION_ENABLED=False` (default):
  `executed: False`, no un falso éxito.

## 3. Cómo se probó

### Baseline (antes de tocar código)

```
cd backend
venv/Scripts/python.exe -m pytest tests -q
```
Resultado: `7 failed, 214 passed, 2 skipped, 35 warnings, 3 errors in 121.76s`
(idéntico al baseline reportado en el encargo).

### Reproducción del hardcode (antes del fix)

Script directo importando `zeus_manager` y llamando
`THALOS.SHIELD`/`SCAN`/`BLOCK` sin argumentos — confirmado el output 100%
fijo transcrito en la sección 1.

### Tras el fix

- **Suite completa**: `7 failed, 220 passed, 2 skipped, 35 warnings, 3 errors
  in 134.60s` — mismos 7 fallos preexistentes
  (`test_basic.py::test_config_loading`,
  `test_justicia_control_layer_v1.py::test_default_flags_simulated`,
  `test_perseo_autofix_v2.py::test_audit_includes_ai_modules`,
  `test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`,
  `test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`,
  `test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`,
  `test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`) más los 3
  errores preexistentes de `test_app.py` (`NameError: TestClient`), ninguno
  causado por este cambio. **+6 tests nuevos, todos en verde. Sin
  regresión.**
- **Aislamiento multi-tenant a nivel de servicio** (sin HTTP, sesión de BD
  directa): se crearon 2 empresas + 2 usuarios reales, 2
  `ThalosSecurityEvent(action_taken='block_user')` solo para la empresa A.
  `THALOS.SHIELD` para A devolvió `threats_blocked: 2`; para B,
  `threats_blocked: 0`. Confirmado con `assert` en script y en el test
  nuevo `test_shield_threats_blocked_is_tenant_isolated`.
- **Verificación end-to-end real por HTTP** (servidor uvicorn local,
  `venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123`):
  1. Se crearon 2 usuarios/empresas reales en la BD de desarrollo
     (`curltenanta_...@example.test` / `curltenantb_...@example.test`,
     `company_id=91` y `92`) y 3 `ThalosSecurityEvent` de bloqueo solo para
     la empresa 91.
  2. Login real vía `POST /api/v1/auth/login` (form-data
     `username`/`password`/`grant_type=password`) para ambos usuarios ->
     JWT reales.
  3. `POST /api/v1/zeus/execute` con `{"command":"THALOS.SHIELD"}` y
     `Authorization: Bearer <token>`:
     - Tenant A (`company_id=91`): `"threats_blocked":3,
       "company_id_scope":91`
     - Tenant B (`company_id=92`): `"threats_blocked":0,
       "company_id_scope":92`
     - Respuestas **ya no son byte-idénticas** (antes del fix lo eran
       siempre, salvo el timestamp): difieren en `threats_blocked` y
       `company_id_scope`, reflejando el estado real de cada tenant.
       `encryption_status`/`jwt_oauth2` sí son iguales entre tenants — es
       legítimo, es configuración de sistema, no de tenant.
  4. `THALOS.BLOCK` sin `user_email` -> `status: "error"`,
     `blocked_ips: []`. Con `data.ip` -> `status: "not_implemented"`,
     `blocked_ips: []` (antes: siempre
     `["192.168.1.100","10.0.0.50"]` ignorando `data`).
  5. `THALOS.SCAN` -> `status: "success"`, datos reales de
     `agent_activities`/intentos de login de la BD de desarrollo
     (`vulnerabilities_found: 6`, `activities_scanned: 122`, con patrones y
     candidatos a fuerza bruta reales, no `0`/`"100%"` fijos).
  6. Caso de error esperado: `POST /api/v1/zeus/execute` sin header
     `Authorization` -> `401 {"detail":"No se pudieron validar las
     credenciales"}` — falla controladamente, no 500 opaco ni falso éxito.
  7. Limpieza: se borraron los 2 usuarios/empresas/eventos de prueba de la
     BD de desarrollo tras la verificación (`cleanup_tenants.py`, ver
     salida `cleaned up users=[149, 150] companies=[91, 92]`).

Nota sobre la BD usada: este entorno usa `sqlite:///./zeus.db` (relativo a
`backend/`, en `.gitignore`, no se versiona) — es la BD de desarrollo local
del worktree, no la de producción en Railway. No se tocó ninguna migración
Alembic (no aplica: no se añadió/cambió ningún modelo/columna).

## 4. Qué sigue simulado o con alcance reducido (declarado explícitamente)

1. **Bloqueo por IP real**: no existe en el sistema (ni en la capa REST
   real, ni en el stub arreglado). `THALOS.BLOCK` con una IP ahora responde
   `not_implemented` explícito en vez de inventar una lista de IPs — es la
   opción "nunca falso éxito" que pide el encargo cuando la implementación
   100% real excede el alcance de este fix. Si se necesita bloqueo de IP de
   verdad, requiere diseño nuevo (p.ej. tabla de IPs bloqueadas +
   middleware que las consulte) — fuera de alcance de este commit.
2. **`thalos_security_engine.scan_logs` no filtra por tenant en la
   lectura**: audita `agent_activities`/`thalos_login_attempts` de forma
   global (esas tablas no tienen columna `company_id`); solo el evento
   persistido al final queda asociado al tenant. Esto es una limitación
   **preexistente de la capa REST real** (la usa tal cual
   `POST /thalos/v1/execute` y `POST /thalos/v1/monitor`), no introducida
   por este fix. `THALOS.SCAN` ahora la hereda porque delega en el mismo
   motor real en vez de duplicar lógica — se documenta explícitamente en la
   propia respuesta (`data.known_limitation`) y aquí. **No se ha corregido
   en este commit** porque implica migrar `company_id` a `AgentActivity`/
   `ThalosLoginAttempt` y tocar la capa REST real compartida — excede el
   alcance de "arreglar el stub legacy de zeus_agents.py" y se reporta como
   hallazgo nuevo para decidir si se aborda aparte.
3. **Singleton mutable compartido entre peticiones**: `zeus_manager` y sus
   agentes (incluido `ThalosAgent`) son instancias de proceso único
   (`self.status`, y ahora `self.db`/`self.company_id` durante la
   ejecución). Se mitigó el riesgo de fuga entre tenants limpiando
   `db`/`company_id` en un `finally` inmediatamente después de despachar el
   comando, y no hay ningún `await` entre la asignación y el uso dentro de
   `_execute_command` (no hay punto de cesión al event loop), por lo que en
   un único worker no hay condición de carrera real. No se ha rediseñado el
   patrón singleton en sí (crear una instancia de `ThalosAgent` por
   petición) porque afecta a la arquitectura completa de `zeus_agents.py`
   (los otros 6 agentes comparten el mismo patrón) — excede el alcance de
   este fix puntual. Se señala como hallazgo estructural a considerar si se
   decide modernizar toda la capa legacy.
4. **La capa legacy en sí sigue siendo legacy**: `agentes.md` ya señala que
   `zeus_core.py`/`zeus_agents.py` es la capa stub y que la fuente de verdad
   debería ser la capa REST por dominio (`thalos_v1.py`). Este fix hace que
   el stub **delegue** en los mismos servicios reales en vez de duplicarlos
   o inventarlos, pero no elimina la capa legacy ni el endpoint
   `/api/v1/zeus/execute` en sí — decisión de producto pendiente (¿se
   deprecia ese endpoint a favor de `/thalos/v1/*`?), fuera del alcance de
   este step.

## 5. Pendiente / a decidir por el usuario o el auditor

- Decidir si se deprecia `POST /api/v1/zeus/execute` en favor de la capa
  REST real (`/thalos/v1/execute`), dado que ahora delega en los mismos
  servicios de todas formas.
- Decidir si merece la pena, en un step aparte, añadir `company_id` a
  `AgentActivity`/`ThalosLoginAttempt` para que `thalos_security_engine.scan_logs`
  deje de auditar actividad global sin filtrar por tenant (afecta también a
  la capa REST real ya en producción, no solo a este stub).
- No se ha tocado ninguna migración Alembic (no hizo falta: no se
  añadieron/modificaron columnas ni tablas).
