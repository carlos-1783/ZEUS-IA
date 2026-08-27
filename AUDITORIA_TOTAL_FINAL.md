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

---

## 3. `GET /api/v1/metrics/dashboard` — sigue expuesto sin auth ni tenant

Petición real, sin cabecera `Authorization`, contra el backend en vivo:

```
$ curl -s -o resp.json -w "HTTP:%{http_code}\n" http://127.0.0.1:8020/api/v1/metrics/dashboard
HTTP:200
{"success":true,"total_interactions":1995,"avg_response_time":"177.7s",
 "cost_savings":"€78,050","success_rate":"78.2%", ...}
```

Repetido con token de Tenant A autenticado: **misma respuesta byte a byte**
(`total_interactions:1995`, `cost_savings:€78,050`) — confirma que ni siquiera
diferencia entre "sin token" y "con token de un tenant concreto": es un
agregado global, no filtrado, accesible por cualquiera.

**Severidad: CRÍTICO.** Este es exactamente el hallazgo que el propio commit
`e6c9717` de esta rama lista como pendiente ("metrics/dashboard" en la lista
de tareas no resueltas). Confirmado en vivo, no solo por lectura de código o
por el reporte previo. Existe un fix real para esto en otra rama
(`feature/fix-seguridad-critica`, commit `9141c71 fix(security): exigir auth
y aislar por usuario en GET /api/v1/metrics/dashboard`) que **no está
mergeado en `feature/fix-thalos-shield-real`** (ver Sección 5).

---

## 4. Heurística de onboarding — falso positivo reproducido en vivo

Se registró una empresa 100% nueva en esta sesión
(`revisor.onb.c1@test.com`, `company_id=1957`, tipo `restaurant`) y se
consultó `GET /api/v1/auth/onboarding/status` **inmediatamente después del
registro, sin completar cuestionario ni perfil operativo**:

```
{"validation":{"checks":{"tpv_products":4,"has_tpv_profile":true,
  "company_employees_count":1, ...}},
 "questionnaire_completed":false,
 "operational_profile_completed":false,
 "setup_completed":true,
 "setup_inferred":true, ...}
```

`setup_completed:true` aunque `questionnaire_completed:false` y
`operational_profile_completed:false` — la empresa nunca respondió el
cuestionario. La causa (leída en `backend/app/api/v1/endpoints/auth.py:594-618`)
es la misma heurística ya documentada: si `company_employees_count >= 1` o
hay productos TPV con perfil asociado, se infiere `setup_completed=True` sin
que el usuario haya completado nada explícitamente. En este caso el registro
con `business_type=restaurant` auto-sembró productos TPV y (al menos) un
empleado, disparando el falso positivo de inmediato.

**Confirmado, tal como se esperaba**: esta rama (`feature/fix-thalos-shield-real`)
**no contiene** el fix de esta heurística — existe en una rama hermana
separada (`feature/fix-onboarding-wizard-real`, ver Sección 5) que nunca se
fusionó aquí. Severidad: medio/alto (afecta a la fiabilidad del estado de
onboarding mostrado al usuario y a cualquier lógica que dependa de
`setup_completed`), pero es un hallazgo ya conocido y esperado, no nuevo.

---

## 5. Comparación de ramas — fixes de seguridad ausentes en esta rama

`git merge-base --is-ancestor <rama> HEAD` ejecutado contra todas las ramas
`feature/*` de seguridad/tenant existentes en el repo (no solo las dos
sugeridas):

| Rama | ¿Ancestro de esta rama? |
|---|---|
| `feature/fix-seguridad-critica` | ❌ NO incluida |
| `feature/multi-tenant-bd` | ❌ NO incluida |
| `feature/fix-jwt-audience-y-tenant-invoices` | ❌ NO incluida |
| `feature/auth-missing-endpoints` | ❌ NO incluida |
| `feature/fix-onboarding-wizard-real` | ❌ NO incluida (esperado, ver Sección 4) |
| `feature/thalos-real-activation` | ❌ NO incluida |
| `feature/stripe-payment-verification` | ❌ NO incluida |
| `feature/google-ads-fail-honesto` | ❌ NO incluida |
| `feature/limpieza-simulacion` | ❌ NO incluida |
| `feature/agents-status-real` | ❌ NO incluida |
| `feature/fix-enum-serialization-erp` | ❌ NO incluida |
| `feature/checkout-publico-fix` | ❌ NO incluida |
| `feature/envio-gestoria` | ❌ NO incluida |
| `feature/iva-duplicado` | ❌ NO incluida |
| `feature/hallazgos-visuales` | ❌ NO incluida |
| `feature/vertical-seguros` | ✅ incluida |
| `feature/facturacion-tpv-real` | ✅ incluida |
| `feature/onboarding-facturacion` | ✅ incluida |
| `feature/rediseno-completo` | ✅ incluida |
| `feature/auditoria-real-nucleo` | ✅ incluida |

