# AUDIT_FIX_BLOQUE3 — Limpieza de la capa de simulación en el núcleo

Rama: `feature/limpieza-simulacion` (creada desde `main`, independiente de
`feature/fix-seguridad-critica` y `feature/multi-tenant-bd` — no se mezclan,
no se tocó nada de aislamiento multi-tenant ni de las otras dos ramas de
seguridad). 4 commits atómicos, uno por tarea. No se hizo merge ni push a
`main`.

**Objetivo**: eliminar la capa de orquestador simulado que seguía viva en
producción, y sustituir el hardcode de `/agents/status` por datos reales.

---

## Tarea 1 — Eliminar el orquestador simulado legacy

**Objetivo pedido**: borrar `zeus_core.py` y `app/core/zeus_agents.py` (el
orquestador legacy que devuelve dicts fijos con `"status": "success"`
siempre, estado solo en memoria, y contradicciones internas como el
dominio erróneo de RAFAEL) — confirmando antes que ningún módulo vivo
depende de ellos, y decidiendo si hay que migrar algo al orquestador real
(`zeus_core_v2.py`) antes de borrar.

### Lo que se encontró

Existen DOS archivos distintos llamados `zeus_core.py` en el repo, en
directorios distintos — confusión que había que resolver primero:

- `backend/agents/zeus_core.py` — una clase `ZeusCore(BaseAgent)` real,
  carga config desde `prompts.json`, usada de verdad por `chat.py`,
  `agents/__init__.py` y los event handlers/bus del sistema. **No es la
  que hay que borrar** — no tiene nada que ver con el hallazgo.
- `backend/app/api/v1/endpoints/zeus_core.py` — el endpoint que envuelve
  `app/core/zeus_agents.py`. **Esta es la capa simulada del hallazgo.**
  Su propio docstring dice `"RAFAEL: Salud y bienestar"` mientras
  `zeus_agents.py` define `RAFAEL = "rafael"  # Asistente Fiscal y
  Contable` — la contradicción exacta descrita en el encargo.

`app/core/zeus_agents.py` (`ZeusAgent`/`ZeusCore`/`zeus_manager`) es
código 100% en memoria: `self.logs = []` por instancia (se pierde al
reiniciar), `"status": "success"` hardcodeado en cada método, sin tocar
la base de datos nunca. Confirmado con `grep`: **solo**
`app/api/v1/endpoints/zeus_core.py` lo importa en todo el backend — seguro
de borrar sin migrar nada de ese archivo.

**Pero `app/api/v1/endpoints/zeus_core.py` NO era 100% simulado.** Cuatro
de sus ocho endpoints llaman a servicios reales, sin tocar `zeus_manager`
para nada:

| Endpoint | Servicio real | ¿Lo consume el frontend? |
|---|---|---|
| `GET /status` | `zeus_execution_controller_v1`, `zeus_safe_lock_v1`, `zeus_data_pipeline_v1` (mezclado con un campo `data.legacy` fake que nadie leía) | Sí — `zeus_status_api.ts` |
| `GET /repair/status` | `zeus_controlled_repair_v1` | No |
| `GET /completion/status` | `zeus_full_completion_v1` | No |
| `GET /document-pipeline/status` | `zeus_document_pipeline_v1` | Sí — `zeus_pipeline_api.ts` |
| `POST /activate` | `zeus_manager.activate_all_agents()` (100% fake) | Sí — `ZeusCore.vue` (huérfana) |
| `POST /execute` | `zeus_manager.execute_zeus_command()` (100% fake) | Sí — `ZeusCore.vue`, `ZeusHologram3D.vue` (ambas huérfanas) |
| `GET /agents` | `zeus_manager.agents` (100% fake) | No |
| `GET /commands` | dict estático (100% fake) | No |

`zeus_status_api.ts`/`zeus_pipeline_api.ts` los consume en vivo
`DashboardProfesional.vue` (vía `AgentActivityPanel.vue` →
`AfroditaWorkspace.vue`/`PerseoWorkspace.vue`), que a su vez es el panel
real usado por `OlymposDashboard.vue` — el dashboard que de verdad se
sirve en `/dashboard`. Borrar el archivo entero habría roto esa
funcionalidad real.

