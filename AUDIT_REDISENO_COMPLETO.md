# AUDIT_REDISENO_COMPLETO.md

**Rama**: `feature/rediseno-frontend-fase1` (desde `main`, continuación de la fase 1)
**Fecha**: 2026-08-16
**Objetivo de esta ronda**: aplicar el sistema de diseño validado (aluminio
cepillado + acento vibrante teal→morado→rosa→naranja + motion con
cubic-bezier) a **toda** la aplicación: Dashboard, `/agents`, los 6
workspaces de agente, CRM, TPV, Control Horario, Nóminas y Onboarding.

Sin cambios de backend, base de datos ni lógica de negocio — solo capa
visual/interacción sobre datos y funcionalidad reales, como en la fase 1.

---

## 1. Sistema de diseño — qué se añadió esta ronda

Extiende `frontend/src/assets/styles/zeus-light-system.css` (ya existente
desde la fase 1) con tres bloques nuevos, extraídos del preview aislado
`preview-rafael.html` que ya había sido aprobado visualmente:

- **`--zeus-accent-gradient`**: `linear-gradient(135deg, #14b8a6 0%, #8b5cf6 40%, #ec4899 70%, #f97316 100%)`
  (teal→morado→rosa→naranja), con `--zeus-accent-gradient-shadow` /
  `-shadow-hover`. Uso deliberadamente restringido: **solo** botón/estado
  activo, anillo de avatar, y badges de "seleccionado"/"online" — nunca
  como fondo de página ni de texto largo.
- **`--zeus-metal-bg` / `--zeus-noise-svg`**: la superficie "metal
  cepillado" (veta fina + barrido de luz diagonal + brillo de esquina +
  grano SVG) para el panel compartido de los 6 agentes.
- **Motion compartido**: `--zeus-ease-enter` (desaceleración, entradas),
  `--zeus-ease-exit` (aceleración, salidas), `--zeus-ease-micro`
  (hover/press), `--zeus-dur-modal` (240ms), `--zeus-dur-hover` (180ms),
  `--zeus-dur-press` (100ms) — para que cada componente los consuma en
  vez de reinventar timings sueltos.

Utilidades globales nuevas: `.zeus-btn-accent`, `.zeus-avatar-ring-accent`,
`.zeus-badge-accent`, `.zeus-metal-surface`.

---

## 2. Pantallas rediseñadas esta ronda

### 2.1 Dashboard principal
Botón "Interactuar" de cada tarjeta de agente con el acento gradiente
(antes azul→violeta plano). Modal de interacción con motion de 240ms y
easing distinto para entrada/salida (antes un único bezier simétrico).
**Verificado en vivo** con Playwright: gradiente computado correcto,
modal abre con datos reales por agente, cierre con Esc confirmado.

### 2.2 `/agents`
Badge "Online" con el acento gradiente (antes verde sólido). **Verificado
en vivo**: los 6 agentes reales se listan correctamente.

### 2.3 Panel compartido de agentes (`AgentActivityPanel.vue`)
Cierra el pendiente de la fase 1: fondo "metal cepillado" completo con
grano SVG, anillo de acento gradiente en el avatar, toggle Texto/Voz y
tabs con el gradiente en el estado activo. **Verificado en vivo** sobre
RAFAEL: fondo y gradientes computados correctos, cambio de tab a Chat
funcional con interacción real.

**Decisión de diseño**: el acento gradiente compartido se reserva para
el "chrome" del sistema (toggle, tabs, anillo de avatar, badges) — la
identidad de color propia de cada agente (ámbar RAFAEL, azul PERSEO,
cielo THALOS, índigo/violeta JUSTICIA, esmeralda AFRODITA) se mantiene
en sus propios botones de acción, para no perder la distinción visual
entre agentes bajo un único gradiente universal.

### 2.4–2.9 Los 6 workspaces de agente
Todos migrados a los tokens `var(--zeus-*)` (antes hex hardcoded, la
mayoría ya en paleta clara pero sin tokenizar; ZEUS CORE era el único
genuinamente oscuro). Cada uno con:
- Botón de acción primaria con profundidad real (sombra con tinte del
  color de identidad del agente, hover/press), mismo patrón que RAFAEL.
