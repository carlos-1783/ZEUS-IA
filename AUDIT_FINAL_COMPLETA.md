# AUDIT_FINAL_COMPLETA.md

**Fecha**: 2026-08-24
**Rama**: `feature/rediseno-completo` (worktree `agent-a8873985b2803de19`), HEAD en `622d431` al empezar.
**Alcance del encargo**: auditoría final completa, página por página, botón por botón, como
usuario real con Playwright (navegador integrado, no solo lectura de código), de toda la
app, más 4 hallazgos pendientes de sesiones anteriores a verificar en vivo.
**Sin merge ni push a `main`** en ningún momento de esta sesión. No se tocó lógica de
negocio ni frontend de producción — el único cambio a `frontend/index.html` (CSP temporal
para permitir que el navegador de pruebas hablara con un backend/frontend aislados en
puertos no estándar) se aplicó y **revirtió explícitamente** antes de cerrar esta sesión;
confirmado con `git status`/`git diff` limpios justo antes de escribir este informe.

---

## 0. Entorno de verificación

- Confirmado al empezar: `git branch --show-current` → `feature/rediseno-completo`,
  `git log -1` → `622d431`. Coincide con lo indicado en el encargo.
- **Puertos 8000/5173 ya ocupados por otro agente** (`curl` confirmó un backend y un
  frontend reales corriendo ahí, sirviendo un checkout/rama distintos — no se tocaron ni
  se mataron esos procesos). Se levantó un backend y un frontend propios y aislados de
  este worktree en puertos alternativos:
  - Backend: `uvicorn app.main:app --port 8010`, `DATABASE_URL=sqlite:///./zeus.db`
    (la BD real de desarrollo de este worktree, no la BD de tests `zeus_test.db`),
    `ENVIRONMENT=development`, `PYTHONIOENCODING=utf-8`.
  - Frontend: `node_modules/.bin/vite --port 5180 --strictPort` ejecutado directamente
    dentro de `.claude/worktrees/agent-a8873985b2803de19/frontend` (ya tenía `node_modules`
    propio de una ronda anterior, no se reinstaló), con `VITE_API_URL=http://localhost:8010/api/v1`.
  - **Confirmado que el frontend servido era el de este worktree y no un checkout
    compartido**: `curl http://localhost:5180/src/views/TPV.vue | grep table-status-dot`
    devolvió el marcador — coincide con el commit real de este worktree.
  - La CSP de `frontend/index.html` solo permite `connect-src` a `localhost:8000`/`5173`
    (hardcoded). Se editó temporalmente para añadir `8010`/`5180`, se verificó todo el
    trabajo de esta sesión con esa CSP ampliada, y se **revirtió a su valor original**
    (`git checkout -- frontend/index.html` primero, y una segunda vuelta editar+revertir
    al retomar pruebas) antes de cerrar. Estado final confirmado: `git status` solo
    muestra `.claude/` sin trackear, cero diff en `frontend/index.html`.
  - El HMR de Vite está hardcoded a puerto 5173 (`vite.config.ts`, `hmr.port: 5173`)
    independientemente del `--port` real usado; esto genera ruido constante en consola
    (`WebSocket connection to 'ws://localhost:5173/' failed`, `CSP violation` repetida) en
    **todas** las pantallas de esta sesión. Es 100% un artefacto de este entorno de
    pruebas (falta de recarga en caliente), no un bug de la app — se excluyó de todos los
    análisis de consola de este informe filtrando ese patrón.
- Cuentas de prueba, todas creadas de verdad vía `POST /api/v1/auth/register` (no inserts
  directos, salvo la promoción a superusuario que sí requiere UPDATE directo en BD porque
  no existe endpoint público para ello, por diseño correcto):
  - `audit.restaurant@example.com` — `business_type=restaurant`, tenant normal.
  - `audit.superadmin@example.com` — promovido a superusuario y **desvinculado de su
    empresa** (`DELETE FROM user_companies`) para reproducir el hallazgo 3.
  - `audit.hospitality.postpago@example.com` — creado vía el endpoint real de
    post-pago `POST /onboarding/create-account` (el que llama `Checkout.vue` tras un pago
    Stripe real), `sector=restaurante`, para reproducir el hallazgo 2 por la vía de pago.
  - `audit.admin2@example.com` — superusuario **con** empresa (para poder probar Admin
    Panel sin caer en la trampa del hallazgo 3).
  - `audit.office@example.com` / `audit.office2@example.com` — `business_type=services`
    (→ `company_type=office`), dos tenants independientes para CRM y aislamiento
    multi-tenant.