`ZeusCore.vue` (ruta `/zeus-core`) sí llamaba a `/activate` y `/execute`,
pero es una ruta **huérfana**: registrada en el router pero no enlazada
desde ningún menú/sidebar, solo alcanzable escribiendo la URL a mano.
`DashboardHolographic.vue` y el componente que usa (`ZeusHologram3D.vue`,
que también llama a `/execute`) están **declaradas pero nunca usadas en
ninguna ruta real** del router — inalcanzables incluso por URL directa.

### Decisión tomada

1. **Migrados** los 4 endpoints reales a `zeus_core_v2.py` (el orquestador
   real, prefix `/zeus-core`), quitando la única referencia que tenían al
   `zeus_manager` legacy (`/status` ya no llama a
   `zeus_manager.get_system_status()` para el campo `timestamp`/
   `data.legacy` — usa `datetime.utcnow()` directo, y ese campo no lo leía
   nadie real).
2. **Borrados** `app/core/zeus_agents.py` y
   `app/api/v1/endpoints/zeus_core.py` enteros (los 4 endpoints
   restantes eran 100% fake y sin consumidor real).
3. **Borrados** `ZeusCore.vue`, `DashboardHolographic.vue`,
   `ZeusHologram3D.vue` — dependían enteramente de lo borrado y eran
   código muerto (huérfano/inalcanzable) independientemente de eso.
4. Frontend actualizado: `zeus_status_api.ts` →
   `/api/v1/zeus-core/status`, `zeus_pipeline_api.ts` →
   `/api/v1/zeus-core/document-pipeline/status`. Corregida también una
   referencia cosmética a la ruta antigua dentro del propio
   `zeus_safe_lock_v1.py` (`execution_source_of_truth.endpoint`, un campo
   descriptivo del reporte de diagnóstico, no usado para lógica).

No se tocó `backend/agents/zeus_core.py` ni
`services/zeus_core_orchestrator_v1.py` — coinciden solo en el nombre con
lo borrado, son código real y en uso.

### Verificación

- `python -c "from app.main import app"` — import limpio, 394 rutas
  registradas.
- `curl /api/v1/zeus/status` (ruta legacy) → 404, confirmado eliminada.
- `curl /api/v1/zeus-core/status` y `/api/v1/zeus-core/document-pipeline/status`
  con token real → 200, datos reales (`execution_mode`, `safe_lock`,
  `modules`, etc. de `zeus_execution_controller_v1`/`zeus_safe_lock_v1`).
- Dashboard real cargado en navegador (login real vía formulario, no
  curl): `OlymposDashboard.vue` renderiza con datos en vivo, sin errores
  de red ni de consola relacionados con este cambio.
- Suite completa: **214 passed / 7 failed / 2 skipped / 3 errors** —
  idéntico al baseline documentado en los bloques anteriores.

---

## Tarea 2 — `GET /api/v1/agents/status` con datos reales

**Objetivo pedido**: sustituir el hardcode (`"uptime": "99.95%"` fijo) por
una consulta real a `agent_activities`, mismo patrón que
`/api/v1/metrics/dashboard`.

### Estado anterior

Los 6 agentes devolvían, en cada arranque y en cada request, exactamente
los mismos valores: `"status": "online"` fijo, un `"uptime"` distinto por
agente pero constante (nunca cambia), `"decisions_today": 0` siempre,
`"last_activity": datetime.utcnow().isoformat()` (es decir, "ahora mismo"
aunque el agente jamás hubiera hecho nada), `"avg_confidence"` inventado,
y `"system_health": "optimal"` fijo.

### Arreglo

Reescrito para calcular todo contra `agent_activities`, mismo patrón que
`/metrics/dashboard` en esta rama (consulta directa a la tabla, sin
tenant-scoping — esta rama parte de `main`, sin el trabajo de multi-tenant
de la otra rama; el endpoint sigue siendo público y agregado a nivel de
sistema, sin cambio de alcance):