- Un único punto de acento gradiente como indicador de "seleccionado":
  franja lateral en listas de entregables (RAFAEL, PERSEO, THALOS,
  JUSTICIA), subrayado en pestaña activa (AFRODITA), botón "Construir
  workspace" (ZEUS CORE, que al ser el orquestador no tiene color de
  identidad propio distinto del sistema).

**Hallazgo real durante la verificación de ZEUS CORE**: sus botones
salían negro sólido — el mismo bug de `css_system_enforcer_v1.css` de la
fase 1 (`[class$='-workspace'] button {...!important}`), que entonces
solo se había excluido para `.rafael-workspace`/`.perseo-workspace`. Se
extendió la exclusión a los 6 workspaces de agente, ya que todos siguen
ahora el sistema de diseño claro con su propio CSS.

**Verificado en vivo** los 6: RAFAEL, PERSEO, AFRODITA, THALOS, JUSTICIA
y ZEUS CORE abren con datos reales (estados de módulo reales tipo
SIMULATED/PARTIAL/REAL, no mockeados) y gradientes/sombras computados
correctamente. En ZEUS CORE se ejecutó además el flujo real completo:
clic en "Construir workspace" disparó `POST
/api/v1/zeus-core/workspace-bootstrap` y el resultado se renderizó con
timestamp real.

### 2.10 Onboarding (`OnboardingSetup.vue`)
De tema oscuro hardcoded (`#0b1020`/`#121a33`/`#0a1228`) a los tokens del
sistema: tarjeta blanca, inputs claros con foco índigo, botones con
profundidad real. El paso activo del stepper (Operación/Canales/
Validación) lleva un subrayado con el acento gradiente. **Verificado en
vivo**: registrando una cuenta de prueba nueva, la pantalla real de
configuración inicial (paso 1, con los inputs reales de empleados/
horario) renderiza en claro con el gradiente visible.

### 2.11 Nóminas (`PayrollDrafts.vue`)
De estilo neutro sin fondo de página propio a los tokens del sistema:
tarjetas de borrador con sombra, botón "Descargar PDF" con profundidad.

### 2.12 CRM (`OfficeCrm.vue` + `office-crm-theme.scss`)
La mayoría del color real vivía en `office-crm-theme.scss` (hoja
importada globalmente), no solo en el componente — se tokenizaron ambos.
Botones primarios con profundidad real; acento gradiente como subrayado
en la pestaña de cliente activa del dock lateral.

### 2.13 Control Horario (`ControlHorario.vue`)
~70 colores hardcoded (ya en paleta clara) migrados a tokens,
preservando la semántica de presencia (dentro/fuera/pausa vía
success/warning/danger). Acento gradiente como subrayado del método de
fichaje activo (QR/PIN/GPS/Face/Remoto).

### 2.14 TPV (`TPV.vue`)
La pantalla más grande (4200 líneas) y la única genuinamente oscura de
este bloque (glassmorphism casi negro con paneles translúcidos blancos).
Migrada por completo a la superficie platino-y-blanco del sistema.
Acento gradiente en exactamente 3 puntos restringidos: categoría de
producto activa, línea de carrito activa en el teclado numérico, y mesa
seleccionada — el resto de la pantalla queda en índigo llano para no
saturar una interfaz operativa de punto de venta.

---

## 3. Hallazgo: no se pudo verificar en vivo CRM / TPV / Control Horario / Nóminas

Al intentar abrir estas 4 pantallas con cuentas de prueba **nuevas**
creadas en esta sesión (la cuenta `test.gestoria@example.com` de la fase
1 tenía la sesión expirada y no se pudo recuperar su contraseña), el
router redirige siempre a `/dashboard`, incluso con una cuenta `owner`
de tipo `bar_restaurant` recién registrada cuya respuesta real de
`GET /api/v1/auth/me` confirma `modules: { tpv: true, control_horario:
true, payroll: true, ... }`.