- Suite de tests backend: **no se re-ejecutó** en esta sesión porque no se modificó ningún
  archivo de `backend/` ni `frontend/` de forma permanente (el único cambio, la CSP, se
  revirtió). El baseline conocido y ya confirmado estable dos veces seguidas por la sesión
  anterior (`7 failed, 214 passed, 2 skipped, 3 errors`, ver sección 14 de
  `AUDIT_REDISENO_COMPLETO.md`) no tiene motivo para haber cambiado. **No verificado de
  nuevo por mí** — si se quiere una confirmación fresca, hay que ejecutar la suite
  explícitamente.

---

## 1. Los 4 hallazgos pendientes — verificados en vivo

### 1.1 Puente venta TPV → factura (`feature/facturacion-tpv-real`)

**Veredicto: OK, confirmado en vivo de extremo a extremo, con cuenta y datos propios.**

Repetí yo mismo el flujo completo con Playwright, sin reutilizar nada de sesiones
anteriores:

1. Login real como `audit.restaurant@example.com` en `/tpv`.
2. Clic en el producto real "Café" (1,65 €) → carrito con subtotal 1,50 €/IVA 0,15 €.
3. Clic real en "Revisar y proceder al pago" → "Confirmar y proceder al pago" →
   "Finalizar pago de €1,65" → `POST /api/v1/tpv/sale` → **200 OK**, ticket real
   `TICKET_20260824195402`.
4. Clic real en "Generar Factura" → `POST /api/v1/tpv/invoice` → **200 OK**.
5. **Confirmado por SQL directo** contra `zeus.db` (no solo la respuesta JSON):
   `invoices` id=9, `invoice_number='FRA-TICKET_20260824195402'`, `company_id=236`,
   `tpv_sale_id=7`, `subtotal=1.5`, `tax_amount=0.15`, `total=1.65`, `status='PAID'` —
   coincide exactamente con la venta.
6. Caso negativo: `POST /tpv/invoice {"ticket_id":"TICKET_NO_EXISTE_AUDIT_999"}` →
   **404** real.
7. Idempotencia: repetir la llamada con el mismo `ticket_id` → `already_existed:true`,
   mismo `invoice.id=9`, no duplica.
8. Aislamiento multi-tenant: con el token de `audit.hospitality.postpago@example.com`
   (empresa distinta) intentando facturar el ticket de `audit.restaurant` →
   **403 "La venta no pertenece a su empresa."**

Conclusión: el puente sigue funcionando correctamente tras la fusión de las 3 ramas en
este worktree. No es solo lo que dice el audit doc anterior — lo repetí yo mismo con mis
propios datos y confirmé el resultado en BD.

### 1.2 Heurística de onboarding (`setup_completed` inferido) — CONFIRMADO, y más grave de lo descrito

**Veredicto: hallazgo CRÍTICO confirmado en vivo — severidad más alta que la descripción original.**

La descripción original decía "casi nunca activa el wizard". Tras rastrear el código y
reproducirlo con 3 cuentas reales distintas en esta sesión, el alcance real es: **el
wizard de onboarding no se activa nunca para ningún registro estándar**, de ningún tipo
de negocio.

**Causa raíz exacta** (`backend/services/onboarding_engine.py`,
`apply_registration_onboarding` → `_apply_roce_automation_seed` →
`_create_owner_employee_and_default_schedules`, líneas 136-261): esta función se ejecuta
**de forma síncrona, en la misma transacción que crea el usuario**, para **cualquier**
`business_type` (`restaurant`/`retail`/`services`), y crea automáticamente:
- 1 `CompanyEmployee` con `role_title="owner"` (`employee_code=f"U{user.id}-OWNER"`).
- Turnos por defecto Lunes-Viernes 09:00-17:00 en `employee_schedules`.