- **`status`**: `"online"` si el agente tiene actividad en las últimas
  24h, si no `"idle"`.
- **`uptime`**: % de actividades completadas (no fallidas) en los últimos
  30 días. `null` si no hay ninguna actividad — no se inventa un
  porcentaje sin datos.
- **`last_activity`**: `MAX(created_at)` real del agente, o `null` si
  nunca actuó.
- **`decisions_today`** / **`decisions_last_30d`**: conteos reales.
- **`avg_confidence`**: eliminado — no existe ningún campo de confianza
  real en `AgentActivity` del que derivarlo; mejor omitirlo que fabricar
  un número.
- **`system_health`**: `"optimal"` si ≥50% de los agentes están online,
  `"degraded"` si hay alguno, `"idle"` si ninguno.
- `role`/`domain`/`country`/`capabilities`/`workspace_tools` se dejan como
  metadata estática del producto — no son mediciones, no dependían del
  hardcode que había que arreglar.

**Hallazgo intermedio resuelto**: `agent_activities.agent_name` no es 1:1
con los 6 agentes del registro — `"ZEUS"` (usado en `main.py`, `auth.py`,
`webhooks.py`, `email_service.py`) y `"ZEUS CORE"` (usado en `chat.py`,
`workspaces.py`, `teamflow.py`, `integrations.py`) alimentan el mismo
agente. Resuelto con un mapa de alias explícito
(`AGENT_NAME_ALIASES`) en vez de asumir que el nombre coincide siempre.

### Verificación

```
GET /api/v1/agents/status (sin auth, como siempre)
  ZEUS CORE: uptime 58.82%, decisions_today 17
  PERSEO:    uptime 100.00%, decisions_today 1
  RAFAEL:    uptime 100.00%, decisions_today 3
  THALOS:    uptime 80.00%, decisions_today 5
  JUSTICIA:  uptime null, decisions_today 0, status "idle"  (sin actividad real)
  AFRODITA:  uptime 100.00%, decisions_today 24
```

Valores realmente distintos y coherentes con la actividad real de cada
agente — no la lista fija de antes. `OlymposDashboard.vue` (consumidor
real en vivo) verificado en navegador sin errores, con polling cada 30s
funcionando (`GET /api/v1/agents/status → 200 OK` repetido en Network).
Suite completa: 214 passed/7 failed/2 skipped/3 errors, idéntico al
baseline.

`GET /api/v1/agents/stats` se deja **fuera de esta tarea** (no era lo
pedido explícitamente) — sigue con valores fijos
(`"total_decisions": 0`, etc.). Hallazgo relacionado, no arreglado.

---

## Tarea 3 — Auditoría de THALOS como middleware (decisión documentada)

**Objetivo pedido**: confirmar el estado actual de THALOS tras el Bloque
2, y decidir con evidencia si hace falta ampliarlo ahora o si el
aislamiento ya conseguido con RLS + auth cubre lo esencial para la demo —
documentando la decisión, no tomándola en silencio.

**Nota de contexto**: esta rama parte de `main`, no de
`feature/multi-tenant-bd` — el trabajo de RLS del Bloque 2 vive en esa
otra rama, no aquí. La pregunta se responde igualmente: ¿hace falta
ampliar THALOS *en esta rama, ahora*, o el aislamiento que ya existe (en
la otra rama, pendiente de mergear) es la protección que importa para la
demo?

### Estado real encontrado (con evidencia)

Se auditó todo el código con "thalos" en el nombre (15+ archivos: agentes,
endpoints, servicios, modelos, migraciones) para separar lo que es
middleware real (corre en cada request) de lo que no:

- **`agents/thalos.py`**: una persona/prompt de agente (para chat/
  workspace), no middleware — solo corre cuando se llama a un endpoint de
  THALOS específico.
- **`services/thalos_control_layer_v1.py`**: su propio docstring lo dice —
  *"Non-destructive overlay: no cambia lógica de negocio; envuelve
  respuestas API"*. Solo etiqueta metadata de ejecución (SIMULATION/
  REAL_SAFE/REAL_ACTIVE), no valida ni bloquea nada.