### 5.1 `GET /invoices/` — verificado en vivo, y es PEOR de lo esperado

El hallazgo señalado por el usuario ("falta el fix de audiencia JWT de
`/invoices/`") se confirma, pero la causa raíz encontrada en vivo es más
grave que "falta aislamiento por tenant": **el endpoint está completamente
roto para CUALQUIER usuario, con CUALQUIER token válido.**

```
$ curl -H "Authorization: Bearer <token_superusuario_recien_emitido>" \
    http://127.0.0.1:8020/api/v1/invoices/?limit=5
{"detail":"No se pudieron validar las credenciales"}   HTTP 401
```

El mismo token, en el mismo minuto, funciona correctamente contra
`/api/v1/thalos/status` y `/api/v1/auth/onboarding/status`. Aislado el
problema a nivel de código: `backend/app/api/v1/endpoints/invoices.py:15`
importa `get_current_active_user` de `app.core.security` (no de
`app.core.auth`, que es lo que usan el resto de endpoints funcionales como
`tpv.py`/`control_horario.py`). Ese módulo (`app/core/security.py:272-287`)
llama:

```python
payload = jwt.decode(
    token, secret_key_str, algorithms=[settings.ALGORITHM],
    audience=settings.JWT_AUDIENCE,   # <- settings.JWT_AUDIENCE es una LISTA
    issuer=settings.JWT_ISSUER, ...)
```

y `settings.JWT_AUDIENCE` (`app/core/config.py:329`) es
`["zeus-ia:auth", "zeus-ia:access", "zeus-ia:websocket"]` — una lista. La
librería `python-jose` usada aquí (a diferencia de PyJWT) **no acepta una
lista como `audience`**. Reproducido de forma aislada, fuera del servidor:

```python
>>> jwt.decode(token, SECRET_KEY, algorithms=["HS256"],
...             audience=["zeus-ia:auth","zeus-ia:access","zeus-ia:websocket"],
...             issuer="zeus-ia-backend")
jose.exceptions.JWTError: audience must be a string or None
```

Esto rompe **todos** los endpoints que importan `get_current_active_user`
desde `app.core.security`: confirmado que son exactamente 3 —
`invoices.py`, `products.py`, `customers_fixed.py`. Verificado en vivo que
`GET /api/v1/products/` también devuelve 401 con el mismo token válido.
Es decir: hoy, en esta rama, **nadie puede listar facturas, productos o
clientes vía estos 3 routers**, sea cual sea su tenant o rol — no es un fallo
de aislamiento explotable, es una regresión de disponibilidad total.

Además, revisando el propio `list_invoices` (líneas 99-152) se confirma que,
si algún día se arregla el bug de audiencia sin tocar nada más, la fuga de
aislamiento por tenant seguiría ahí: `query = db.query(Invoice)` **sin ningún
filtro por `company_id`** en ningún punto de la función. El fix real de esto
existe en otra rama (`feature/fix-jwt-audience-y-tenant-invoices`, commits
`f3196ef`/`88fe637`, y `feature/fix-seguridad-critica`, commit `36b38fd`) y
**no está mergeado aquí**.

**Nota positiva de aislamiento**: el flujo de facturación real usado por TPV
(`POST /api/v1/tpv/invoice`, `app/api/v1/endpoints/tpv.py:1274`) usa
`app.core.auth` (el módulo que sí funciona) y no pasa por el router roto de
`invoices.py` — confirmado que el flujo de venta+factura de TPV (Sección 7)
no depende de este código roto.

### 5.2 Otros fixes ausentes verificados en vivo (no solo por `git log`)

- **`GET/POST /api/v1/google/*` sin autenticación** (`feature/fix-seguridad-critica`,
  commit `61b87c6`, ausente aquí). Confirmado que `backend/app/api/v1/endpoints/google.py`
  no importa ningún `Depends(get_current_active_user)` en ninguna de sus 9 rutas
  (`grep` sobre el fichero). Probado en vivo sin token:
  `GET /api/v1/google/drive/files?folder_id=abc` → HTTP 500
  `{"detail":"Google Drive not configured"}` — ejecuta lógica real (llega hasta
  el punto de fallo de configuración) **sin pedir ningún token**. Severidad:
  crítico si algún día se configuran credenciales de Google, porque cualquier
  visitante no autenticado podría leer/escribir Calendar, Gmail, Drive y Sheets
  de la cuenta configurada.
- **`POST /activities/log` SÍ exige auth en esta rama** (contraejemplo, por
  transparencia): aunque el commit `b2f5423` que lo arregla en
  `feature/multi-tenant-bd` no está mergeado, la prueba en vivo sin token
  devolvió `401 {"detail":"No se pudieron validar las credenciales"}` —
  no reproduce el problema aquí (puede estar cubierto por otro mecanismo). No
  se marca como hallazgo.
- **`GET /api/v1/agents/status` hardcodeado**: ya documentado en
  `references/agentes.md` de la skill como hallazgo transversal preexistente
  (no específico de esta rama); el fix (`feature/agents-status-real`, commit
  `0cd7668`) tampoco está mergeado aquí. No se ha vuelto a verificar en vivo
  en esta vuelta por no ser hallazgo nuevo, pero se deja constancia de que
  sigue sin resolver en esta rama.
- **Verificación de pago Stripe antes de activar cuenta** (`feature/fix-seguridad-critica`,
  commit `207afba`) — commit ausente aquí. No verificado en vivo en esta
  vuelta (requiere credenciales Stripe de test que no están confirmadas en
  este entorno); se deja como pendiente de verificación explícito, no como
  "aprobado".
- **Botón Admin sin proteger en `OlymposDashboard.vue`** (`feature/multi-tenant-bd`,
  commit `3430ec9`) — ausente aquí. Ver verificación de frontend en Sección 6.

**Conclusión Sección 5**: la rama `feature/fix-thalos-shield-real` resuelve a
fondo un problema estructural concreto (THALOS) pero deja fuera un número
significativo de fixes de seguridad ya existentes en otras ramas del mismo
repo — no solo el ya conocido de `/invoices/`. Antes de cualquier fusión a
`main` hace falta una decisión explícita sobre cómo incorporar (rebase/cherry-pick/
remerge) al menos: `feature/fix-seguridad-critica`, `feature/multi-tenant-bd`,
`feature/fix-jwt-audience-y-tenant-invoices` y `feature/auth-missing-endpoints`.

---

## 6. Frontend — pantallas verificadas en vivo (Playwright/browser real)

**Preparación e independencia de la prueba**: el proceso de vite ya estaba
corriendo en `5173` desde una sesión anterior sobre este mismo worktree
(confirmado por línea de comandos del proceso), pero su proxy apuntaba a
`localhost:8000`, que estaba caído. Para no dar por buena una captura vieja
en caché, arranqué yo mismo un segundo backend real
(`uvicorn app.main:app --port 8000`, mismo código/DB de este worktree) y
verifiqué que las pantallas cargan datos frescos generados por mí en esta
sesión (ver marcadores cruzados en cada punto).

| Pantalla | URL | Resultado |
|---|---|---|
| ✅ Login | `/login` | Formulario real, login contra backend real funciona (probado con Tenant A). |
| ✅ Dashboard (Panel) | `/dashboard` | Carga `OlymposDashboard.vue` → `DashboardProfesional.vue` (modo `firstPersonMode` por defecto). KPIs reales (agentes, alertas, etc.), lista de 6 agentes "En línea" con contador de actividades 24h que **cambió en vivo** de 0 a valores reales tras mis pruebas de agentes (Sección 1) — confirma que no es un valor estático. |
| ⚠️ Dashboard — bug JS confirmado | `/dashboard` | Consola: `Uncaught ReferenceError: shouldShowTPV is not defined` en `DashboardProfesional.vue:962,974,986`. Código (`grep`) confirma que `shouldShowTPV.value` se referencia dentro de tres `console.log` de depuración (delays de 100/500/1000 ms) **sin que `shouldShowTPV` esté nunca declarado** en el fichero. El error interrumpe la ejecución de esos callbacks antes de llegar a `updateModulesForSuperuser()`, por lo que el re-chequeo tardío de visibilidad de módulos para superusuarios nunca se ejecuta. No bloquea el resto de la pantalla (el error ocurre en un `setTimeout` aislado). |
| ✅ Agentes activos | `/agents` | Lista real de los 6 agentes con estado "Online". Pantalla informativa, sin acciones. |
| ⚠️ Núcleo ZEUS-IA (legacy) | `/zeus-core` | **Pantalla real y alcanzable que expone directamente el stub roto.** Al cargar, log en pantalla: `Error inicializando sistema: Error activando Núcleo ZEUS: 1 validation error for ZeusResponse agent Field required...` (mismo bug 500 de la Sección 1). Al ejecutar el comando `THALOS.SCAN` desde la consola de la UI, la petición real (vía `ZeusHologram3D.vue:364`) devolvió `403 THALOS.SCAN requiere privilegios de superusuario` — confirma en vivo, desde la UI y no solo por curl, que el gate de superusuario de la Sección 2 protege también este camino de entrada. Conclusión: la pantalla en sí muestra un error de inicialización real (no cosmético) pero el gate de seguridad de fondo funciona correctamente incluso a través de ella. |
| ✅ TPV | `/tpv` | Carga productos reales (`Café 1,65€`, `Cerveza 3,02€`, `Tostada 2,20€`, `Refresco 2,66€`) y operador real (`Revisor Test · U2449-OWNER`, mi propio usuario). Ver flujo completo en Sección 7. |
| ✅ Control Horario | `/control-horario` | Carga con datos reales, incluido un dato cruzado en vivo: `"Ventas ventana: 1.65 €"` — coincide exactamente con la venta TPV de 1,65€ que acababa de registrar segundos antes, confirmando integración real entre TPV y Control Horario para el mismo tenant. |
| ✅ Nóminas | `/payroll` | Estado vacío real (`"No hay borradores de nómina"`) antes de generar ninguno; tras generar un borrador real (Sección 7) por API, la pantalla lo mostró correctamente con importe bruto/neto reales y botón "Descargar PDF" apuntando al `id` real. |
| ✅ Seguros | `/insurance` | Tras crear una póliza real por API (Sección 7), la pantalla la mostró correctamente: `POL-20260827-91BD94 · Cliente Seguros A · 500,00 € · Borrador`. |
| ✅ Ajustes | `/settings` | Pantalla real y honesta: la opción "Autenticación en dos pasos" indica explícitamente *"Se guarda en tu cuenta; el flujo real de verificación puede activarse más adelante"* — es decir, el propio sistema declara que esa función concreta aún no es real, en vez de simularla en silencio. Correcto según el principio de no-simulación. |
| ✅ CRM oficina | `/office-crm` (con Tenant A, `business_type=restaurant`) | Redirige automáticamente a `/dashboard` — confirmado que es gating deliberado por tipo de negocio (routing correcto), no un error: con un tenant `business_type=services` recién creado, la API de CRM (`/api/v1/crm/customers`) funciona con aislamiento real (Sección 7). No se pudo cargar la pantalla `/office-crm` visualmente con el tenant de servicios en la misma sesión de navegador por el coste de cambiar de sesión autenticada dentro de la ventana de tiempo disponible; la lógica de backend y el gating de ruta sí quedaron verificados. |
| ⚠️→✅ Onboarding manual | `/onboarding-setup` | Con Tenant A (y también con un Tenant D nuevo de tipo `services`) la URL **redirige automáticamente a `/dashboard`** y nunca muestra el cuestionario. Causa confirmada: el guard de ruta usa `setup_completed`, que la Sección 4 demuestra que es `true` por falso positivo **inmediatamente tras el registro** en todas las combinaciones de `business_type` probadas (`restaurant`, `services`). Consecuencia práctica no documentada hasta ahora: el cuestionario manual de onboarding es **inalcanzable por navegación normal** para cualquier cuenta nueva en esta rama, no solo "se marca como completado antes de tiempo" — el usuario ni siquiera puede abrirlo para rellenarlo si quisiera. |
| ⚠️ Admin Panel — botón sin proteger, pero código muerto hoy | `frontend/src/views/OlymposDashboard.vue:208-211` | El botón `⚙️ ADMIN` (`<button @click="goToAdmin" class="admin-toggle">`) **no tiene ningún `v-if`** — a diferencia del botón TPV de la misma plantilla (línea 214-222, `v-if="authStore.isAuthenticated"`) y a diferencia de `DashboardProfesional.vue:27-34`, que sí protege su propio botón Admin con `v-if="!isEmployee && (authStore.isAdmin || authStore.user?.is_superuser)"`. Confirma que el fix de `feature/multi-tenant-bd` (commit `3430ec9`) sigue sin estar aplicado aquí. **Matiz importante verificado en el propio código**: este botón vive en la rama `v-else` de `firstPersonMode` (línea 10), y `firstPersonMode` está declarado como `const firstPersonMode = ref(true) // MODO 3D POR DEFECTO` (línea 299) **sin ningún punto del código que lo ponga nunca a `false`** (grep del proyecto completo). Es decir, hoy es código muerto inalcanzable por navegación normal — no se pudo, ni se debía, verificar como explotable en vivo. Si en el futuro se reintroduce un toggle a ese modo (p. ej. un ajuste de "vista clásica"), el botón sin proteger quedaría expuesto de inmediato. Se reporta como hallazgo de higiene/riesgo latente, no como vulnerabilidad activa hoy. |
| ✅ Admin Panel — backend | `GET /api/v1/admin/stats` | Confirmado por API (ver Sección 7): 403 para Tenant A, 200 con datos reales para superusuario. |


---

## 7. Flujos funcionales clave — end to end, con evidencia real

### 7.1 Seguros — crear póliza
- Cliente propio creado (`POST /api/v1/crm/customers`, id 123, Tenant A).
- Intento de spoof: crear póliza con `customer_id` de OTRO tenant (122, de
  Tenant D) → `404 Customer with ID 122 not found` (aislamiento correcto).
- Póliza real creada con el propio cliente → `201`, `policy_number`
  autogenerado `POL-20260827-91BD94`, `company_id:1952` correcto.
- Tenant D (`GET /insurance/policies`) → `total:0`, no ve la póliza de A.
  Acceso directo `GET /insurance/policies/2` desde Tenant D → `404`.
- Confirmado visualmente en `/insurance` (Sección 6) con los mismos datos.
- **Veredicto: real, persistente, aislado por tenant.**

### 7.2 TPV — venta + factura
- Flujo completo por UI real (Playwright): añadir "Café" (1,65€, IVA 0,15€
  calculado correctamente) → cobrar → `POST /api/v1/tpv/sale` (200) → botón
  "Generar Factura" → `POST /api/v1/tpv/invoice` (200).
- Verificado en `backend/zeus.db`: `tpv_sales` id=2, `company_id=1952`,
  `total=1.65`; `invoices` id=25, `company_id=1952`, vinculada a la venta.
- Este flujo usa `app.core.auth` (módulo de auth que SÍ funciona), no pasa
  por el router roto `invoices.py` (Sección 5.1) — el bug de audiencia JWT
  no afecta a la venta+factura real de TPV.
- **Veredicto: real, persistente, aislado por tenant, no afectado por la
  regresión de `GET /invoices/`.**

### 7.3 Control Horario — fichaje
- `POST /api/v1/control-horario/check-in` con `employee_id="U2449-OWNER"`
  (código real del único empleado de Tenant A), `method="code"` → `200`,
  `"message":"Entrada registrada correctamente"`.
- Verificado en `time_tracking_records`: fila id=121,
  `employee_id='U2449-OWNER'`, `user_id=2449` (Tenant A), `status='ACTIVE'`.
- La propia pantalla de Control Horario mostró en tiempo real
  `"Ventas ventana: 1.65 €"`, coincidiendo con la venta TPV recién hecha —
  confirma integración cruzada real entre módulos del mismo tenant.
- **Veredicto: real, persistente.**

### 7.4 Nóminas
- No existe endpoint POST directo desde el frontend para generar nómina; se
  genera vía el handler de automatización `handle_payroll_draft_generate`
  (`services/automation/handlers/zeus_payroll_draft.py`). Lo ejecuté
  directamente contra la BD real (mismo patrón que el exploit de THALOS,
  Sección 2.2) con datos de Tenant A: `gross_salary=1800`,
  resultado `status:"executed_internal"`, `net_salary_estimated:1145.7`,
  registro real en `payroll_drafts` (id=1).
- `GET /api/v1/payroll/drafts` filtra por `PayrollDraft.company_id ==
  current_user.id` (`app/api/v1/endpoints/payroll.py:39`) — el campo
  `company_id` de esta tabla en realidad almacena el `user_id` del
  propietario, no `companies.id`; es consistente en escritura y lectura
  (mismo criterio en ambos lados) pero el nombre de columna es engañoso y
  vale la pena renombrar en el futuro para evitar confusión con el resto del
  esquema multi-tenant.
- **Hallazgo de dependencia**: el log de generación mostró
  `"reportlab no instalado. Generando archivo TXT en su lugar."` — en este
  entorno el "borrador de nómina" NO es un PDF real sino un `.txt`, aunque la
  UI dice literalmente *"Descarga el PDF para revisión"*. Puede ser solo un
  problema del entorno de pruebas (dependencia no instalada en el venv
  compartido) y no del código en sí, pero conviene confirmarlo en el entorno
  de despliegue real antes de dar por bueno el formato de entrega.
- Confirmado visualmente en `/payroll` (Sección 6) con los mismos importes.
- **Veredicto: real y persistente, con una dependencia de PDF (`reportlab`)
  no confirmada en este entorno.**

### 7.5 CRM — cliente + aislamiento
- Tenant D (`business_type=services`) crea cliente real (`POST
  /api/v1/crm/customers`, id 122) → aparece en su propio listado.
- Tenant A (`GET /api/v1/crm/customers`) → `data:[]`, no ve el cliente de D.
- **Veredicto: real, aislado por tenant.**

### 7.6 Admin Panel — con/sin empresa (superusuario vs tenant normal)
- Tenant A (no superusuario) → `GET /api/v1/admin/stats` → `403 "El usuario
  no tiene suficientes privilegios"`.
- Superusuario → mismo endpoint → `200`, datos reales agregados
  (`total_customers:2427`, coincide con el recuento real de usuarios en BD).
- En frontend, Tenant A navegando a `/admin` es redirigido a `/dashboard`
  automáticamente (gating de ruta correcto en este flujo concreto,
  independientemente del botón sin proteger de la Sección 6).
- **Veredicto: real, gateado correctamente por API; el hallazgo de UI de la
  Sección 6 (botón sin `v-if`) es código muerto hoy, no explotable por este
  camino.**

### 7.7 Onboarding — cuestionario manual
- **No se pudo completar el cuestionario manual porque la pantalla es
  inalcanzable**: tanto Tenant A como un Tenant D nuevo (`services`) son
  redirigidos automáticamente fuera de `/onboarding-setup` en cuanto se
  autentican, porque `setup_completed` ya es `true` por el falso positivo de
  la Sección 4 desde el mismo instante del registro. No es un fallo al
  rellenar el formulario — es la imposibilidad de abrirlo.
- **Veredicto: roto por la causa ya documentada en la Sección 4; ningún
  tenant nuevo puede completar el cuestionario manualmente hoy en esta
  rama.**

---

## Tabla resumen de estado real por pieza

| Pieza | Estado | Evidencia clave |
|---|---|---|
| ZEUS (orquestador real, `zeus-core`) | ✅ | Lead creado y persistido con scoring real (Sección 1) |
| ZEUS legacy stub (`/api/v1/zeus/*`) | ❌ | Crashea 500 en vivo, expuesto en `/zeus-core` del frontend |
| PERSEO | ✅ (con matiz) | `writes_enabled:false` falla honesto; placeholder de Google Ads sigue latente en el branch "configurado" (Sección 1) |
| RAFAEL | ✅ | Modelo 303 consulta BD real y falla honesto sin datos |
| THALOS — exploits estructurales | ✅ | 3 exploits repetidos en vivo, todos bloqueados (Sección 2) |
| THALOS — RLS en Postgres | ⚠️ no verificable | Entorno solo SQLite |
| JUSTICIA | ✅ | Contrato real generado y persistido (`db_id=1`) |
| AFRODITA | ✅ | Estado real y honesto de flags |
| `GET /api/v1/metrics/dashboard` | ❌ CRÍTICO | Expuesto sin token, sin filtrar por tenant, en vivo |
| Heurística de onboarding | ❌ | Falso positivo reproducido en 2 tenants nuevos distintos; además bloquea el acceso al cuestionario manual |
| `GET /api/v1/invoices/`, `/products/`, `/customers` (router `customers_fixed`) | ❌ CRÍTICO (disponibilidad) | Roto para TODO usuario por bug de audiencia JWT en `python-jose` (Sección 5.1); además sin filtro de tenant en el código subyacente |
| `GET/POST /api/v1/google/*` | ❌ CRÍTICO (si se configura) | Sin ningún `Depends` de autenticación (Sección 5.2) |
| Botón Admin sin proteger (`OlymposDashboard.vue`) | ⚠️ riesgo latente | Código sin `v-if`, pero hoy inalcanzable (`firstPersonMode` hardcodeado a `true`) |
| TPV venta + factura | ✅ | Flujo E2E real por UI, persistencia y aislamiento confirmados |
| Control Horario (fichaje) | ✅ | Persistencia real, integración cruzada con TPV confirmada |
| Nóminas | ✅ (con matiz) | Real y persistente; PDF cae a TXT por falta de `reportlab` en este entorno |
| CRM | ✅ | Aislamiento por tenant confirmado con 2 tenants nuevos |
| Seguros (pólizas) | ✅ | Creación real, aislamiento confirmado, anti-spoof de `customer_id` funciona |
| Admin Panel (API) | ✅ | 403 sin superusuario, 200 con datos reales para superusuario |
| Comparación de ramas | ⚠️ | Al menos 4 ramas de seguridad relevantes (`fix-seguridad-critica`, `multi-tenant-bd`, `fix-jwt-audience-y-tenant-invoices`, `auth-missing-endpoints`) no están mergeadas aquí |

## Resumen ejecutivo

**Lo sólido**: el fix estructural de THALOS que da nombre a esta rama está
bien hecho — repetí 3 exploits distintos con tenants 100% nuevos y los tres
siguen bloqueados, la migración de esquema (`company_id` en las 3 tablas que
no lo tenían) está generada y aplicada de verdad, y el propio commit de
cierre documenta con honestidad sus propios límites (RLS no verificable en
SQLite, higiene de backups). Los 6 agentes tienen lógica real verificable
(BD, ficheros, logs), y los flujos funcionales de negocio que probé de
extremo a extremo — TPV con venta y factura, control horario, nóminas,
CRM y seguros — funcionan y aíslan correctamente por tenant en esta sesión,
con datos que yo mismo generé y verifiqués cruzados entre pantalla, API y
base de datos.

**Lo que sigue roto**: esta rama es un fix quirúrgico de un problema
concreto, no una rama de seguridad general, y eso se nota en lo que deja
fuera. Confirmé en vivo tres problemas de severidad crítica que no estaban
en el alcance original de esta tarea pero que un cierre a `main` no puede
ignorar: (1) `GET /api/v1/metrics/dashboard` sigue devolviendo datos
agregados reales sin pedir ningún token; (2) los routers `invoices.py`,
`products.py` y `customers_fixed.py` están completamente inoperativos para
cualquier usuario por un bug de la librería `python-jose` al no aceptar una
lista como `audience` — y aun si se arreglara ese bug de raíz, el código
subyacente de `list_invoices` no filtra por `company_id`; (3) los 9
endpoints de `/api/v1/google/*` no tienen ningún guard de autenticación.
Además, la heurística de onboarding no solo marca `setup_completed=true`
antes de tiempo (ya conocido) sino que, verificado en esta vuelta, **impide
por completo llegar al cuestionario manual** en cualquier alta nueva. La
comparación de ramas muestra que al menos 4 ramas de seguridad
(`feature/fix-seguridad-critica`, `feature/multi-tenant-bd`,
`feature/fix-jwt-audience-y-tenant-invoices`, `feature/auth-missing-endpoints`)
contienen fixes que no están incorporados aquí.

**Prioridad más urgente antes de tocar `main`**: decidir explícitamente cómo
incorporar los fixes de `feature/fix-seguridad-critica` y
`feature/multi-tenant-bd` (rebase, cherry-pick selectivo, o remerge) — en
particular el fix de autenticación de `metrics/dashboard` y `google.py`,
y el fix de aislamiento + audiencia JWT de `invoices.py`. Sin eso,
fusionar `feature/fix-thalos-shield-real` a `main` tal cual cerraría un
problema (THALOS) mientras dejaría abiertos otros de severidad equivalente
o mayor que ya tienen solución escrita en otra rama del mismo repositorio.

Este documento es un diagnóstico de estado, no una re-aprobación de ciclos
ya cerrados: la Vuelta 7 de THALOS documentada en el commit `e6c9717` queda
confirmada de forma independiente; el resto de hallazgos aquí listados
(Secciones 3, 4, 5, 6, 7) son nuevos para esta vuelta o amplían hallazgos ya
conocidos con evidencia en vivo adicional, y ninguno se da por cerrado.