Y en `app/api/v1/endpoints/auth.py::onboarding_status` (líneas 590-618), el flag
`setup_completed` se calcula así:
```python
setup_completed = questionnaire_completed or operational_profile_completed or user_onboarding_backup
if not setup_completed and co:
    ce_count = ...  # cuenta company_employees
    tpv_products = ...
    if (pilot_company or ce_count >= 1 or (tpv_products >= 1 and tpv_business_profile) or has_profile_data):
        setup_completed = True
        setup_inferred = True
```
Como **siempre** hay al menos 1 `CompanyEmployee` (el "owner" autogenerado) desde el
instante mismo del registro, `ce_count >= 1` es **siempre verdadero**, y
`setup_completed` se marca `True` (`setup_inferred: True`) sin que el usuario haya
completado nunca el cuestionario real (horario semanal, canales, email del gestor
fiscal, IBAN, empleados reales).

**Reproducido en vivo, 3 veces, con cuentas 100% propias de esta sesión:**

| Cuenta | Vía de alta | `questionnaire_completed` | `setup_completed` | `setup_inferred` |
|---|---|---|---|---|
| `audit.restaurant@example.com` (`business_type=restaurant`) | `POST /auth/register` directo | `false` | **`true`** | **`true`** |
| `audit.hospitality.postpago@example.com` (`sector=restaurante`) | `POST /onboarding/create-account` (el mismo endpoint real que llama `Checkout.vue` tras un pago Stripe real) | `false` | **`true`** | **`true`** |
| `audit.admin2@example.com` (`business_type=services`) | `POST /auth/register` directo | `false` | **`true`** | **`true`** |

Confirmado también **en el propio navegador**: navegando con `force:true` (recarga dura,
no `router.push`) a `/onboarding-setup` con la sesión de `audit.office@example.com` ya
autenticada, el guard redirige inmediatamente a `/dashboard` sin mostrar el wizard nunca
— exactamente el síntoma descrito, visto con mis propios ojos en el navegador, no solo
por API.