- **`app/api/v1/endpoints/thalos.py`/`thalos_v1.py`**: endpoints
  específicos (dashboards de seguridad), no middleware global.
- **`app/middleware/thalos_login_audit_middleware.py`**: el **único**
  código que corre como middleware FastAPI de verdad, interceptando
  peticiones. Su alcance completo: auditar intentos de login
  (éxito/fallo, email, IP) en `/api/v1/auth/login` y `/api/v1/auth/token`.
  **No hace nada más** — no valida inputs, no sanea nada, no controla
  acceso a ningún otro endpoint.
- El rate-limiting real del sistema (`SecurityMiddleware`, con headers de
  seguridad y límites por endpoint/IP) **no está branded como THALOS** —
  es infraestructura genérica separada.

Esto confirma exactamente lo que planteaba el encargo: THALOS, como
middleware, no valida nada de negocio más allá de auditoría de login — y
el rate-limiting que sí existe vive en otro componente sin relación con
el nombre THALOS.

**Hallazgo adicional durante la auditoría**: `THALOS_REAL_MONITORING`
defaultaba a `"false"` — ni siquiera esa única función (auditoría de
login) estaba activa de fábrica salvo que alguien pusiera la variable de
entorno a mano. Y con el flag activado a mano, el middleware **tampoco
funcionaba de verdad**: hacía `json.loads()` sobre el body de
`/api/v1/auth/login`, pero ese endpoint usa `Form(...)`/
`OAuth2PasswordRequestForm` (`application/x-www-form-urlencoded`), nunca
JSON — el parseo fallaba siempre en silencio (`JSONDecodeError`
atrapado), el email quedaba vacío, y la condición `if is_login and email`
nunca se cumplía. Es decir: **incluso activando el flag a mano, ningún
login real quedaba auditado nunca** — dos capas de simulación silenciosa
apiladas sobre la misma función.

### Decisión

**No se amplía el alcance de THALOS en esta tarea.** Justificación:

1. El riesgo crítico para la demo — que los datos de una empresa se
   filtren a otra — ya está cubierto por RLS a nivel de Postgres +
   filtrado por tenant a nivel de aplicación + JWT, verificado con
   evidencia real (curl contra Postgres de staging, aislamiento probado
   en ambas direcciones) en `AUDIT_FIX_BLOQUE2.md` de la rama
   `feature/multi-tenant-bd`. Ese trabajo, una vez mergeado, es la
   protección que importa para la demo — no depende de que THALOS exista.
2. Convertir a THALOS en lo que la skill zeus-produccion describe (una
   capa global de validación de inputs, saneamiento y control de acceso
   para *todas* las peticiones al núcleo) es una pieza de infraestructura
   sustancial — diseño, pruebas de regresión reales, y riesgo genuino de
   bloquear tráfico legítimo si se hace con prisa. No encaja en el alcance
   de una rama de "limpieza de simulación"; merece su propio bloque
   dedicado, con el mismo nivel de cuidado que tuvieron el Bloque 1
   (seguridad) y el Bloque 2 (multi-tenant).
3. Lo que SÍ se arregla aquí son los dos hallazgos de "simulación
   silenciosa" reales encontrados durante la auditoría — no ampliar el
   alcance de THALOS, sino hacer que lo poco que ya afirma hacer
   (auditoría de login) funcione de verdad:
   - `THALOS_REAL_MONITORING` cambiado a `"true"` por defecto — es una
     escritura de auditoría de solo lectura de negocio, envuelta en
     try/except con rollback, no puede romper el login si falla. Esto
     también activa `workers/thalos_worker.py` (monitorización de logs +
     creación de alertas reales en BD), que estaba igualmente "skipped"
     de fábrica.
   - Arreglado el parseo de body para leer `application/x-www-form-urlencoded`
     (lo que el endpoint real envía) en vez de asumir JSON siempre.

### Verificación

```
POST /api/v1/auth/login (credenciales correctas) → fila real en
  thalos_login_attempts: email correcto, ip real, success=1
POST /api/v1/auth/login (contraseña incorrecta)   → fila real:
  mismo email, success=0
```