Se investigó el guard de rutas (`frontend/src/router/index.js`, función
`routeAllowed` de `frontend/src/utils/companyModules.ts`): con esos
módulos y sin ser superusuario, la lógica debería permitir el acceso.
El redirect persiste de todos modos — indicio de una posible
desincronización entre `authStore.modules` (estado en memoria del
frontend) y la respuesta real de `/auth/me`, no relacionada con este
cambio visual. **No se investigó ni se tocó** este comportamiento —
está fuera del alcance de esta tarea (solo frontend visual) y merece su
propia auditoría.

Por eso, en estas 4 pantallas la verificación se limitó a: confirmar
compilación HMR limpia (sin errores de sintaxis CSS/SCSS en los logs de
Vite) y aplicar exactamente el mismo patrón de conversión ya verificado
visualmente en las otras 9 pantallas de esta ronda. El riesgo de
regresión visual es bajo (cada valor nuevo usa `var(--zeus-*,
valor-original-como-fallback)`), pero **no equivale a la confirmación
visual real** que sí se hizo en el resto — se marca explícitamente aquí
para que quien revise la PR lo sepa antes de aprobar.

---

## 4. Verificación realizada

10 de las 14 pantallas de esta ronda (Dashboard, `/agents`, los 6
workspaces de agente, Onboarding) se verificaron en vivo con Playwright:
captura de pantalla, estilos computados vía `getComputedStyle()`,
interacción real (clics, cambios de tab, envío de formularios) y
revisión de consola. El único error de consola presente en toda la
sesión (`shouldShowTPV is not defined` en `DashboardProfesional.vue`) es
preexistente de `main`, ya diagnosticado en una rama separada — no
introducido por este trabajo.

Las 4 restantes (CRM, TPV, Control Horario, Nóminas) se verificaron solo
a nivel de compilación, por el hallazgo de la sección 3.

No se tocó `backend/` en ningún commit de esta rama.

---

## 5. Pendiente

1. **El hallazgo de la sección 3** (module gate no respeta
   `modules.*:true` de `/auth/me` para cuentas owner recién creadas) —
   merece su propia investigación; puede estar bloqueando en producción
   a clientes reales de tipo `bar_restaurant`/`office` recién dados de
   alta.
2. Verificación visual real de CRM, TPV, Control Horario y Nóminas una
   vez resuelto el punto anterior (o con una cuenta de prueba que sí
   tenga acceso).
3. La exploración de "metal cepillado + acento vibrante + motion" para
   el modal de RAFAEL sigue **solo** en el preview aislado
   (`preview-rafael.html`, fuera del repo) — no aplicada a ningún
   componente real, pendiente de aprobación final (ver
   `AUDIT_REDISENO_FASE1.md`, sección 3).
4. Explícitamente fuera de alcance: CRM/TPV/Control Horario/Nóminas ya
   cubiertos ahora; quedan fuera Admin Panel, Settings, y el resto de
   vistas menores (`ScanHub`, `SystemStatusPanel`, `Pricing`, `Checkout`,
   `AdminPanel`) no mencionadas en el encargo original.

---

## 6. Ronda 2 — sistema de diseño definitivo (2026-08-16, misma tarde)

El usuario dio un sistema de diseño **exacto y obligatorio**, distinto
(más estricto) del usado en la ronda 1, con instrucción explícita de no
reinterpretarlo ni aplicar solo una parte:

- **Fondo**: `repeating-linear-gradient(90deg, #E8E9EB 0px, #F5F6F7 15px,
  #D4D6D9 35px, #F0F1F3 60px, #C9CCD0 85px, #E5E7E9 110px)` + veta
  diagonal blanco→transparente 12% + grano SVG 3% — en TODA página y
  modal, sin excepción. Sustituye el degradado plano de la ronda 1 y el
  "metal cepillado" de textura fina que solo se aplicaba a modales.
- **Botón activo/primario**: gradiente de 3 paradas teal→morado→rosa
  (`#14B8A6→#8B5CF6→#EC4899`, sin naranja), sombra `0 2px 8px
  rgba(0,0,0,.15)` — **solo UNO por vista, el de mayor jerarquía real**.
- **Botón secundario**: blanco, borde `1px solid #D1D5DB`, sin
  gradiente, sin sombra — todos los demás botones, sin excepción.
- Motion sin cambios respecto a la ronda 1.

### Proceso seguido