**Impacto real, concreto**: en las 3 cuentas de prueba, `rafael_email_ready: false`,
`has_iban_on_file: false`, `email_gestor_fiscal: null`, y para las cuentas hospitality
además `employees_seed_defined: false`/`company_employees_count: 0` en la clave interna
del check aunque el owner-placeholder exista (la validación separa "empleados reales
capturados en el wizard" de "el owner autogenerado"). Es decir: **el 100% de las cuentas
nuevas, de cualquier vertical (hostelería u oficina), aterrizan directo en `/dashboard`
sin haber configurado nunca**: email del gestor fiscal para RAFAEL (necesario para el
envío real de facturación), IBAN/`tax_id`/`legal_name`, empleados reales (solo existe el
placeholder "owner" con turno ficticio 09:00-17:00 L-V), canales de comunicación, ni
horario real del negocio. Esto degrada de forma silenciosa y sistémica RAFAEL (fiscal),
Control Horario (turnos ficticios) y Nóminas/Payroll (solo ve al owner placeholder) para
absolutamente todo cliente nuevo.

**Archivos**: `backend/services/onboarding_engine.py:136-261` (seed síncrono en registro),
`backend/services/global_company_bootstrap.py:171-203,298-314` (seed duplicado, mismo
efecto, en el flujo de post-pago/Stripe), `backend/app/api/v1/endpoints/auth.py:590-618`
(heurística que no distingue "empleado real" de "placeholder autogenerado").
**Severidad: crítica** — no es un bug de UI, es una pérdida sistémica de un paso de
negocio para el 100% de altas.

### 1.3 Bug de superusuario sin empresa (`Login.vue` / `resolvePostAuthPath`)

**Veredicto: confirmado, vivo, reproducido con cuenta propia — coincide con lo ya descrito por el revisor de la Ronda 4.**

Código confirmado (`frontend/src/utils/postAuthRedirect.ts`, función
`resolvePostAuthPath`, líneas 33-62): **no recibe ni comprueba `isAdmin` en ningún
punto** — solo mira `token` y el resultado de `/auth/onboarding/status`. `Login.vue`
(líneas 162 y 222) la llama sin pasar información de rol. En cambio, el guard del router
(`frontend/src/router/index.js`, líneas 555-559) sí exime explícitamente a los admins
(`!authStore.isAdmin`) de la comprobación de onboarding — pero esa exención vive en el
router, no en `Login.vue`, así que nunca llega a aplicarse en el primer login.

**Reproducido en vivo con cuenta propia** (`audit.superadmin@example.com`, promovido a
`is_superuser=1` y con su fila de `user_companies` borrada, exactamente el escenario que
pide el encargo):
- `GET /auth/me` → `is_superuser: true`, `company_id: null`.
- `GET /auth/onboarding/status` → `company_linked: false`, `setup_completed: false`.
- `POST /auth/onboarding/profile` (lo que intentaría enviar el wizard) →
  **`{"detail":"Usuario sin empresa vinculada. Completa el registro antes de configurar el perfil."}`**
  — es decir, aunque llegara al wizard, **no hay forma de completarlo nunca** (no existe
  empresa a la que asociar los datos).
- Revisado el template de `OnboardingSetup.vue` completo: **no tiene ningún enlace de
  navegación, botón "omitir" ni "cerrar sesión"** — solo el stepper del wizard. Un
  superusuario sin empresa que aterriza ahí queda con una pantalla de formulario que
  jamás puede enviarse con éxito y sin salida visible en la UI (la única forma de salir
  es escribir manualmente `/dashboard` en la barra de direcciones, lo cual sí funciona
  porque el guard del router exime a los admins — pero es un escape no descubrible desde
  la propia interfaz).

**Impacto real**: cualquier superusuario real de producción que no tenga una `Company`
asociada (cuenta de plataforma pura, o cuenta cuyo vínculo se rompió) queda con una
pantalla de configuración inicial rota tras iniciar sesión, sin ningún control visible
para salir de ella.

**Archivos**: `frontend/src/utils/postAuthRedirect.ts:33-62` (fuente del bug — falta el
parámetro `isAdmin`), `frontend/src/views/auth/Login.vue:162,222` (llamada sin ese dato),
`frontend/src/views/OnboardingSetup.vue` (plantilla íntegra sin escape visible).
**Severidad: alta** (afecta solo a superusuarios sin empresa, pero los deja en una
pantalla rota sin salida descubrible).

### 1.4 `encryption_status` simulado en THALOS.SHIELD

**Veredicto: CONFIRMADO — simulación pura, sin lógica real, reproducida en vivo por API y en la UI real.**

`backend/app/core/zeus_agents.py`, clase `ThalosAgent._execute_command` (líneas 355-410):
el comando `THALOS.SHIELD` devuelve un diccionario **100% hardcodeado** —
`"encryption_status": "activo"`, `"threats_blocked": 0`, `"jwt_oauth2": "configurado"` —
sin ninguna consulta a BD, sin comprobar nada real de cifrado ni JWT. `THALOS.BLOCK`
devuelve literalmente los mismos dos IPs de ejemplo (`192.168.1.100`, `10.0.0.50`)
siempre, sin usar el `data` recibido. `THALOS.SCAN` devuelve `vulnerabilities_found: 0`
fijo.

**Confirmado en vivo, no solo leyendo código:**
- Endpoint real y autenticado: `POST /api/v1/zeus/execute` (requiere
  `get_current_active_user`, `401` sin token — confirmado). No filtra por tenant en
  absoluto: llamado con el token de `audit.restaurant@example.com` y con el de
  `audit.superadmin@example.com` (dos tenants/cuentas distintas), la respuesta es
  **byte-por-byte idéntica** salvo el `timestamp` — cero lógica dependiente del llamador.
- Reachable desde el frontend real: `frontend/src/views/ZeusCore.vue` (ruta `/zeus-core`,
  registrada en el router, sin enlace de navegación visible desde el dashboard pero
  accesible por URL directa) llama a este mismo endpoint. Verificado **en el propio
  navegador**: escribí el comando `THALOS.SHIELD` en el terminal de `/zeus-core` y lo
  ejecuté — la tarjeta THALOS pasó a "ACTIVE" y se mostró el mensaje "ZEUS SHIELD
  activado - Protección máxima" con voz simulada, exactamente como si hubiera ocurrido
  una acción de seguridad real.
- Por contraste: el workspace REAL de THALOS (el que se abre desde "Interactuar" en el
  dashboard, `ThalosWorkspace.vue` → `/api/v1/thalos/v1/execute`) sí se etiqueta a sí
  mismo explícitam% como `REAL_SAFE` / `REAL` / `EJECUCIÓN REAL` en la UI — confirmando
  que existe una capa real y separada, y que el problema es específicamente el stub
  legacy de `zeus_agents.py`, que sigue vivo y accesible en paralelo.

**Hallazgo incidental en el mismo sitio**: al probar el comando `ZEUS.ACTIVAR` en la
misma pantalla `/zeus-core`, el propio sistema registra en su log interno un error real:
`Error activando Núcleo ZEUS: 1 validation error for ZeusResponse agent Field required`
— un bug de verdad (el modelo `ZeusResponse` exige el campo `agent` y el comando
`ZEUS.ACTIVAR` no lo incluye en su respuesta), no relacionado con la simulación de
THALOS pero visto de pasada.

**Archivos**: `backend/app/core/zeus_agents.py:355-410` (los 3 comandos de THALOS
simulados), `backend/app/api/v1/endpoints/zeus_core.py` (endpoint `/zeus/execute`, sin
tenant), `frontend/src/views/ZeusCore.vue` (UI real que lo consume).
**Severidad: crítica** — es middleware de seguridad simulado, expuesto por API real y
autenticada, capaz de hacer creer a un usuario (o a un auditor externo) que se activó
cifrado/protección real cuando no ocurrió nada. Viola directamente la regla no negociable
de "prohibidas las respuestas simuladas" y "cada agente = proceso real".

---

## 2. Barrido pantalla por pantalla

Metodología real esta sesión: login real con cuentas propias, navegación dura
(`force:true`, recarga completa) para cada ruta, lectura de consola filtrando el ruido de
HMR ya documentado en la sección 0, y para las pantallas con escritura, interacción real
+ recarga para confirmar persistencia en BD (no solo ausencia de error).

| Pantalla | Verificación realizada | Veredicto |
|---|---|---|
| **Login / Registro** | 2 registros reales (`POST /auth/register`), login real vía formulario con clic (no solo Enter — Enter no envía el formulario, ver nota abajo), token real, redirect a dashboard | OK, con nota menor |
| **Dashboard (`/dashboard`, `OlymposDashboard.vue`)** | KPIs reales (6 agentes, tareas 24h reales), botón "Interactuar" abre modal real por agente | OK |
| **`/agents`** | Lista real de 6 agentes con estado "Online" | OK |
| **Workspace RAFAEL** (modal "Interactuar") | Abrió con datos reales, tabs Chat/Actividad/Workspace, TeamFlow real vacío, automatización fiscal con fallback manual real cuando la cámara no está disponible | OK |
| **Workspace THALOS** (modal "Interactuar") | Abrió con datos reales, historial de tareas real con timestamps reales, autoetiquetado `REAL_SAFE`/`EJECUCIÓN REAL` | OK (contraste positivo con el hallazgo 1.4) |
| Workspaces PERSEO / JUSTICIA / AFRODITA / ZEUS CORE (modal) | **No verificados en esta sesión** por límite de tiempo — sí verificados extensamente en rondas anteriores (ver `AUDIT_REDISENO_COMPLETO.md` secciones 2.4-2.9, 9.6) | No verificado de nuevo (riesgo bajo, sin cambios de código desde entonces) |
| **`/zeus-core`** (legacy, standalone) | Real, reachable, comando `ZEUS.ACTIVAR` con error real (ver 1.4), `THALOS.SHIELD` simulado (ver 1.4), botón "SALIR" hace logout real | Hallazgo crítico (1.4) + hallazgo incidental (ZEUS.ACTIVAR) |
| **TPV** | Flujo de venta completo + factura, ver sección 1.1 | OK |
| **Control Horario** | Datos reales (1 empleado, alertas reales `EMPLEADO_NO_FICHA`/`TURNO_SIN_CUBIERTA`, coste laboral real, integración real con ventas TPV — "Ventas ventana: 1.65 €" coincide con la venta hecha en 1.1) | OK |
| **Nóminas (`/payroll`)** | Estado vacío real, sin datos inventados | OK |
| **Seguros (`/insurance`)** | Formulario real "Nueva póliza", combo de clientes vacío real (sin clientes CRM para ese tenant — correcto, no fuerza datos falsos) | OK |
| **Onboarding (`/onboarding-setup`)** | Confirmado inalcanzable en la práctica por el hallazgo 1.2 — navegación directa redirige a dashboard sin mostrar el wizard | Ver hallazgo 1.2 |
| **Admin Panel (`/admin`)** | Con superusuario **sin** empresa: bloqueado por el hallazgo 1.3 (queda atrapado antes de llegar). Con superusuario **con** empresa (`audit.admin2`): acceso real, KPIs reales (396 clientes reales, ingresos reales), pestaña Clientes con datos reales de BD (incluidas las cuentas creadas en esta misma sesión) | OK (con la cuenta correcta) |
| **CRM oficina (`/office-crm`)** | Creado un cliente real ("Cliente Auditoria SL"), confirmado que **persiste tras recarga dura** (no solo ausencia de error) — ver captura de red `POST → 201 Created`, y confirmado por lectura del formulario tras `navigate force:true` que los datos siguen ahí. Aislamiento multi-tenant confirmado con una 2ª cuenta `office` independiente: `GET /crm/customers` devuelve `[]` (no ve el cliente del otro tenant) | OK |
| **Ajustes (`/settings`)** | Carga real (tema, idioma, RAFAEL — gestor fiscal, seguridad) con valores reales de `GET /settings` | Cargado; **no se probó el guardado de "Guardar gestor fiscal" end-to-end en esta sesión** (ya lo dejó como pendiente la Ronda 3 también) |
| **Analíticas — Tareas 24h (`/analytics/tasks`)** | Real: `client_created / CRM / success`, coincide con la creación del cliente CRM de esta misma sesión | OK |
| **Analíticas — Eficiencia (`/analytics/efficiency`)** | Real: 100%, 1 evento 24h, 1 éxito — coincide también con la actividad real generada en esta sesión | OK |
| **Alertas (`/alerts`)** | Real: "Total: 0" (sin alertas para este tenant, estado vacío genuino) | OK |
| **Automatizaciones (`/automations`, `/automations/audit`)** | **No verificadas en esta sesión** por límite de tiempo | No verificado |
| **Facturación** | No existe una pantalla dedicada de "Facturación" en el router (`grep` de rutas confirmó que no hay ninguna ruta `/invoices` ni "facturación" registrada) — la facturación vive dentro del workspace de RAFAEL ("Paquetes fiscales") y del flujo TPV→factura ya verificado en 1.1. **Hallazgo confirmado, pre-existente, no introducido aquí**: `GET /api/v1/invoices/` sigue devolviendo `401 "No se pudieron validar las credenciales"` incluso con un token recién emitido y válido — reproducido en esta sesión con un token fresco de `audit.restaurant`. Coincide exactamente con el bug de audiencia JWT ya documentado en `AUDIT_FACTURACION_TPV_REAL.md` (`settings.JWT_AUDIENCE` es una lista, `python-jose` exige string) — **sigue sin arreglar**, y confirma que hoy no hay ninguna forma de listar facturas vía ese endpoint para ningún tenant | Hallazgo confirmado vivo (pre-existente) |
| **ScanHub (`/scan`), SystemStatusPanel (`/system/status`)** | **No verificadas en esta sesión** — ya documentadas en la Ronda de remate anterior como pantallas sin migrar al sistema de diseño (tema oscuro propio), pero sin evidencia de que estén rotas funcionalmente | No verificado |

**Nota sobre login con Enter**: al escribir la contraseña y pulsar `Return` en el campo de
contraseña, el formulario **no se envía** — hay que hacer clic explícito en el botón
"Iniciar sesión". No confirmé si esto es por diseño (quizá el campo no está dentro de un
`<form>` con submit nativo, o hay un `@keyup.enter` que falta) o es un descuido de UX
menor. **No investigado a fondo — hallazgo menor, no bloqueante**, señalado para que se
decida si merece arreglo.

---

## 3. Hallazgos nuevos encontrados de paso (no pedidos explícitamente)

1. **`ZEUS.ACTIVAR` rompe con error de validación Pydantic** (`ZeusResponse agent Field
   required`) en `/zeus-core` — ver sección 1.4. Menor, pantalla legacy/huérfana.
2. **`GET /api/v1/invoices/` sigue devolviendo 401 con tokens válidos** (bug de
   audiencia JWT, `app/core/security.py`) — confirmado todavía vivo, pre-existente,
   documentado ya en otra rama (`feature/fix-jwt-audience-y-tenant-invoices`). Bloquea
   cualquier listado real de facturas para cualquier tenant hasta que se arregle.
3. **Enter no envía el formulario de login** — hay que hacer clic explícito en el botón.
   Menor.
4. **No hay ningún control de "cerrar sesión" visible en el dashboard principal
   (`OlymposDashboard.vue`) ni en `MainLayout`/`AdminPanel` para el flujo real que ve un
   usuario normal** — el único "SALIR" encontrado en toda la sesión vive en la pantalla
   legacy `/zeus-core`, no en ningún punto de la navegación principal. Tuve que navegar
   manualmente a `/zeus-core` para poder cerrar sesión y cambiar de cuenta de prueba
   durante esta auditoría. Si esto también le pasa a un usuario real, no tiene forma
   descubrible de cerrar sesión desde el dashboard, TPV, CRM, Control Horario, Nóminas,
   Seguros ni Ajustes. **Verificar si existe en algún menú que no encontré (posible, dado
   el viewport reducido de esta sesión — ver limitaciones) o si es un hueco real de UX.**
5. Confirmado (no nuevo, pero re-confirmado con datos propios) que el ruido de consola
   `WebSocket ... 5173 ... Content Security Policy` es 100% un artefacto de este entorno
   de pruebas multi-worktree, no de la app — para que quien revise no lo cuente como
   hallazgo.

---

## 4. Qué NO se pudo verificar (honesto, no se da por bueno)

- **Suite de tests backend**: no se volvió a ejecutar en esta sesión (no se tocó código
  de forma permanente). El baseline conocido es `7 failed, 214 passed, 2 skipped, 3
  errors`.
- **Workspaces PERSEO, JUSTICIA, AFRODITA y ZEUS CORE** (vía modal "Interactuar"): no
  reprobados en esta sesión, confiando en la verificación extensa de rondas anteriores
  (mismo código, sin cambios desde entonces).
- **`/automations`, `/automations/audit`, `/scan`, `/system/status`**: no visitadas en
  esta sesión.
- **Guardado real de "Guardar gestor fiscal" en Ajustes**: cargado pero no se probó el
  ciclo completo guardar → recargar → confirmar persistencia en esta sesión.
- **Acciones irreversibles de Admin Panel** (Desactivar/Eliminar cuenta): no ejecutadas,
  por no mutar destructivamente datos de prueba sin necesidad — mismo criterio que
  rondas anteriores.
- **Viewport real de escritorio ancho** (>1280px): el navegador de esta sesión está fijo
  en ~629px de ancho, igual que en sesiones anteriores — no se pudo confirmar visualmente
  el hallazgo ya documentado de "franjas oscuras en viewports anchos" ni descartar que
  exista un control de "cerrar sesión" que solo aparece en un layout de escritorio más
  ancho (ver hallazgo nuevo 4 de la sección 3 — podría ser un falso positivo causado por
  esta limitación de viewport, no lo doy por confirmado al 100% como ausencia real).
- **`resolvePostAuthPath` en el momento exacto del primer login** (sección 1.3): no pude
  hacer clic en el formulario de login estando ya autenticado como el superusuario sin
  empresa (el `onMounted` de `Login.vue` redirige antes de poder interactuar) — la
  reproducción se hizo con las mismas llamadas API que ese código ejecuta
  (`/auth/onboarding/status`, `/auth/onboarding/profile`) más lectura línea a línea del
  código fuente real, no con un clic literal en el botón "Iniciar sesión" de esa cuenta
  específica. Es una reproducción equivalente y determinista (mismo código, mismos
  inputs), pero no un clic físico grabado en vídeo.

---

## 5. Resumen ejecutivo

- Los 4 hallazgos del encargo: **los 4 confirmados en vivo**, con evidencia real (API +
  BD + UI donde fue posible). El hallazgo 2 (onboarding) resultó ser **más grave** de lo
  descrito originalmente: no es "casi nunca", es "nunca" para cualquier registro
  estándar, con causa raíz identificada con precisión de línea de código.
- El puente TPV→factura (hallazgo 1) sigue funcionando correctamente tras la fusión de
  las 3 ramas — no hay regresión.
- El resto de la app recorrida esta sesión (Dashboard, `/agents`, RAFAEL, THALOS, TPV,
  Control Horario, Nóminas, Seguros, Admin Panel, CRM, Ajustes, Analíticas, Alertas)
  funciona con datos reales, sin mocks permanentes detectados, con aislamiento
  multi-tenant confirmado explícitamente en TPV/facturación y en CRM con tenants propios
  distintos.
- Se encontraron 4 hallazgos nuevos de menor severidad de paso (sección 3), el más
  relevante siendo el bug pre-existente de `GET /invoices/` (401 con tokens válidos, aún
  sin arreglar) y la posible ausencia de un control de logout descubrible en el flujo
  principal.
- Nada de esto se cierra como aprobado por mí — corresponde a `revisor-independiente`
  confirmar de forma independiente antes de dar por bueno cualquier punto de este informe.