`workers.thalos_worker` arranca en el log de arranque (antes:
`"[THALOS_WORKER] skipped (no monitoring flags enabled)"`, ahora
`"[THALOS_WORKER] started interval=30s"` + ciclos reales creando alertas).
Login verificado también end-to-end vía formulario real en el navegador.
Suite completa: 214 passed/7 failed/2 skipped/3 errors — idéntico al
baseline (los tests de THALOS que ya fallaban en el baseline no dependen
de estos dos flags; `test_monitoring_cycle_respects_flags` fija el flag
explícitamente con `monkeypatch`, insensible al nuevo default).

**Cabo suelto documentado, no resuelto en esta rama**: `THALOS_AUTO_BLOCK`
sigue en `"false"` por defecto — deliberado. Activarlo significa que
THALOS empezaría a bloquear IPs automáticamente tras cierto número de
fallos de login, un cambio de comportamiento activo (no solo auditoría),
que entra en la misma categoría que la decisión de arriba: ampliar el
alcance real de THALOS merece su propio bloque, no colarse aquí como
efecto secundario de arreglar el parseo de un middleware.

---

## Tarea 4 — Frontend: ruta `/dashboard` duplicada y `KpiAgentsView.vue`

**Objetivo pedido**: arreglar la ruta `/dashboard` duplicada
(`OlymposDashboard.vue` vs `Dashboard.vue`) y conectar
`KpiAgentsView.vue` a datos reales de `agent_activities` en vez de mock —
dependiente de que la Tarea 2 estuviera cerrada primero (lo estaba).

### `/dashboard` duplicada

`router/index.js` tenía dos entradas **top-level** (no anidadas, mismo
nivel del array `routes`) con `path: '/dashboard'`:
- `name: 'Dashboard'` → `OlymposDashboard.vue` (línea ~214)
- `name: 'DashboardProtected'` → `Dashboard.vue` (línea ~390, registrada
  después)

En Vue Router, cuando dos rutas comparten el mismo `path`, solo la
**primera registrada** es alcanzable — `DashboardProtected`/
`Dashboard.vue` llevaba tiempo siendo código muerto sin que nadie lo
notara, precisamente porque el propio bug de routing lo hacía invisible
(nunca se disparaba un error, simplemente esa rama del código nunca se
ejecutaba).

Inspeccionado `Dashboard.vue` antes de decidir qué hacer: es un dashboard
más antiguo y menos desarrollado —`recentActivities` hardcodeado con
nombres de muestra fijos ("Juan Pérez", "María García", "Carlos López"),
un gráfico Chart.js deliberadamente deshabilitado (comentario en el
propio código: *"Chart deshabilitado temporalmente para diagnóstico"*), y
una función `loadUserData()` con un bug de referencia real (`user.value =
userData` sin que `user` esté declarado — solo `userData`/`currentUser`)
que nunca se había detectado porque ni la función ni el archivo eran
alcanzables.

**Decisión**: borrar `Dashboard.vue` (no fusionarlo ni redirigirlo — es
claramente la versión abandonada, `OlymposDashboard.vue` es la que ya se
sirve de verdad y ya se verificó funcionando en las Tareas 1 y 2). Sus
tres componentes hijo (`SystemStatusBadge.vue`, `Zeus3D.vue`,
`DashboardMetric.vue`) no los importa nada más en todo el repo — quedaban
huérfanos tras el borrado, así que se borraron también. (El único otro
sitio que importaba `Dashboard.vue` era `main-ultra-minimal.js`, un
entry-point alternativo no referenciado desde `index.html`, `vite.config.ts`
ni `package.json` — completamente fuera del grafo de build real. Se deja
sin tocar, fuera del alcance de esta tarea, pero queda anotado como
hallazgo: es un archivo huérfano en el repo.)

### `KpiAgentsView.vue`

Antes: un array de 6 agentes hardcodeado en el `<script setup>`, sin
ninguna llamada a la API, con la pill "Online" fija para todos siempre.