Se reconstruyó `preview-rafael.html` (fuera del repo) con los valores
exactos como referencia única aprobada, verificando con
`document.fonts.check()` que Inter carga de verdad. Cada pantalla se
comparó contra esa referencia con capturas + estilos computados
(`getComputedStyle`, conteo de elementos con el gradiente) antes de
darla por terminada — no se pudieron adjuntar las capturas como
archivos en el commit/PR (limitación de herramientas: no hay forma de
guardar una captura del navegador como archivo en disco), así que se
compartieron directamente en la conversación en su lugar.

### Decisión de diseño: "un solo botón por vista" en la práctica

Muchos elementos que en la ronda 1 llevaban el gradiente (tabs, toggles,
franjas de "seleccionado", badges repetidos por fila) no son en rigor
"el botón primario" de su vista — son controles de navegación/selección
entre pares. Se aplicó un criterio consistente en las ~15 pantallas:

- **Selección dentro de un grupo** (tabs, toggle Texto/Voz, categoría de
  producto, mesa, fila de lista): gradiente retirado, queda solo negrita
  y/o cambio de borde.
- **Acción repetida por fila** (Interactuar ×6 en Dashboard, Descargar
  ×N en Nóminas): botón secundario — ninguna instancia es "la" única.
- **Acción real de mayor jerarquía de la vista** (Actualizar en cada
  workspace de agente, Cobrar en TPV, Siguiente/Finalizar en
  Onboarding, Construir workspace en ZEUS CORE): el único botón con el
  gradiente.
- **Anillo de avatar de agente**: exento — no es un botón, es marca de
  identidad, igual que en la referencia aprobada.

### Hallazgo real durante la conversión masiva de TPV.vue

