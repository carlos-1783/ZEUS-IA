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

---

## 6. Revision independiente (revisor-independiente)

Fecha: 2026-08-25. Rama: feature/rediseno-completo, HEAD al empezar cc725db (el commit
de este mismo informe). Sin merge ni push a main en ningun momento.

Principio aplicado: no me fio de nada de lo escrito arriba por el ejecutor. Cada
afirmacion marcada como "confirmada" en esta seccion fue reproducida por mi, con mis
propios comandos, contra el sistema real, con cuentas 100% nuevas (rev1.restaurant,
rev2.office, rev3.superadmin, rev4.office2, todas @example.com, ninguna reutilizada de
las audit.* del ejecutor).

### 6.0 Entorno de verificacion propio

- git status/git log -1 confirmados al empezar: rama correcta, HEAD cc725db.
- Backend propio, aislado, en el puerto 8020 (distinto del 8010 del ejecutor y del 8000
  de otro agente activo), mismo zeus.db de este worktree, arrancado con
  uvicorn app.main:app --port 8020 desde backend/ con el mismo venv compartido.
- 4 cuentas propias creadas via POST /auth/register real (no inserts): rev1.restaurant
  (business_type=restaurant), rev2.office/rev4.office2 (business_type=services, dos
  tenants independientes), rev3.superadmin (promovido a is_superuser=1 y desvinculado de
  su empresa via DELETE FROM user_companies directo en zeus.db, igual que hizo el
  ejecutor, por no existir endpoint publico para esa promocion).
- Al terminar, mate el proceso propio del puerto 8020 y confirme git status limpio de
  nuevo (solo .claude/ sin trackear, igual que al principio - cero diffs colgados,
  confirmando la afirmacion del ejecutor de que no dejo cambios de CSP ni de ningun otro
  archivo).

### 6.1 Los 4 hallazgos pendientes - verificacion independiente

1. Puente TPV-factura: reproducido de extremo a extremo con rev1.restaurant. POST
/tpv/sale (con cart_items, no items - el nombre real del campo, distinto al que use en
mi primer intento) genero el ticket TICKET_20260825065337, luego POST /tpv/invoice
genero la factura id=10. Confirmado por SQL directo contra zeus.db: invoices id=10,
tpv_sale_id=8, company_id=242, coincide con tpv_sales id=8 del mismo company_id. Caso
404 real (ticket_id inexistente) confirmado con status 404. Idempotencia confirmada
(already_existed:true, mismo invoice.id). Aislamiento multi-tenant confirmado: con el
token de rev2.office (tenant distinto) intentando facturar el ticket de rev1, la
respuesta fue 403 "La venta no pertenece a su empresa.". Coincide con lo reportado - OK.

2. Heuristica de onboarding: confirmado el codigo exacto (onboarding_engine.py:158-170
crea siempre el CompanyEmployee "owner"; auth.py:594-618 marca setup_completed=True en
cuanto ce_count>=1). Reproducido por API con 2 cuentas propias nuevas de tipos de
negocio distintos: rev1.restaurant y rev2.office (services), ambas con
questionnaire_completed:false, operational_profile_completed:false, pero
setup_completed:true, setup_inferred:true, company_employees_count:1. Coincide
exactamente con lo reportado, severidad critica razonable - OK.

3. Superusuario sin empresa: reproducido con rev3.superadmin (cuenta propia, promovida y
desvinculada por mi). GET /auth/me devolvio is_superuser:true, company_id:null. GET
/auth/onboarding/status devolvio company_linked:false, setup_completed:false. POST
/auth/onboarding/profile devolvio el mismo mensaje exacto reportado: "Usuario sin
empresa vinculada. Completa el registro antes de configurar el perfil." Confirmado
tambien que OnboardingSetup.vue no tiene ningun logout/enlace de navegacion/"omitir" en
su plantilla (grep sin resultados). Coincide exactamente - OK.

4. encryption_status simulado en THALOS.SHIELD: confirmado. Sin token, 401. Con token de
rev1.restaurant y con token de rev2.office (dos tenants distintos), respuesta
byte-identica salvo timestamp, incluyendo "encryption_status":"activo" fijo. Coincide
exactamente - OK.

### 6.2 Repo limpio

Confirmado independientemente: git status --porcelain antes y despues de toda mi sesion
de pruebas solo muestra .claude/ sin trackear. git diff --stat vacio. Ninguna
modificacion colgada de frontend/index.html ni de ningun otro archivo. Coincide con lo
afirmado - OK.

### 6.3 Muestreo de pantallas (elegidas por menor evidencia en el informe original)

- Seguros (/insurance): GET /insurance/policies -> 200, lista vacia real. GET
  /crm/customers (de donde realmente lee el combo de clientes, confirmado por lectura de
  InsuranceView.vue:271, no de un endpoint /insurance/clients que no existe) -> []
  real para rev1, consistente con "combo vacio real, no forzado". POST
  /insurance/policies con payload incompleto -> error de validacion real (422), no un
  200 falso. OK, coincide con lo reportado.
- Admin Panel con superusuario SIN empresa: GET /admin/customers con el token de
  rev3.superadmin (sin empresa) -> 200 real, datos reales. Esto confirma que el
  hallazgo 3 es puramente de routing del frontend (el guard de Vue Router SI exime a
  AdminPanel del skipOnboardingGate, linea 553 de router/index.js) y no un bloqueo real
  de la API - matiza correctamente lo que ya insinuaba el informe original.
- CRM oficina, aislamiento multi-tenant: creado cliente real en rev2.office (POST
  /crm/customers con id:47 devuelto). Confirmado con GET /crm/customers que aparece. Con
  un TERCER tenant nuevo (rev4.office2, jamas usado por el ejecutor ni por mi antes),
  GET /crm/customers devuelve []. Aislamiento confirmado con un tenant nunca antes
  usado en esta auditoria - OK.
- Ajustes (/settings) - guardado del gestor fiscal: el informe deja esto explicitamente
  "no probado end-to-end". Lo probe yo, y esta roto. POST
  /api/v1/documents/update-advisor-emails?email_gestor_fiscal=... devuelve SIEMPRE 500:
  "Error actualizando emails de asesores: Instance <User at 0x...> is not persistent
  within this Session". Reproducido DOS veces, con DOS cuentas distintas
  (rev1.restaurant y rev2.office), 100% de repeticion. Causa visible en
  backend/app/api/v1/endpoints/document_approval.py:219-260: el try hace
  current_user.email_gestor_fiscal = ...; db.commit(); db.refresh(current_user) y el
  refresh falla porque current_user no esta en la identity map de la sesion db inyectada
  en este endpoint (indicio de que get_current_user/get_current_active_user no comparten
  sesion con el db: Session = Depends(get_db) del propio endpoint en este codigo en
  particular). Esto es un hallazgo NUEVO que el informe no encontro porque no llego a
  probarlo.