Ahora: hace `fetch` real a `GET /api/v1/agents/status` (el mismo endpoint
ya real de la Tarea 2) en `onMounted`, mismo patrón que ya usan el resto
de vistas `views/kpi/*` (`KpiPageShell` + `loading`/`error` + `api.get`,
ver `KpiAutomationsAuditView.vue` como referencia). Muestra por agente:
estado real (online/idle), uptime real, decisiones de hoy, y fecha de
última actividad.

### Verificación

En navegador real (no solo curl): `/dashboard` carga
`OlymposDashboard.vue` sin ambigüedad. `/agents` (`KpiAgentsView.vue`)
muestra valores realmente distintos por agente — ZEUS CORE 59.46% / 37
hoy, PERSEO 100.00% / 1 hoy, cada uno con su propio timestamp de última
actividad — confirmado también por Network
(`GET /api/v1/agents/status → 200 OK` repetido). Suite completa: 214
passed/7 failed/2 skipped/3 errors, idéntico al baseline.

**Hallazgo relacionado encontrado, NO arreglado (fuera del alcance de
esta tarea)**: `DashboardProfesional.vue` (líneas 939/951/963) referencia
`shouldShowTPV.value` sin que `shouldShowTPV` esté declarado en ningún
sitio del archivo — error de consola real (`ReferenceError`) en tiempo de
ejecución. Confirmado que es un bug **preexistente**, no introducido por
ningún cambio de este bloque (no se tocó `DashboardProfesional.vue` en
ninguna de las 4 tareas) y que no bloquea el render del dashboard (el
resto del componente sigue funcionando, confirmado visualmente). Anotado
para que se arregle en un bloque futuro que sí toque ese archivo.

---

## Resumen de riesgo por tarea

| # | Tarea | Confianza | Verificado en vivo |
|---|---|---|---|
| 1 | Eliminar orquestador simulado (`zeus_core.py`/`zeus_agents.py`) | Alta | Sí — curl + navegador |
| 2 | `/agents/status` con datos reales | Alta | Sí — curl + navegador, valores realmente distintos por agente |
| 3 | Auditoría THALOS + activar auditoría de login real | Alta | Sí — curl (filas reales en BD) + navegador |
| 4 | `/dashboard` duplicada + `KpiAgentsView.vue` real | Alta | Sí — navegador, ambas rutas |

**Regresión**: las 4 tareas se verificaron una por una tras cada commit —
suite completa **214 passed / 7 failed / 2 skipped / 3 errors** en las 4
ejecuciones, exactamente el mismo baseline documentado en los bloques
anteriores. Cero regresiones nuevas introducidas.

## Cabos sueltos conocidos que quedan fuera de esta rama

- `GET /api/v1/agents/stats` sigue con valores fijos (Tarea 2, fuera del
  alcance explícito pedido).
- `THALOS_AUTO_BLOCK` sigue en `false` — bloqueo automático de IPs tras
  fallos de login repetidos, decisión deliberada de no activarlo aquí
  (Tarea 3, ver justificación arriba).
- Ampliar THALOS a validación real de negocio/saneamiento/control de
  acceso (lo que la skill zeus-produccion le exige idealmente) queda
  pendiente como su propio bloque futuro — decisión explícita, no
  silenciosa (Tarea 3).
- `DashboardProfesional.vue` tiene un `ReferenceError` real
  (`shouldShowTPV` no declarado) — preexistente, no introducido aquí, no
  bloquea el render, pendiente de un bloque que toque ese archivo
  (Tarea 4).
- `frontend/src/main-ultra-minimal.js` es un entry-point huérfano, no
  referenciado desde ningún config de build — no se tocó, fuera de
  alcance (Tarea 4).
- Esta rama parte de `main` y no incluye el trabajo de RLS/multi-tenant
  de `feature/multi-tenant-bd` ni los fixes de seguridad de
  `feature/fix-seguridad-critica` — ambas siguen sin mergear, tal y como
  pedía el alcance de este bloque ("no toques nada de las ramas de
  seguridad ni multi-tenant").

No se hizo merge ni push a `main`.