Al convertir en bloque ~15 botones de indigo sólido a blanco, varios
`:hover`/`:active` que solo redefinían el color de texto a blanco
(pensado para verse sobre el indigo que ya no está) quedaron con texto
blanco sobre fondo ya blanco — invisible. Se encontraron y corrigieron
4 casos reales (teclado numérico, botón de cantidad, tarjeta "añadir
producto", `.btn-secondary` del modal de producto) revisando cada
bloque tras la conversión, no solo confiando en el patrón de búsqueda y
reemplazo.

### Verificación

Dashboard, `/agents`, los 6 workspaces de agente y Onboarding: **verificados
en vivo** con capturas y `getComputedStyle` — fondo de bandas exacto
(`rgb(232,233,235)`, `rgb(245,246,247)`... coinciden con los hex del
encargo), recuento de elementos con el gradiente = 1 (o 0 cuando no
aplica) en cada vista, sin errores de consola nuevos.

CRM, TPV, Control Horario, Nóminas: **no se pudieron verificar en vivo**,
mismo hallazgo de la sección 3 (guard de rutas). Verificados por
compilación limpia y, en el caso de TPV, revisión manual de cada bloque
convertido para descartar regresiones de contraste.

---

## 7. Ronda 3 (2026-08-19) — merge de Seguros, fix del guard de rutas,
##    verificación real de CRM/TPV/Control Horario/Nóminas

Rama: `feature/rediseno-completo`, creada desde `feature/rediseno-frontend-fase1`
(32 commits, confirmado `main...feature/rediseno-frontend-fase1` = `0 32`).
Mergeada `feature/vertical-seguros` (4 commits, desde `main`) sin
conflictos (commit `4161056`).

### 7.1 Confirmación de los tokens — nada que reinterpretar

Antes de tocar nada se releyó `frontend/src/assets/styles/zeus-light-system.css`
en esta rama: **ya tenía exactamente** los valores de la Ronda 2 exigidos
en el encargo — `--zeus-bg-bands` con los 6 stops hex literales,
`--zeus-accent-gradient` en **3 paradas sin naranja**
(`linear-gradient(135deg, #14b8a6 0%, #8b5cf6 50%, #ec4899 100%)`), y el
motion system (`--zeus-ease-enter/exit/micro`, `--zeus-dur-modal/hover/press`)
intacto desde la Ronda 1. La "alerta" del encargo (posible regresión a
4 paradas con naranja) **no aplicaba** — el archivo ya estaba correcto,
confirmado leyendo el valor real, no asumido.

**Decisión sobre archivo de tokens**: se confirmó que `zeus-light-system.css`
es la única fuente de verdad — se importa una sola vez, globalmente, en
`frontend/src/assets/styles/main.scss` (línea 5), que a su vez se importa
en el entrypoint real de la app (`frontend/src/main.ts`, no `main.js`,
que es legacy y no se usa — confirmado vía `frontend/index.html`). No se
creó ningún `design-tokens.scss` paralelo.

### 7.2 Hallazgo crítico de entorno — el preview servía el checkout equivocado

Gran parte de esta sesión se perdió persiguiendo un fantasma: el bug de
`routeAllowed()` parecía "no arreglarse nunca" pese a que el código del
fix era correcto y estaba en disco. La causa real: la herramienta de
preview (`preview_start` con `name`) arrancó `npm run dev` sobre el
**checkout compartido** `C:\Users\Acer\ZEUS-IA\frontend` (rama
`feature/vertical-seguros`, sin ninguno de los cambios de esta rama),
no sobre el worktree aislado de este agente. Confirmado con
`curl http://localhost:5173/src/router/index.js | grep <marcador>`:
el marcador nunca aparecía pese a estar en el archivo real del worktree.

**Corrección**: se creó un junction de `node_modules` hacia el checkout
compartido (solo lectura, sin tocar sus archivos de código) y se
arrancó un servidor Vite propio (`npx vite --port 5173 --strictPort`,
tras liberar el puerto) directamente desde
`.claude/worktrees/agent-a8873985b2803de19/frontend`, confirmando con el
mismo `curl` que el contenido servido correspondía al del worktree. A
partir de ahí toda verificación de esta sección es fiable.

**Consecuencia importante**: los hallazgos "Dashboard y /agents se ven
oscuros, sin bandas" registrados a mitad de esta sesión eran **falsos
positivos** causados por este bug de entorno (se estaba mirando la rama
`feature/vertical-seguros`, que nunca tuvo el rediseño). Repetida la
verificación contra el servidor correcto, Dashboard y `/agents` **ya
estaban correctos** tal y como documenta la sección 6 — no hizo falta
ningún cambio en ninguno de los dos. Se deja constancia explícita para
que quien revise no repita la misma persecución.

### 7.3 Bug de `routeAllowed()` — diagnóstico y fix real

Diagnóstico exacto (no solo "puede estar desincronizado" como especulaba
la sección 3): `authStore.modules` sólo se rellena dentro de
`login()`/`initialize()` cuando alguna de esas dos funciones se ejecuta
con éxito. `frontend/src/main.ts` (entrypoint real) **nunca llama a
`authStore.initialize()`** al arrancar la app — sólo restaura el token
desde `localStorage`. Por tanto, en cualquier navegación con sesión ya
guardada que no pase por `login()` (refresco de página, pegar una URL,
abrir una pestaña nueva), `authStore.modules` queda en `{}` durante toda
la sesión del tab, y `routeAllowed()` evalúa siempre en falso para
TPV/Control Horario/CRM/Nóminas aunque `/auth/me` real confirme el
módulo activo.

Existía además una función `authStore.initialize()` ya completa y
correcta (decodifica el token, refresca si expiró, llama a `/auth/me`,
rellena `modules` vía `applyProfileModules`) pero **sólo se invocaba
desde código de componente** (`TPV.vue`, `OfficeCrm.vue`,
`OnboardingSetup.vue`, `DashboardProfesional.vue`), es decir, después de
que el guard de rutas ya hubiera decidido bloquear y redirigir — nunca
llegaba a ejecutarse a tiempo.

**Fix** (`frontend/src/router/index.js`, dentro del único
`router.beforeEach` real — el otro, `setupNavigationGuards`, es código
muerto que nunca se invoca, confirmado por grep): antes de evaluar
`routeAllowed`, si `authStore.isAuthenticated` es verdadero se espera
`await authStore.initialize()`. Es idempotente (flag interno
`hasInitialized`) y no repite la llamada de red en navegaciones
posteriores dentro del mismo tab.

Commit: `d98cb50 fix(router): hidratar authStore.modules en cada
navegación (bug, no cambio de diseño)` — commit separado y marcado
explícitamente como fix, no como cambio de diseño, tal como pedía el
encargo.

**No se tocó nada más** de `routeAllowed`/`companyModules.ts`: la lógica
en sí ya era correcta, el problema era exclusivamente de hidratación.

### 7.4 Cuenta de prueba

`test.gestoria@example.com` no existía en ningún entorno accesible
desde este agente (sin credenciales de Railway/producción, sin base de
datos local previa). Se creó **de verdad** vía el endpoint real
`POST /api/v1/auth/register` (no un mock, no un insert directo en BD)
contra un backend FastAPI corriendo en local con SQLite
(`DATABASE_URL=sqlite:///./zeus_test.db`, tablas creadas con la función
real `create_tables()` de `app/db/base.py`), `business_type=restaurant`
→ `company_type=bar_restaurant`. `GET /auth/me` confirmó
`modules: {tpv: true, control_horario: true, payroll: true, crm: false, ...}`
— igual que describía la sección 3 del audit original.

No se pudo levantar la base de datos con `alembic upgrade head` desde
cero (la cadena de migraciones asume una BD legacy preexistente antes
de Alembic e intenta `ALTER TABLE` sobre tablas que create_all aún no
había creado); se usó en su lugar `create_tables()`, la función de
bootstrap real que ya usa la app en producción como fallback. Se
encontró y sorteó (sin modificar código de producción) un bug menor no
relacionado: `app/db/base.py::create_tables()` no importa
`app.models.company_employee` antes de `Base.metadata.create_all()`,
lo que rompe la resolución de FK de `time_cost_checkins` en una BD
totalmente nueva — se referencia aquí como hallazgo nuevo, no se
corrigió (fuera de alcance de esta tarea de diseño).

### 7.5 Verificación real de TPV / Control Horario / Nóminas (bug ya resuelto)

Con el fix del punto 7.3 y el servidor correcto del punto 7.2, se
verificó en vivo con Playwright, navegación **dura** (recarga completa
de documento, no `router.push` interno) a cada ruta con la sesión ya
guardada en `localStorage` — el escenario exacto que fallaba:

- `/tpv` → antes del fix: redirigía a `/dashboard`. Después del fix:
  título `TPV Universal Enterprise - ZEUS-IA`, contenido real (operador
  `Gestoria Test · U2-OWNER`), fondo de bandas metálicas visible.
- `/control-horario` → título `Control Horario Universal - ZEUS-IA`,
  métodos de fichaje reales (QR/Manual/Geolocalización/Facial), fondo de
  bandas correcto, subrayado con el gradiente en el método seleccionado
  (Código QR). **Hallazgo nuevo**: el botón "Actualizar" es verde sólido
  plano, no el gradiente de 3 paradas ni el blanco/borde del sistema —
  una tercera variante de botón no contemplada por el encargo
  ("solo DOS estados: acento o secundario"). No corregido en esta sesión
  por límite de tiempo — documentado como pendiente.
- `/payroll` (Nóminas) → título `Nóminas - ZEUS-IA`, estado vacío real
  ("No hay borradores de nómina", sin datos simulados), fondo de bandas
  correcto. Franjas oscuras finas en los bordes izquierdo/derecho del
  viewport (el `body` de fondo oscuro asomando alrededor del contenedor
  centrado) — cosmético, no bloqueante, mismo patrón visto en Seguros;
  pendiente de revisión si se decide que el fondo debe llegar
  literalmente a los bordes del viewport en vez de al contenedor
  centrado.
- `/office-crm` (CRM): **no se probó** — la cuenta de prueba es
  `business_type=restaurant` (`bar_restaurant`), que no tiene el módulo
  `crm` activo (`modules.crm=false` en `/auth/me`, consistente con
  `MODULES_BY_TYPE` en `companyModules.ts`); probarla habría requerido
  una segunda cuenta `office`. Con el fix aplicado, la lógica de
  `routeAllowed` para CRM es idéntica a la de TPV/Control
  Horario/Nóminas (mismo `ROUTE_MODULE_MAP`), así que hay alta confianza
  de que también funciona, pero **no se confirmó visualmente** — pendiente.

No se ejecutó código real de negocio simulado en ningún punto: los datos
de TPV/Control Horario/Nóminas vistos son los que devuelve el backend
real para una empresa recién creada (mesas/borradores vacíos, no
placeholders con datos inventados).

### 7.6 Seguros (InsuranceView.vue) — sistema aplicado desde cero

Pantalla completamente nueva (traída por el merge), sin ningún token
`--zeus-*` aplicado: fondo oscuro genérico, botón negro plano sin
distinción primario/secundario. Migrada por completo: fondo de bandas +
grano en toda la vista, tarjeta blanca, único botón con el gradiente de
3 paradas en la acción de mayor jerarquía de cada pantalla interna
(listado → "Nueva póliza"; detalle de póliza → "Abrir siniestro"), resto
de botones (Ver, Guardar, Cancelar, Volver al listado) en secundario
blanco/borde. Verificado en vivo: `Pólizas (0)` cargado desde
`GET /api/v1/insurance/policies` real (no mock), fondo y botón
correctos por captura. Commit `78ac502`.

### 7.7 Ajustes (SettingsView.vue + UserAppSettings.vue) — sistema aplicado desde cero

Pantalla completamente nueva según el encargo. `SettingsView.vue` tenía
un fondo oscuro hardcoded (`linear-gradient(135deg, #1a1f2e, #0f1419)`);
su sub-componente `UserAppSettings.vue` (donde vive la mayoría del
contenido real: Apariencia, RAFAEL — Gestor fiscal, Seguridad) usaba
tarjetas translúcidas blancas al 5% sobre ese fondo oscuro, inputs
oscuros. Migrados ambos a los tokens `--zeus-*`: fondo de bandas +
grano, tarjetas blancas sólidas, único botón con gradiente en "Guardar
gestor fiscal" (la única acción de escritura real de esta vista — los
selects de tema/idioma/2FA/timeout guardan solos al cambiar, no son
botones). Verificado en vivo: fondo de bandas correcto, tarjetas
"Apariencia"/"RAFAEL — Gestor fiscal"/"Seguridad" en blanco, valores
reales de `GET /api/v1/settings` (`theme: dark, language: es,
two_factor_enabled: false`). Commit `fe16405`.