### 6.4 Suite de tests backend - ejecutada por mi, no citada del informe

pytest -q sin acotar falla con INTERNALERROR al recolectar TEST_SISTEMA_COMPLETO.py (un
script en la raiz de backend/ con sys.exit(0) a nivel de modulo - no es una regresion, es
el mismo problema de recoleccion ya investigado y descartado en el commit 622d431, que
documenta la ejecucion de la suite acotada a tests/). Ejecute pytest tests/ -q completo y
obtuve:

7 failed, 214 passed, 2 skipped, 3 errors in 100.86s

Coincide exactamente, cifra por cifra, con el baseline citado (7 failed, 214 passed, 2
skipped, 3 errors) que el propio informe admite no haber vuelto a ejecutar. Sin
regresion - confirmado por mi de forma exclusiva, ya que ni el ejecutor ni nadie mas lo
habia re-confirmado en esta sesion.

### 6.5 Migracion Alembic

Confirmado en zeus.db: la tabla invoices tiene la columna tpv_sale_id (de
0044_invoice_tpv_sale_link.py), consistente con el uso real observado en 6.1. Los
ficheros 0043_insurance_policies_claims.py, 0044_invoice_tpv_sale_link.py,
0045_company_billing_fields.py existen sin colision de numeracion. OK.

### 6.6 Hallazgos nuevos del informe - verificacion independiente

- ZEUS.ACTIVAR con error Pydantic: mi primer intento de reproducirlo llamando a POST
  /zeus/execute {"command":"ZEUS.ACTIVAR"} no fallo (devolvio 200 con "agent":"ZEUS"
  incluido) - una discrepancia aparente con el informe. Investigado a fondo: el bug real
  vive en un endpoint DISTINTO, POST /zeus/activate (sin body), que es el que realmente
  llama ZeusCore.vue en su initializeZeusSystem() al cargar la pantalla
  (ZeusCore.vue:225). Ese si devuelve 500: "Error activando Nucleo ZEUS: 1 validation
  error for ZeusResponse agent Field required" - porque zeus_manager.activate_all_agents()
  (codigo real en zeus_agents.py:677-700) devuelve un dict con clave "agents" (plural,
  por agente) y sin clave "agent" (singular) a nivel raiz, y ZeusResponse(**result) en
  zeus_core.py:84 exige agent: str como campo obligatorio. Confirmado tras identificar el
  endpoint correcto - coincide con lo reportado, sin discrepancia real.
- GET /invoices/ con 401 pese a token valido: reproducido con token fresco de
  rev1.restaurant -> 401 {"detail":"No se pudieron validar las credenciales"}.
  Confirmado, coincide.
- Ausencia de boton de "cerrar sesion" descubrible: confirmado, y reforzado con una
  causa raiz mas precisa que la del informe original. MainLayout.vue si tiene un boton
  de logout real (linea 74-79, llama authStore.logout()), pero el router
  (frontend/src/router/index.js) nunca usa MainLayout como componente de ninguna ruta
  activa - OlymposDashboard.vue (el componente real de /dashboard) no lo importa ni lo
  referencia. El unico sitio del codigo donde MainLayout se monta de verdad es
  frontend/src/main-ultra-minimal.js, un entry point alternativo que no es el que
  arranca la SPA de produccion. Es decir: el boton de logout de MainLayout.vue es codigo
  muerto, inalcanzable desde el flujo real de un usuario. Esto confirma con mas
  precision el hallazgo del informe, no lo contradice.
- "Enter no envia el formulario de login": no pude verificarlo de forma independiente.
  Motivo: reproducirlo requiere un frontend en vivo con Playwright/navegador, y la CSP
  de frontend/index.html solo permite connect-src a localhost:8000/5173 (puertos
  ocupados por otro agente durante toda mi sesion); a diferencia del ejecutor, como
  revisor-independiente no tengo herramientas de Edit/Write para editar la CSP
  temporalmente ni para revertirla despues, asi que no repeti ese truco. Por lectura de
  codigo (Login.vue:24,42-52,82-86): es un form con @submit.prevent="handleSubmit"
  completamente estandar, con un input type="password" dentro y un button
  type="submit" - esta es exactamente la estructura HTML que en cualquier navegador
  real dispara el evento submit del formulario al pulsar Enter en cualquiera de sus
  campos de texto. No hay ningun @keydown.enter.prevent ni logica que lo bloquee visible
  en el componente. La afirmacion del informe es, por tanto, sorprendente dado el
  codigo, y queda sin confirmar ni descartar por mi - senalado como pendiente, no como
  hallazgo cerrado.

### 6.7 Hallazgo nuevo encontrado por mi, no reportado por el ejecutor

POST /api/v1/documents/update-advisor-emails (guardar email del gestor fiscal en
Ajustes) devuelve 500 siempre, en toda circunstancia probada. Ver 6.3. Esto es relevante
porque:
1. Es exactamente el punto que el informe del ejecutor marco como "no probado
   end-to-end" en Ajustes - al probarlo, resulto estar roto, no solo sin probar.
2. Agrava el impacto real del hallazgo critico 2 (onboarding): dado que el wizard de
   onboarding nunca se activa (hallazgo 2) y que la unica via manual alternativa para
   fijar email_gestor_fiscal (necesaria para que RAFAEL pueda enviar facturacion real)
   esta rota con un 500, hoy no existe ningun camino funcional, ni automatico ni
   manual, para que un usuario real configure el email de su gestor fiscal.
3. Archivo y lineas: backend/app/api/v1/endpoints/document_approval.py:219-260.
   Severidad propuesta: ALTA (bloquea permanentemente una funcion de configuracion
   basica y compuesta con el hallazgo critico 2, aunque no es en si mismo una brecha de
   seguridad ni de aislamiento multi-tenant).

### 6.8 Evaluacion de severidades asignadas por el ejecutor

- Hallazgo 2 (onboarding, critico): razonable y bien fundamentado - confirmado
  independientemente con dos tipos de negocio distintos, causa raiz exacta verificada
  linea por linea. No exagerado.