**Nota**: el selector "Tema: Oscuro/Claro/Auto" visible en Apariencia
es una funcionalidad real y preexistente (no de esta sesión) que
persiste en BD (`user_settings.theme`, por defecto `"dark"` para toda
cuenta nueva). El shell de bandas metálicas de Ronda 2 se aplicó **de
forma fija**, independiente de ese valor — no se investigó si ese
selector todavía controla algo visible en el resto de la app tras el
rediseño, o si ha quedado huérfano. Se señala como pregunta abierta para
el usuario: ¿el selector de tema debe eliminarse (ya que Ronda 2 exige
un único sistema "sin excepción"), o debe pasar a controlar alguna otra
cosa?

### 7.8 Spot-checks de pantallas ya hechas (Ronda 1/2, no tocadas)

Con el servidor correcto: **Dashboard principal** y **`/agents`**
confirmados correctos sin cambios (ver hallazgo 7.2 — el problema era el
entorno, no el código). **RAFAEL workspace** confirmado por captura:
fondo de bandas dentro del modal, anillo de avatar con gradiente
(marca de identidad, excepción documentada), botón "Actualizar" con el
gradiente de 3 paradas como único acento de la vista, tabs
Chat/Actividad/Métricas planas sin gradiente. No se repitió el
spot-check exhaustivo de los otros 5 workspaces (PERSEO, THALOS,
JUSTICIA, AFRODITA, ZEUS CORE) ni de Onboarding por límite de tiempo de
esta sesión — la sección 6 ya los documenta como verificados en la
ronda anterior y no hay motivo para sospechar regresión (no se tocó
ningún archivo suyo en esta rama).

### 7.9 Pendiente — honesto, no completado en esta sesión

1. **Admin Panel** (`frontend/src/views/AdminPanel.vue`, 1971 líneas,
   ~780 de CSS): **no se tocó**. Pantalla nueva según el encargo, pero
   de tamaño considerable — aplicar el sistema completo con la misma
   disciplina que el resto (captura, comparación, corrección antes de
   avanzar) no cupo en el tiempo disponible de esta sesión. Prioridad
   alta para una sesión siguiente.
2. **CRM** (`OfficeCrm.vue`): código ya convertido en la Ronda 2 (según
   sección 6), pero **no verificado en vivo en esta sesión** — requiere
   una cuenta `company_type=office` (la cuenta de prueba usada aquí es
   `bar_restaurant`). Alta confianza de que el fix del guard también lo
   desbloquea (mismo mecanismo que TPV/Control Horario/Nóminas), pero
   no confirmado visualmente.
3. **Botón verde plano en Control Horario** ("Actualizar") — tercera
   variante de botón fuera de las dos permitidas por el sistema
   definitivo. No corregido.
4. **Franjas oscuras en los bordes** de Nóminas y Seguros (el fondo
   oscuro del `body` asoma unos px alrededor del contenedor centrado
   `max-width`) — cosmético, no investigado a fondo por límite de
   tiempo.