- Hallazgo 4 (THALOS.SHIELD simulado, critico): razonable - es middleware de seguridad
  simulado y accesible por API real y autenticada sin diferenciacion por tenant, tal
  como exige tratar la skill zeus-produccion (regla no negociable de THALOS obligatorio
  y prohibicion de respuestas simuladas). No exagerado.
- Hallazgo 3 (superusuario sin empresa, alto): razonable, alcance limitado a un caso de
  borde (superusuarios sin empresa) pero con impacto real de UI atascada. No exagerado.
- Hallazgo 1 (puente TPV-factura): correctamente calificado como resuelto/OK.
- Si acaso, el informe se quedo corto: no asigno severidad al hueco de "Guardar gestor
  fiscal" simplemente porque no llego a probarlo - no es una minimizacion consciente, es
  una laguna de cobertura en un area que el propio informe senalo como de riesgo.

### 6.9 Veredicto

DEVUELTO AL EJECUTOR. No se puede cerrar esta auditoria como completa todavia.

Motivos concretos:
1. Hallazgo nuevo no cubierto: POST /documents/update-advisor-emails (guardado de
   "gestor fiscal" en Ajustes, la propia area que el informe dejo como pendiente de
   probar) devuelve 500 de forma reproducible y consistente
   (backend/app/api/v1/endpoints/document_approval.py:219-260). Esto contradice la
   conclusion general de la seccion 5 del informe ("el resto de la app... funciona con
   datos reales, sin mocks permanentes detectados") y agrava directamente el impacto del
   hallazgo critico 2, porque elimina tambien la unica via manual de mitigacion.
2. Afirmacion sin poder confirmar ni descartar: "Enter no envia el formulario de login"
   no pudo reproducirse de forma independiente en esta ronda (limitacion de
   herramientas del rol revisor, no del sistema en si) y resulta contraintuitiva dado el
   codigo real del formulario (form con @submit.prevent estandar y boton submit). Debe
   confirmarse con evidencia mas solida (grabacion, estado del DOM, o log de consola en
   el momento exacto) antes de darla por buena o descartarla.

Lo que SI se confirma cerrado y no necesita repetirse: los 4 hallazgos pendientes
(puente TPV-factura OK; heuristica de onboarding critica confirmada; superusuario sin
empresa confirmado; THALOS.SHIELD simulado confirmado), el estado limpio del repo, el
baseline de tests sin regresion (7 failed, 214 passed, 2 skipped, 3 errors, confirmado
por mi de forma exclusiva), la migracion Alembic aplicada, el aislamiento multi-tenant en
TPV/facturacion y en CRM (con un tercer tenant nunca antes usado), y el resto de
hallazgos nuevos de la seccion 3 del informe original (ZEUS.ACTIVAR, GET /invoices/ 401,
ausencia de logout descubrible - este ultimo reforzado con causa raiz mas precisa).

Que falta para la siguiente vuelta:
- Investigar y corregir (o, si corresponde a otro step del loop, documentar como
  hallazgo formal con severidad) el 500 de update-advisor-emails.
- Reproducir de forma concluyente (grabacion Playwright o inspeccion de consola en el
  momento del intento) si Enter realmente no envia el formulario de login, o retirar esa
  afirmacion si no se puede sostener.
- Los hallazgos 2, 3 y 4 siguen diagnosticados pero no corregidos - igual que ya
  indicaba el propio informe del ejecutor ("nada de esto se cierra como aprobado...
  hasta que se corrija"); esta revision confirma el diagnostico, no sustituye el
  arreglo.

---

## 7. Vuelta 2 — cierre de los 2 huecos señalados por el revisor

Fecha: 2026-08-25. Rama `feature/rediseno-completo` (mismo worktree
`agent-a8873985b2803de19`), sin merge ni push a `main`. Entorno: backend propio en
puerto 8030→8031 (el 8030 quedó ocupado tras un problema de backgrounding del propio
entorno de pruebas, ver nota más abajo), mismo `zeus.db` de este worktree, venv
compartido (`C:\Users\Acer\ZEUS-IA\backend\venv`). Frontend propio en puerto 5192 sólo
para el punto 2. Cuentas de prueba 100% nuevas, ninguna reutilizada de `audit.*` ni
`rev*.`: `ejec2.rest1@example.com`, `ejec2.off1@example.com`, `ejec2.enter@example.com`.

### 7.1 Punto 1 — `POST /documents/update-advisor-emails` devuelve 500 (hallazgo del revisor, sección 6.7/6.9)

**Causa raíz exacta, confirmada línea por línea, con reproducción antes y después del fix:**

- `backend/app/api/v1/endpoints/document_approval.py:15` importa `get_db` desde
  `app.db.session` (`from app.db.session import get_db`) para su propio
  `db: Session = Depends(get_db)`.
- `backend/app/core/auth.py:13` importa `get_db` desde **otro módulo distinto**,
  `app.db.base` (`from app.db.base import get_db`), y es esa función la que usa
  `get_current_user`/`get_current_active_user` (línea 235) para cargar `current_user`.
- `backend/app/db/base.py:885-888` define su propio `get_db()` "de compatibilidad" que
  hace `yield from get_db_with_retry()` reexportando `app.db.session.get_db` — pero al
  ser una función **distinta como objeto** (aunque delegue al mismo código), FastAPI la
  trata como una dependencia diferente a efectos de su caché de dependencias por
  request (la caché de `Depends()` se indexa por identidad del *callable*, no por lo que
  hace internamente). Resultado: en cualquier endpoint que (a) reciba `current_user` vía
  `get_current_active_user` y (b) declare también su propio `db: Session =
  Depends(get_db)` importado de `app.db.session`, **`current_user` queda vinculado a una
  sesión de SQLAlchemy distinta de `db`** — dos objetos `Session` distintos, dos
  conexiones distintas, dos identity maps distintos, para la misma petición HTTP.
- Mientras el código solo *lee* atributos ya cargados de `current_user` (p. ej.
  `current_user.id`, `current_user.company_id`) para filtrar consultas hechas con `db`,
  el desajuste es inofensivo. El bug se manifiesta **solo** cuando un endpoint muta un
  atributo de `current_user` y luego usa su propio `db` para persistir el cambio:
  - `update-advisor-emails` (líneas 219-260, antes del fix): hacía
    `current_user.email_gestor_fiscal = ...; db.commit(); db.refresh(current_user)`.
    `db.refresh()` exige que el objeto esté "persistente" (en el identity map) de esa
    sesión concreta; como `current_user` pertenece a la sesión de `app.db.base.get_db`
    y no a la de `db`, SQLAlchemy lanza
    `InvalidRequestError: Instance <User ...> is not persistent within this Session` —
    exactamente el mensaje que reportó el revisor.
  - Adicionalmente, aunque no llegara a `refresh()`: como el cambio de atributo se hizo
    sobre un objeto que pertenece a la sesión de `get_current_user` (no a `db`), y esa
    sesión nunca hace `commit()` (se cierra sin commit al terminar la petición, ver
    `app/db/session.py:29-31`), el cambio se habría **perdido silenciosamente** incluso
    si no hubiera excepción — es decir, sin este fix habría dos formas de fallar: con
    excepción visible (500, lo que de hecho ocurre) o, en otro orden de eventos, con
    pérdida silenciosa del dato sin ningún error. Ambas son inaceptables.

**Alcance verificado — no es exclusivo de `update-advisor-emails`:**

- `POST /documents/toggle-authorization` (mismo archivo, líneas 263-289) tiene el
  **mismo patrón exacto** (`current_user.autoriza_envio_documentos_a_asesores =
  autoriza; db.commit(); db.refresh(current_user)`) y falla con el mismo error. Confirmado
  en vivo antes del fix:
  `{"detail":"Error actualizando autorización: Instance '<User at 0x...>' is not persistent within this Session"}`.
- Grep exhaustivo (`current_user\.\w+\s*=` combinado con `db.commit()` en el mismo
  archivo) sobre todo `backend/app/api/v1/endpoints/`: solo dos archivos coinciden,
  `document_approval.py` (los dos endpoints de arriba) y `auth.py`. En `auth.py`, la
  función `_onboarding_profile_impl` (la que procesa el wizard real de onboarding,
  `POST /auth/onboarding/profile`) **ya conocía y mitigaba este mismo bug**: línea
  812-813 hace exactamente
  `current_user = db.query(User).filter(User.id == user_id).first()` con el comentario
  explícito *"Re-cargar el usuario desde esta sesión para evitar 'Object already
  attached to session N'"* — es decir, alguien ya diagnosticó este problema de raíz en
  esa función concreta, pero el mismo parche nunca se replicó a
  `document_approval.py`. Esto confirma que la causa es sistémica (la dualidad
  `app.db.base.get_db` / `app.db.session.get_db` usada por `auth.py` de un lado y por
  55 archivos de endpoints del otro), aunque solo **estos dos endpoints concretos**
  llegan a manifestarla como error 500 hoy.
- Solo otros dos archivos (`commands.py`, `zeus_core.py`) importan `get_db` desde
  `app.db.base` como el resto de la auth; ningún otro endpoint mezcla ambas fuentes de
  `get_db` mutando `current_user`.

**Fix aplicado** (bajo riesgo, aislado, reutiliza un patrón ya probado en el mismo
código — `auth.py::_onboarding_profile_impl`, no una solución nueva): en los dos
endpoints afectados de `document_approval.py`, re-obtener `current_user` a través de la
propia sesión `db` del endpoint antes de mutarlo:
```python
current_user = db.query(User).filter(User.id == current_user.id).first() or current_user
```
No se tocó `app/core/auth.py` ni `app/db/base.py` (el fix "correcto" a nivel arquitectónico
sería unificar `get_current_user` para que use `app.db.session.get_db`, pero eso afecta
la cadena de autenticación de los ~55 endpoints restantes del backend — fuera de alcance
de una auditoría, requiere su propio step de producción con pruebas dedicadas; señalado
como pendiente más abajo, no aplicado aquí).

**Verificado en vivo, antes y después del fix, con dos tenants nuevos:**

- Antes del fix — reproducido 3 veces: `ejec2.rest1@example.com` →
  `{"detail":"Error actualizando emails de asesores: Instance '<User at 0x2264e8be5c0>' is not persistent within this Session"}`;
  `toggle-authorization` con la misma cuenta → mismo patrón de error; repetido con
  `ejec2.off1@example.com` (segundo tenant, independiente) → mismo error exacto.
- Después del fix (backend reiniciado para cargar el cambio, sin `--reload`):
  - `POST /documents/update-advisor-emails?email_gestor_fiscal=gestor.fixed@example.com`
    con `ejec2.rest1` → `200 {"success":true,"email_gestor_fiscal":"gestor.fixed@example.com",...}`.
  - Confirmado por una llamada **independiente**, `GET /auth/onboarding/status`, que el
    valor persiste de verdad (no es solo el eco de la respuesta):
    `"email_gestor_fiscal":"gestor.fixed@example.com"`.
  - Confirmado además por **SQL directo** contra `zeus.db`: `email_gestor_fiscal =
    'gestor.fixed@example.com'` para el usuario 450 (`ejec2.rest1`), `NULL` para el
    usuario 451 (`ejec2.off1`, no tocado todavía en ese momento).
  - `POST /documents/toggle-authorization?autoriza=true` con `ejec2.rest1` → `200
    {"success":true,"autoriza_envio_documentos_a_asesores":true}`.
  - Aislamiento multi-tenant confirmado explícitamente: `POST
    /documents/update-advisor-emails?email_gestor_fiscal=gestor2.fixed@example.com` con
    `ejec2.off1@example.com` (segundo tenant, independiente) → `200` con su propio
    valor; SQL directo confirma `ejec2.off1` = `gestor2.fixed@example.com` y
    `ejec2.rest1` sigue con `gestor.fixed@example.com` — cada tenant solo modifica su
    propio registro, ninguno pisa al otro.
  - Caso de error controlado: la misma llamada sin token → `401` (no 500, no
    falso-éxito) — comportamiento de autenticación intacto tras el fix.
- **Regresión backend**: `pytest tests/ -q` tras el fix →
  `7 failed, 214 passed, 2 skipped, 3 errors in 94.61s` — coincide cifra por cifra con
  el baseline ya confirmado dos veces (por el ejecutor original y por
  revisor-independiente). Sin regresión.

**Severidad**: mantengo **ALTA**, de acuerdo con la propuesta del revisor, por las
mismas razones que ya dio (bloquea permanentemente una función de configuración básica,
y se compone con el hallazgo crítico 2 de onboarding porque elimina también la única vía
manual de mitigación) — no la subo a crítica porque, a diferencia del hallazgo 4
(THALOS.SHIELD simulado), no hay aquí ninguna brecha de seguridad ni de aislamiento
multi-tenant: el bug es un 500 que impide guardar, no una fuga de datos entre tenants
(confirmado arriba explícitamente con dos tenants independientes).

**Archivos y líneas tocados por el fix**: `backend/app/api/v1/endpoints/document_approval.py`
— línea añadida antes de la mutación en `update_advisor_emails` (dentro del bloque que
empieza en la antigua línea 230) y en `toggle_document_authorization` (dentro del bloque
que empieza en la antigua línea 272). Commit atómico, un solo archivo, sin tocar
`auth.py` ni `db/base.py`.

### 7.2 Punto 2 — "Enter no envía el formulario de login": RETRACTADO

**Veredicto: la afirmación original de la sección 2 del informe (nota al pie) no se
sostiene. La retracto explícitamente. No hay evidencia de que sea un bug real de
Login.vue ni de la app.**

Repetí la prueba con el navegador integrado (Playwright vía MCP), sirviendo el frontend
real de este worktree (confirmado por marcador único `Login.vue component is
mounting` y por `withModifiers` — el código compilado de `@submit.prevent` — presentes
en el módulo servido por Vite en `http://localhost:5192/src/views/auth/Login.vue`):

1. Login real (`/auth/login`), campos email+password rellenados con una cuenta nueva
   (`ejec2.enter@example.com`), clic explícito en el campo de contraseña, tecla
   `Return` — **no se disparó ninguna petición de red** (`read_network_requests`
   filtrado por `login` → "No network requests recorded"), no apareció ningún log de
   consola de `handleSubmit` (que sí se loguea explícitamente en el código,
   `console.log('[auth/Login.vue] handleSubmit llamado')`), y la captura de pantalla
   confirma que la UI se quedó exactamente igual (sin mensaje de error, sin estado
   "Enviando...", sin redirect).
2. Repetido también pulsando `Return` en el campo de email (con password vacío
   deliberadamente): si `handleSubmit` se hubiera ejecutado, `validateForm()` habría
   poblado `error.value` con el mensaje de contraseña requerida y aparecería el cuadro
   rojo de error (`v-if="error"`) — la captura confirma que **no apareció ningún
   error**, es decir, `handleSubmit` no llegó a ejecutarse en absoluto, ni siquiera para
   fallar la validación.
3. **Control decisivo**: repetí la misma secuencia de teclas sobre un HTML plano de
   control, sin ningún framework ni JavaScript de la app (`<form onsubmit="...">` con
   un `<input type=text>`, un `<input type=password>` y un `<button type=submit>`,
   servido como archivo estático desde el mismo Vite en el mismo puerto/entorno) —
   **el mismo resultado: pulsar `Return` (y también probé el identificador `Enter`) no
   disparó el `submit` nativo del navegador** (el título de la pestaña, que el propio
   `onsubmit` del HTML de control cambia a `"SUBMITTED"`, permaneció como `"Enter
   test"`). Sin embargo, **hacer clic en el botón `Go` de ese mismo formulario de
   control sí lo envió al instante** (el título cambió a `"SUBMITTED"` inmediatamente
   tras el clic).

Esto demuestra de forma concluyente que la ausencia de envío al pulsar Enter es una
**limitación del propio mecanismo de simulación de teclado de esta herramienta de
automatización de navegador** (el evento de tecla sintético no dispara el algoritmo de
envío implícito de formularios de Chromium), reproducible incluso en el HTML más simple
posible sin una sola línea de JavaScript de por medio — **no es un bug de Login.vue ni
de ZEUS IA**.

Por lectura de código, además, no hay ningún indicio de que un navegador real fuera a
comportarse igual: `Login.vue:24` tiene un `<form @submit.prevent="handleSubmit">`
completamente estándar, con el `<input type="password">` (línea 42-52) dentro de ese
mismo `<form>` y el `<button type="submit">` (línea 82-94) también dentro de él — la
estructura exacta que en cualquier navegador real dispara el envío implícito al pulsar
Enter en cualquier campo de texto del formulario. Grep exhaustivo sobre
`frontend/src/` completo de `addEventListener('keydown', ...)`, `@keydown`, `key ===
'Enter'` y variantes no encontró **ningún** listener global ni específico de la pantalla
de login que intercepte o bloquee la tecla Enter — los únicos `keydown` globales
registrados en toda la base de código (`DashboardProfesional.vue`, `OlympoGLB.vue`,
`OlympoFirstPerson.vue`, `audioService.ts`, `settings.ts::bumpActivity`) no se montan en
la pantalla de login ni interfieren con formularios (el de `settings.ts` solo
actualiza un timestamp de actividad, sin `preventDefault`).

**Conclusión**: retracto la afirmación de la sección 2 del informe original ("Enter no
envía el formulario"). No hay evidencia, ni por prueba en vivo ni por lectura de código,
de que sea un comportamiento real de la app — todo apunta a un falso positivo causado
por la misma limitación de la herramienta de automatización que ya se documentó en la
sección 0 para otros síntomas (ruido de HMR). Recomiendo, si se quiere una confirmación
100% definitiva más allá de toda duda, una prueba manual con un teclado físico real por
parte de un humano — algo que ni yo ni el revisor de la ronda anterior pudimos hacer con
las herramientas disponibles en esta sesión.

**Limpieza**: el archivo estático de control (`frontend/public/test-enter.html`) se creó
solo para esta prueba y se eliminó inmediatamente después. La CSP temporal de
`frontend/index.html` (se añadieron los puertos 8031/5192 a `connect-src` para que el
navegador de pruebas pudiera hablar con el backend/frontend aislados de esta sesión) se
revirtió con `git checkout -- frontend/index.html` antes de cerrar; confirmado con `git
status`/`git diff` limpios (solo queda como cambio real
`backend/app/api/v1/endpoints/document_approval.py`, más `.claude/` sin trackear como en
todas las rondas anteriores).

### 7.3 Qué NO se pudo verificar en esta vuelta

- Confirmación con un clic/tecla físicos de un humano real de que Enter sí envía el
  login en un navegador real fuera de esta herramienta de automatización — no disponible
  en este entorno.
- No se auditó si la misma dualidad `app.db.base.get_db` / `app.db.session.get_db`
  causa problemas *silenciosos* (sin excepción, con pérdida de datos) en algún otro
  flujo que mute `current_user` sin pasar por `db.refresh()` — el grep realizado busca
  específicamente el patrón "mutar current_user + db.commit() en el mismo archivo", que
  cubre los casos conocidos, pero no se puede descartar al 100% algún patrón más sutil
  (p. ej. mutación a través de un método de servicio importado que reciba `current_user`
  como parámetro) fuera del alcance de esta vuelta.

### 7.4 Qué queda pendiente

- **Decisión de producto/arquitectura, no tomada aquí**: si merece la pena, en un step
  de producción dedicado (no en una auditoría), unificar `get_current_user` /
  `get_current_active_user` (`app/core/auth.py`) para que usen `app.db.session.get_db`
  en lugar de `app.db.base.get_db`, eliminando la dualidad de raíz para los ~55 archivos
  de endpoints restantes, en vez de ir parcheando caso por caso con el patrón de
  re-fetch. Esto tiene mayor radio de impacto (toca la cadena de autenticación de todo
  el backend) y requiere su propia batería de pruebas de regresión antes de aplicarse —
  señalado aquí, no ejecutado.
- Los hallazgos 2, 3 y 4 de la sección 1 (heurística de onboarding, superusuario sin
  empresa, THALOS.SHIELD simulado) siguen sin corregir, tal como ya señalaban tanto el
  informe original como la revisión independiente — esta vuelta 2 no los toca, solo
  cierra los dos huecos concretos que motivaron la devolución del informe.
- Corresponde a `revisor-independiente`, en una nueva vuelta, confirmar de forma
  independiente el fix de `update-advisor-emails`/`toggle-authorization` y la
  retractación del punto de Enter, antes de dar la auditoría por cerrada. No la declaro
  cerrada yo mismo.

---

## 7.5 Revision independiente de la Vuelta 2 (revisor-independiente)

Fecha: 2026-08-25. Rama feature/rediseno-completo (worktree agent-a8873985b2803de19), HEAD
al empezar ca2e7fe (commit del fix de la Vuelta 2). Sin merge ni push a main en ningun
momento de esta sesion.

Principio aplicado: no me fio de lo escrito por el ejecutor en la seccion 7. Cada afirmacion
fue reproducida por mi, con mis propios comandos, contra el sistema real, con cuentas 100%
nuevas (indep.rest1@example.com, indep.office1@example.com, indep.enter.test@example.com),
ninguna reutilizada de audit.*, rev*. ni ejec2.* de rondas anteriores.

### 7.5.0 Entorno de verificacion propio

- git status/git log -1 confirmados al empezar: rama correcta, HEAD ca2e7fe.
- Backend propio, aislado, en el puerto 8040 (libre, distinto de 8000/8010/8020/8030-8031
  usados por el ejecutor y otro agente), mismo zeus.db de este worktree, venv compartido
  C:\Users\Acer\ZEUS-IA\backend\venv.
- Frontend propio, aislado, en el puerto 5195 (libre), servido con
  node_modules/.bin/vite --port 5195 --strictPort directamente en este worktree, sin
  reinstalar dependencias.
- 2 cuentas propias nuevas via POST /auth/register real: indep.rest1@example.com
  (business_type=restaurant, user_id=500, company_id=305) e
  indep.office1@example.com (business_type=services, user_id=501, company_id=306).
  Una tercera cuenta, indep.enter.test@example.com, usada solo para el punto 2 (no
  necesita persistir en BD para esa prueba).
- Al terminar, mate los procesos propios de los puertos 8040 y 5195 y confirme git status
  limpio de nuevo (solo .claude/ sin trackear, git diff --stat vacio) - cero diffs
  colgados de CSP ni de ningun otro archivo, igual que en todas las rondas anteriores.

### 7.5.1 Punto 1 - fix de update-advisor-emails/toggle-authorization: verificado, correcto y completo

Codigo leido directamente, no el diff:

- backend/app/api/v1/endpoints/document_approval.py completo (478 lineas). Confirmado
  linea por linea: update_advisor_emails (219-267) y toggle_document_authorization
  (270-299) tienen ambas, antes de mutar current_user, la linea
  current_user = db.query(User).filter(User.id == current_user.id).first() or current_user
  (236 y 282 respectivamente), con comentario explicando la causa. El resto del archivo
  (approve_document, get_pending_documents, get_approval_history, export_fiscal_document,
  get_fiscal_document_trace) no muta atributos de current_user, por lo que no necesitaba
  el mismo parche - confirmado que el fix no se aplico de mas ni de menos.
- Causa raiz confirmada como tecnicamente correcta, no una racionalizacion post-hoc:
  - backend/app/api/v1/endpoints/document_approval.py:15 - from app.db.session import get_db.
  - backend/app/core/auth.py:13 - from app.db.base import get_db (import distinto), y
    get_current_user (linea 233-235) usa ese get_db para su propio
    db: Session = Depends(get_db).
  - backend/app/db/base.py:885-888 - get_db() "de compatibilidad" que hace
    yield from get_db_with_retry() reexportando app.db.session.get_db - pero como
    objeto/funcion es un callable distinto.
  - backend/app/db/session.py:11-32 - el get_db() real crea SessionLocal(), hace
    yield db y en el finally hace db.close() sin commit() explicito antes. Esto
    es coherente con SQLAlchemy estandar: al cerrar una sesion con una transaccion
    pendiente sin commit, el rollback es implicito - confirma tecnicamente la segunda
    mitad de la explicacion del ejecutor (perdida silenciosa de datos como fallo
    alternativo al 500, no solo el 500 en si).
  - Confirmado que FastAPI cachea las dependencias Depends() por identidad del callable
    (comportamiento documentado de FastAPI, no una suposicion): dos funciones get_db
    distintas como objetos, aunque una delegue en la otra, producen dos instancias de
    Session distintas para la misma peticion HTTP. La explicacion del ejecutor es
    correcta, no una racionalizacion incorrecta.
  - backend/app/api/v1/endpoints/auth.py:812-813 - confirmado el patron ya existente:
    current_user = db.query(User).filter(User.id == user_id).first() con el comentario
    "Re-cargar el usuario desde esta sesion para evitar Object already attached to
    session N", dentro de _onboarding_profile_impl (linea 801). El fix aplicado en
    document_approval.py reutiliza exactamente este patron ya probado en el mismo
    codebase - coherente, no una solucion inventada de cero.
  - backend/app/api/v1/endpoints/auth.py:22 - confirmado que este archivo importa
    get_db de app.db.session (igual que document_approval.py), consistente con el
    diagnostico.

Alcance del riesgo - grep exhaustivo propio, no solo el del ejecutor:

- grep -rln "current_user\.\w+\s*=" backend/app/api/v1/endpoints/ | xargs grep -l "db.commit()"
  devuelve solo auth.py y document_approval.py. Ampliado a grep -rln "db.refresh(current_user)" .
  sobre todo backend/ (no solo endpoints/) devuelve los mismos 2 archivos, ningun otro.
- Confirmado que current_user es, en la practica totalidad de los ~63 archivos que usan
  get_current_active_user/get_current_user, el unico nombre de variable usado para el
  resultado de esa dependencia (grep de la firma \w+: User = Depends(get_current sobre
  todos los endpoints devuelve solo current_user), por lo que el grep de mutacion no deja
  huecos por alias de variable distintos.
- Solo 3 archivos en todo el backend importan get_db desde app.db.base (la fuente de
  sesion distinta): app/core/auth.py, app/api/v1/endpoints/commands.py,
  app/api/v1/endpoints/zeus_core.py - coincide exactamente con lo que reporto el ejecutor.
  Ninguno de esos otros 2 archivos de endpoints mezcla ademas mutacion de current_user.
- Revisado tambien user_account.py (candidato plausible por su nombre, "cuenta de
  usuario") - no muta current_user, solo lee sus atributos y opera sobre otras filas
  (UserSettings), por lo que no esta expuesto a este bug.

Reproducido en vivo, de extremo a extremo, con cuentas 100% nuevas:

- POST /documents/update-advisor-emails?email_gestor_fiscal=indep.gestor1@example.com
  con el token de indep.rest1 -> 200 {"success":true,"email_gestor_fiscal":"indep.gestor1@example.com",...}.
- POST /documents/toggle-authorization?autoriza=true con el mismo token -> 200
  {"success":true,"autoriza_envio_documentos_a_asesores":true}.
- POST /documents/update-advisor-emails?email_gestor_fiscal=indep.gestor2@example.com
  con el token de indep.office1 (segundo tenant, independiente) -> 200 con su propio
  valor.
- Persistencia confirmada por llamada independiente, no por el eco de la respuesta:
  GET /auth/onboarding/status con cada token devuelve exactamente el valor guardado por
  ese tenant (indep.gestor1@example.com / autoriza:true para indep.rest1;
  indep.gestor2@example.com / autoriza:false para indep.office1).
- Persistencia confirmada ademas por SQL directo contra zeus.db:
  SELECT id, email, email_gestor_fiscal, autoriza_envio_documentos_a_asesores FROM users
  WHERE id IN (500,501) devuelve (500, indep.rest1@example.com, indep.gestor1@example.com, 1),
  (501, indep.office1@example.com, indep.gestor2@example.com, 0).
- Aislamiento multi-tenant confirmado explicitamente: cada usuario solo tiene su
  propio valor en BD; ninguno de los dos registros fue sobrescrito por la llamada del
  otro tenant.
- Caso de error controlado sin regresion de auth: la misma llamada sin token ->
  401 (no 500, no falso-exito) - confirmado con curl propio.

Regresion backend - ejecutada por mi, cifra por cifra:

7 failed, 214 passed, 2 skipped, 3 errors in 97.45s

Coincide exactamente con el baseline citado por el ejecutor y por la revision de la
Vuelta 1 (7 failed, 214 passed, 2 skipped, 3 errors). Esta es la primera vez que un
revisor independiente confirma este baseline con el fix de ca2e7fe ya aplicado -
sin regresion.

Veredicto punto 1: OK, coincide exactamente con lo reportado en la seccion 7.1. El
fix es correcto, minimo, coherente con un patron ya probado en el mismo codebase, y no
introduce fugas entre tenants ni rompe el manejo de errores.

### 7.5.2 Punto 2 - retractacion de "Enter no envia el login": confirmada de forma independiente, sin hueco logico

Reproduje la prueba completa yo mismo, sin reutilizar el archivo de control del ejecutor
(que ya habia sido borrado) - cree mi propio archivo HTML de control desde cero.

1. Login.vue real, cuenta nueva: abri http://localhost:5195/auth/login (frontend
   propio de este worktree, confirmado por los logs de consola reales de la app -
   [AuthStore] Starting login process, [auth/Login.vue] Resultado del login, etc., no
   una pagina generica). Rellene email/password de indep.enter.test@example.com
   (cuenta nueva, no usada por nadie mas en esta auditoria), clic explicito en el campo
   de contrasena, tecla Return. Resultado: ninguna peticion de red registrada
   (read_network_requests filtrado por "login" - "No network requests recorded"),
   ningun log de consola de handleSubmit/AuthStore (que si aparecen y se registran
   explicitamente en el codigo real), captura de pantalla identica a antes de pulsar Enter.
2. Control decisivo, hecho por mi con mi propio archivo, no el del ejecutor: escribi
   un HTML estatico minimo con un formulario cuyo manejador onsubmit cambiaba el titulo
   de la pestana a SUBMITTED y devolvia false, con un input de texto, un input de
   password y un boton submit, sin Vue, sin CSP, sin ningun JavaScript de la app -
   servido como archivo real (no snapshot estatico) a traves del propio Vite de este
   worktree via la ruta interna @fs (posible porque vite.config.ts ya tiene
   fs: { strict: false, allow: [".."] } configurado de antes, no algo que yo haya tenido
   que tocar). Escribi texto en el campo de contrasena y pulse Return: el titulo de la
   pestana permanecio "Enter test", sin cambiar a "SUBMITTED". Acto seguido, clic
   explicito en el boton Go del mismo formulario: el titulo cambio a "SUBMITTED" de
   inmediato.
3. Repeti el mismo contraste dentro de la propia app real: en el login real de
   indep.enter.test, tras confirmar que Enter no disparaba nada, hice clic explicito en
   el boton Iniciar sesion - esta vez si aparecieron los logs reales
   ([AuthStore] Starting login process, [API] Sending POST to auth/login, etc.) y una
   peticion de red real (POST http://127.0.0.1:8010/api/v1/auth/login, bloqueada por la
   CSP de este entorno por apuntar a un puerto no blanqueado - comportamiento esperado y
   sin relacion con el hallazgo de Enter, documentado ya en la seccion 0 del informe
   original).

Este es un experimento A/B limpio dentro de la misma sesion de navegador: el mismo tipo
de interaccion (tecla Return) fallo tanto en el formulario real de la app como en un
HTML sin una sola linea de JavaScript de framework, mientras que el clic funciono en
ambos casos sin excepcion. Esto descarta que el problema sea especifico de Login.vue o
de algun keydown oculto.

Verificacion adicional por lectura de codigo, hecha por mi de forma independiente:
grep propio de keydown, keyup, @keydown, key === Enter, keyCode === 13, which === 13
sobre todo frontend/src/ - los unicos matches son
DashboardProfesional.vue, OlympoFirstPerson.vue, OlympoGLB.vue, settings.ts,
audioService.ts, TPV.vue. Lei los dos unicos que registran listeners globales
(window.addEventListener("keydown", ...), en settings.ts::armIdleWatcher y
audioService.ts::handleInteraction): ninguno de los dos llama a preventDefault() ni a
stopPropagation() - bumpActivity solo actualiza un timestamp, handleInteraction solo
inicializa el sistema de audio y se auto-elimina tras el primer evento. Ninguno podria
bloquear el envio nativo de un formulario aunque estuviera montado en la pantalla de
login. Login.vue en si (lineas 24, 42-52, 82-94) es un form completamente estandar
con @submit.prevent="handleSubmit", sin ningun @keydown propio.

No encuentro ningun hueco logico en el razonamiento del ejecutor. El control es
valido porque aisla la variable correcta (mecanismo de sintesis de teclado de la
herramienta de automatizacion vs. estructura HTML/JS de la pagina), y mi repeticion
independiente con un archivo de control distinto, en un entorno servido de forma
distinta (ruta @fs de Vite en vez de frontend/public/), llega exactamente al mismo
resultado.

Veredicto punto 2: retractacion confirmada de forma independiente. No hay evidencia,
ni por prueba en vivo (dos veces, con dos archivos de control distintos) ni por lectura
de codigo, de que "Enter no envia el login" sea un bug real de Login.vue o de ZEUS IA.
Sigue sin poder descartarse al 100% con un teclado fisico real fuera de esta herramienta
de automatizacion (limitacion compartida por el ejecutor, la revision de la Vuelta 1 y
esta revision), pero eso ya no bloquea el cierre: la retractacion esta suficientemente
fundamentada con dos pruebas de control independientes que apuntan a la misma causa.

### 7.5.3 Repo limpio - confirmado de forma independiente

git status --porcelain antes y despues de toda mi sesion de pruebas: solo .claude/
sin trackear. git diff --stat: vacio. zeus.db esta en .gitignore
(git check-ignore zeus.db -> ignorado), por lo que los 2 usuarios nuevos que cree
(id=500, id=501) no afectan al estado del repo. Ningun archivo de prueba (mi HTML de
control vivio solo en el scratchpad temporal fuera del repo, nunca dentro de
frontend/public/ ni de ningun directorio trackeado) quedo colgado. Coincide con lo
afirmado en la seccion 7.2 - OK.

### 7.5.4 Veredicto final de esta auditoria completa

APROBADO. Se cierra esta auditoria final completa (informe + Vuelta 1 + Vuelta 2 +
esta revision independiente de cierre).

Los 2 motivos concretos que motivaron la devolucion en la seccion 6.9 quedan cerrados,
verificados de forma 100% independiente, con cuentas y herramientas propias:

1. El 500 de update-advisor-emails/toggle-authorization esta corregido, con causa raiz
   tecnicamente correcta y verificada linea por linea, fix minimo y coherente con un
   patron ya probado en el mismo codebase, alcance del riesgo acotado por grep exhaustivo
   propio (solo estos 2 endpoints lo manifestaban), reproducido en vivo con persistencia
   confirmada por API independiente y por SQL directo, aislamiento multi-tenant
   confirmado, y sin regresion en la suite de tests (7 failed, 214 passed, 2 skipped, 3
   errors, identica al baseline, confirmada por mi con el fix ya aplicado).
2. La retractacion de "Enter no envia el login" esta fundamentada de forma solida:
   reproducida de forma independiente por mi con un experimento de control propio
   (archivo HTML distinto al del ejecutor, servido de forma distinta), con el mismo
   resultado - no es un bug de Login.vue, es una limitacion de la herramienta de
   automatizacion de teclado usada en todas las sesiones de esta auditoria.

Resumen de las 4 rondas completas de este documento:

- Ronda 1 (secciones 0-5, ejecutor): auditoria inicial completa, 4 hallazgos
  pendientes verificados en vivo (puente TPV-factura OK; heuristica de onboarding
  critica; superusuario sin empresa alto; THALOS.SHIELD simulado critico), mas 5
  hallazgos nuevos de menor severidad.
- Ronda 2 (seccion 6, revisor-independiente): confirmo de forma independiente los 4
  hallazgos pendientes y el resto del informe, pero devolvio por 2 motivos: un
  hallazgo nuevo no cubierto (500 en update-advisor-emails, precisamente el area que el
  informe original dejo como "no probado end-to-end") y una afirmacion sin poder
  confirmar ni descartar ("Enter no envia el login").
- Ronda 3 (seccion 7, ejecutor, Vuelta 2): cerro los 2 motivos de la devolucion -
  diagnostico la causa raiz exacta del 500 (doble get_db cacheado por FastAPI como
  dependencias distintas), aplico un fix minimo de una linea en los 2 endpoints
  afectados reutilizando un patron ya probado en el mismo codebase, y se retracto de la
  afirmacion sobre Enter tras un control decisivo con HTML plano sin JavaScript.
- Ronda 4 (esta seccion 7.5, revisor-independiente): verificacion 100% independiente
  de la Ronda 3, sin fiarse de nada de lo escrito - codigo releido linea por linea,
  causa raiz confirmada tecnicamente (no solo aceptada de palabra), fix reproducido en
  vivo con cuentas nuevas y persistencia confirmada por dos vias independientes
  (API + SQL), grep propio y mas amplio confirmando que el alcance del riesgo esta bien
  acotado, suite de tests re-ejecutada con el fix aplicado sin regresion, y la
  retractacion de Enter confirmada con un segundo experimento de control independiente
  del primero. Ningun hallazgo nuevo de esta ronda impide el cierre.

Los hallazgos 2 (heuristica de onboarding, critico), 3 (superusuario sin empresa, alto) y
4 (THALOS.SHIELD simulado, critico) de la seccion 1 siguen diagnosticados pero no
corregidos - eso nunca fue el alcance de esta auditoria de cierre (una auditoria
documenta y verifica, no arregla salvo mandato explicito), y tanto el informe original
como las dos rondas de revision lo han senalado consistentemente como pendiente de un
step de produccion dedicado, no de esta auditoria. Esta auditoria se cierra sobre esos
terminos: el informe completo, con sus 2 vueltas de correccion y esta revision final, es
un documento fiable del estado real de la aplicacion a fecha 2026-08-25, y no requiere
una Vuelta 3.