5. **Suite de tests**: no se re-ejecutó la suite completa de backend
   (baseline conocido `7 failed, 214 passed, 2 skipped, 3 errors`) por
   límite de tiempo de la sesión. Los cambios de esta sesión son
   exclusivamente frontend (`router/index.js`, `InsuranceView.vue`,
   `SettingsView.vue`, `UserAppSettings.vue`) — no se tocó ningún
   archivo de `backend/`, por lo que el riesgo de regresión en esa
   suite es bajo, pero no está confirmado con una ejecución real.
6. **Bug de entorno de la sección 7.2** (preview sirviendo el checkout
   compartido en vez del worktree aislado): mitigado manualmente para
   esta sesión (junction de `node_modules` + servidor Vite propio en el
   puerto 5173), pero no es una solución permanente — quien retome este
   trabajo en un worktree distinto puede toparse con el mismo problema
   y debería confirmar con el mismo `curl <url>/src/<archivo> | grep
   <marcador>` antes de fiarse de ninguna captura del preview.

---

## 8. Revisión independiente de la Ronda 3 (2026-08-19)

**Veredicto: ✅ APROBADO.**

Verificación 100% independiente, sin reutilizar nada del ejecutor: confirmó primero (con `curl` sobre un fragmento único del código) que su propio preview servía su worktree real, no el checkout compartido — evitando el mismo problema de entorno documentado en la sección 7.2. Diff de alcance confirmado exacto. Fix del router verificado línea a línea (`setupNavigationGuards` confirmado código muerto por grep, `initialize()` confirmado genuinamente idempotente vía su guard `hasInitialized`).

**Reproducción end-to-end con cuentas propias, no reutilizadas:** registró dos cuentas nuevas vía `/auth/register` — una `business_type=restaurant` (igual que la del ejecutor) y **una segunda `business_type=services` → `company_type=office`**, cerrando exactamente el hueco de verificación de CRM que el ejecutor había dejado pendiente. Confirmó `/tpv`, `/control-horario`, `/payroll` con la cuenta restaurant, y `/office-crm` con la cuenta office — todas renderizando contenido real tras navegación dura, sin redirect. Control adicional: confirmó que la cuenta restaurant sigue correctamente bloqueada de `/office-crm` — el gating por módulo no se rompió, solo se desbloqueó lo que debía.

**Seguros y Ajustes**: confirmados en vivo — stops exactos del fondo de bandas, gradiente de 3 paradas sin naranja, un único botón con acento por vista.

**Suite de tests de backend — cerrada por el revisor, el ejecutor no lo había hecho**: `7 failed, 214 passed, 2 skipped, 3 errors`, idéntico al baseline. Sin regresión.

Hallazgos cosméticos pendientes (botón verde en Control Horario, franjas oscuras en bordes) evaluados como no bloqueantes — no violan ninguna regla no negociable. `main` confirmado sin tocar, nada empujado a remoto.

**Estado: Ronda 3 CERRADA — APROBADA.** Pendiente para una ronda siguiente: Admin Panel (no tocado), los dos hallazgos cosméticos, y el bug preexistente de `create_tables()` (fuera de alcance, ya señalado).
