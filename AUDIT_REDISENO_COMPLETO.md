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

---

## 9. Ronda 4 (2026-08-19/20) — Admin Panel

Rama: `feature/rediseno-completo` (misma de siempre). Objetivo:
`frontend/src/views/AdminPanel.vue`, el componente más grande que
quedaba del alcance original (1971 líneas).

### 9.1 Mapeo antes de tocar nada

Se leyó el archivo completo (template + script + estilos) antes de
escribir ningún CSS. No es una sola pantalla: es una SPA interna con
navegación por sidebar (`currentView`), sin rutas propias, con 4 vistas
+ 2 modales:

1. **Shell/chrome** — sidebar (logo, nav Overview/Clientes/Ingresos/
   Configuración, "Volver al Dashboard") + cabecera móvil (hamburguesa,
   título, "Volver") + fondo del panel. No es una "vista" de contenido,
   pero es una sección natural propia (se repite en las 4 vistas).
2. **Overview** — 4 tarjetas KPI + gráfico de ingresos por mes
   (Chart.js). Solo lectura.
3. **Clientes** — tabla de clientes reales + modal "Ver cliente" +
   modal "Editar cliente" (con zona de superadmin: desactivar/reactivar/
   eliminar cuenta, irreversible).
4. **Ingresos** — resumen de facturación + desglose por plan. Solo
   lectura.
5. **Configuración** — estado de integraciones (Stripe/WhatsApp/
   SendGrid) + botón de verificación E2E real + notificaciones +
   guardar configuración.

Un commit por sección, en ese orden: `0b16359` (shell), `ab339d2`
(Overview), `93d519b` (Clientes+modales), `52d3c33` (Ingresos),
`c76ec9e` (Configuración) — más un commit de fix aparte, `2ed1369`
(ver 9.4).

### 9.2 Entorno — mismo bug de la Ronda 3, mitigado de forma más robusta

Al retomar la tarea los servidores de la Ronda 3 ya no existían
(reinicio de sesión). Al reconstruirlos se repitió el problema conocido
del junction de `node_modules` apuntando al checkout compartido: otro
proceso había reinstalado ese `node_modules` entre sesiones y el
junction quedó roto (`Cannot find package '...vite/index.js'`).
Esta vez, en lugar de repetir el parche frágil, se resolvió de raíz:
`npm install` genuinamente dentro del worktree aislado (901 paquetes,
~8 min), sin depender en absoluto del checkout compartido. Confirmado
de nuevo con `curl http://localhost:5173/src/router/index.js | grep
<marcador>` antes de fiarse de ninguna captura.

### 9.3 Cuenta de superusuario — el bug conocido NO se reprodujo

Se creó `admin.test@example.com` vía el flujo real de dos pasos: (1)
`POST /api/v1/auth/register` (crea usuario + empresa transaccionalmente,
igual que `test.gestoria@example.com` en rondas anteriores), (2)
`UPDATE users SET is_superuser=1` directo en SQLite (no existe endpoint
público para crear superusuarios, por diseño de seguridad correcto; el
script `create_user.py` del repo falló por el mismo problema de import
order de modelos ya documentado en la sección 7.4, se evitó en vez de
depurarlo por no ser parte del alcance).

Se decidió **deliberadamente** que la cuenta tuviera una `Company`
asociada real (paso 1) precisamente para evitar el bug conocido
descrito en `CICLO_PRODUCCION.md` (superusuario sin `Company` atrapado
en el wizard de onboarding). Verificado en vivo: login con esta cuenta
aterriza directo en `/dashboard`, sin pasar por `/onboarding-setup` —
**el bug no se reprodujo** con esta cuenta. No se puede afirmar que el
bug esté arreglado (no se tocó `Login.vue` ni el guard del router para
esto), solo que la mitigación elegida (cuenta con `Company`) fue
suficiente para completar la verificación de Admin Panel sin bloqueos,
tal como preveía la instrucción del encargo. El bug de fondo
(`Login.vue` no comprueba `isAdmin` antes de llamar a
`resolvePostAuthPath()`) sigue sin arreglar y sigue fuera de alcance de
esta ronda.

### 9.4 Regla del botón vibrante aplicada vista por vista

- **Shell**: nav del sidebar = selección dentro de un grupo → sin
  gradiente, tinte índigo suave + negrita en el activo (mismo patrón
  que tabs en rondas anteriores). "Volver al Dashboard"/"Volver" →
  secundario.
- **Overview**: sin acción real (solo lectura) → 0 botones con
  gradiente, válido según la regla ya documentada en la Ronda 2.
- **Clientes** (vista lista): "Actualizar" (utilidad repetible) y
  Ver/Editar/Pausar (repetidas por fila) → todo secundario, 0 gradiente
  en la lista. El gradiente vive en los dos modales, cada uno su propia
  vista: "Editar / Gestionar" en el modal Ver, "Guardar" en el modal
  Editar (mutuamente excluyentes, nunca los dos gradientes a la vez).
  La zona de superadmin (Desactivar/Eliminar cuenta) se mantiene en rojo
  secundario, deliberadamente sin el gradiente festivo — una acción
  destructiva irreversible no debe compartir el acento de una acción de
  guardado.
- **Ingresos**: solo lectura → 0 gradiente.
- **Configuración**: "Verificar E2E" es diagnóstico gratuito y
  repetible (no muta nada) → secundario. "Guardar configuración" es la
  única escritura real de la vista → el único gradiente.

### 9.5 Hallazgo real encontrado y corregido en el camino

Al migrar `.chart-section` de tarjeta oscura a superficie blanca
(commit `ab339d2`), la configuración **JavaScript** de Chart.js
(leyenda, ticks de los ejes, mensaje de "sin datos" dibujado
directamente en el canvas) seguía usando `rgba(255,255,255,*)` —
pensada para el fondo oscuro anterior. Resultado: texto blanco sobre
tarjeta blanca, invisible. No es un descuido de CSS (el CSS scoped no
alcanza al contenido dibujado en un `<canvas>`), había que tocar el
JS. Encontrado por spot-check visual real (no habría aparecido en
ningún grep de CSS) y corregido en un commit de fix aparte (`2ed1369`),
igual que se hizo con el bug de `routeAllowed()` en la Ronda 3.
Verificado en vivo: el mensaje "No hay datos para mostrar" pasó de
(previsiblemente) invisible a legible en gris sobre blanco.

### 9.6 Verificación funcional real (no solo visual)

Con la cuenta superusuario, además de la comparación visual en cada
sección:

- **Clientes**: clic en "Ver" abrió el modal con datos reales de un
  cliente real (registro de prueba creado vía el flujo real de Stripe
  checkout, no un mock — visible el email sintético
  `zeus-tx-...@test.local` típico de esos tests). Clic en "Editar /
  Gestionar" navegó correctamente al modal de edición. Clic en
  "Cancelar" cerró el modal (confirmado leyendo el árbol de
  accesibilidad antes/después — el botón desapareció de la lista de
  controles interactivos). El cambio de CSS no rompió ningún
  manejador de eventos.
- **Configuración**: clic en "Verificar E2E (sin cargo)" disparó un
  `POST /api/v1/test/integrations-e2e` real (200 OK, confirmado en
  `read_network_requests`) y el resultado real de la verificación
  (`5/9 OK · Externas listas`, checks reales contra Stripe/Twilio/
  SendGrid) se renderizó correctamente con los nuevos estilos — no se
  probó solo que el botón "se viera bien", se confirmó que sigue
  ejecutando la acción real contra el backend.
- **Overview**: `stats.totalCustomers` mostró cifras reales (50 y luego
  97, cambiando entre sesiones según el estado real de la base de
  datos — no un valor fijo).

No se probó explícitamente el flujo de "Guardar configuración" ni las
acciones irreversibles de la zona de superadmin (Desactivar/Eliminar
cuenta) para no mutar datos de prueba de forma destructiva sin
necesidad — se verificó que los botones existen, tienen el estilo
correcto y no están rotos (clicables, `:disabled` respetado), pero no
se ejecutó su acción final. Se señala explícitamente como límite de
esta verificación.

### 9.7 Suite de tests

Ejecutada dos veces durante esta ronda (no se dejó para el final):
tras la sección 3 (Clientes) y de nuevo al terminar. Ambas veces
idéntica al baseline conocido: `7 failed, 214 passed, 2 skipped, 3
errors`. Sin regresión — coherente con que ningún archivo de `backend/`
se tocó en esta ronda.

### 9.8 Limpieza de entorno

El `npm install` local generó un cambio trivial en
`frontend/package-lock.json` (una entrada `"dev": true` →
`"devOptional": true` de un paquete, normalización propia de npm, no un
cambio de versión real). Revertido con `git checkout --
frontend/package-lock.json` antes de cerrar la ronda — no formaba parte
del encargo y no debía quedar en el commit.

### 9.9 Pendiente — honesto

1. **Botones "Desactivar cuenta"/"Eliminar cuenta y empresa"**: estilo
   verificado, acción real no ejecutada (ver 9.6) — quien revise puede
   querer confirmarlo explícitamente con una cuenta de prueba
   desechable.
2. **"Guardar configuración"**: estilo verificado, acción de guardado
   no confirmada end-to-end (no se leyó de vuelta el valor persistido).
3. Los hallazgos cosméticos de la Ronda 3 (botón verde en Control
   Horario, franjas oscuras en bordes de Nóminas/Seguros) siguen sin
   tocar — no eran parte del encargo de esta ronda.
4. El bug de `Login.vue`/`resolvePostAuthPath()` para superusuarios sin
   `Company` (CICLO_PRODUCCION.md, Ciclo 4) sigue sin arreglar — se
   confirmó que no bloquea con la cuenta de prueba usada aquí, pero
   sigue afectando potencialmente a superusuarios reales sin empresa
   asociada en producción.
5. Con esto se completan las 7 categorías del alcance original del
   encargo de rediseño: Dashboard, `/agents`, los 6 workspaces, Seguros,
   CRM/TPV/Control Horario/Nóminas, Onboarding, y Admin Panel/Ajustes.

**Estado: Ronda 4 (Admin Panel) — completada, pendiente de revisión
independiente.**

---

## 10. Revisión independiente de la Ronda 4 — CIERRE DEL ENCARGO COMPLETO (2026-08-20)

**Veredicto: ✅ APROBADO.**

Verificación 100% independiente, worktree y servidor propios (confirmó con `curl` sobre un fragmento único del fix de Chart.js que su preview servía el commit real antes de fiarse de nada visual). Diff exacto confirmado (solo `AdminPanel.vue` + el doc, `package-lock.json` ausente). Mapeo de secciones confirmado real leyendo los 6 diffs completos — y confirmó además, por grep, que ninguno de los 6 commits toca lógica de `<script>`, solo clases/estilos (el riesgo de romper funcionalidad con estos cambios es estructuralmente bajo).

**Bug de fondo reproducido en vivo, no solo citado:** el revisor fue más allá de lo pedido — además de confirmar que su cuenta de superusuario con `Company` aterriza en `/dashboard` (rastreó la causa exacta: `GET /auth/onboarding/status` infiere `setup_completed` de la presencia de `company_employees`/`tpv_products` sembrados en el registro), creó una SEGUNDA cuenta, le quitó el vínculo `user_companies`, la promovió a superusuario, y confirmó por API que `setup_completed:false, company_linked:false` — es decir, **el bug de `CICLO_PRODUCCION.md` (Ciclo 4) sigue vivo, confirmado de primera mano**, no arreglado (correctamente fuera de alcance de esta ronda de diseño).

**Verificación visual y funcional**: las 5 secciones confirmadas contra la referencia (conteo exacto de botones-con-gradiente por sección, tal como describía el ejecutor). Única limitación declarada: no pudo completar el click-through visual de "Configuración" por un límite de viewport de su propio navegador de revisión (629×275px, sin relación con el código) — lo compensó leyendo el diff línea a línea y disparando directamente el mismo endpoint que llama el botón, confirmando 200 real con checks reales de Stripe/Twilio/SendGrid/OpenAI/Postgres. Fix de Chart.js confirmado legible en vivo. Modal "Ver"/"Editar" con datos reales, guard de superadmin genuino confirmado ("No se puede modificar ni eliminar un superusuario desde aquí"). Suite de tests idéntica al baseline, corrida de forma independiente.

## Ronda 4 — CERRADA

**Rama final:** `feature/rediseno-completo`, commits `0b16359`→`ea425ab` (sobre `81e03db`, Rondas 1-3). Sin merge ni push a `main`.

---

## CIERRE DEL ENCARGO COMPLETO — valoración final (revisor-independiente, Ronda 4)

Con esta ronda se cierran las 7 categorías del alcance original: Dashboard, `/agents`, los 6 workspaces de agente, Seguros, CRM/TPV/Control Horario/Nóminas, Onboarding, y Admin Panel/Ajustes — ~19 pantallas en total, a lo largo de 4 rondas de trabajo, cada una con al menos una vuelta de devolución real y corrección antes de aprobarse (excepto la Ronda 4, aprobada a la primera).

**Lo sólido**: un sistema de diseño único, consistente, y verificado en código real en las ~19 pantallas — bandas metálicas exactas, gradiente de 3 paradas teal→morado→rosa, regla de "un solo botón vibrante por vista" aplicada con criterio documentado y defendible en cada caso, no una pasada superficial. Cada ronda encontró y corrigió al menos un bug real en el camino, no solo cambios cosméticos: `css_system_enforcer_v1.css` forzando botones negros (Ronda 1-2), `authStore.modules` sin hidratar bloqueando CRM/TPV/Control Horario/Nóminas para toda la app (Ronda 3, bug de infraestructura real, no solo de diseño), y el texto invisible de Chart.js (Ronda 4).

**Pendientes conocidos, ninguno bloqueante, para decisión del usuario:**
1. Botón verde plano en "Actualizar" de Control Horario — tercera variante fuera de la regla de dos estados (acento/secundario).
2. Franjas oscuras cosméticas en los bordes de Nóminas y Seguros (el fondo del `body` asoma alrededor del contenedor centrado).
3. El selector "Tema: Oscuro/Claro/Auto" en Ajustes quedó con propósito huérfano tras fijar un único sistema visual "sin excepción" — decidir si eliminarlo o si debe controlar otra cosa.
4. **El bug estructural de superusuario sin `Company`** (`Login.vue`/`resolvePostAuthPath()`, `CICLO_PRODUCCION.md` Ciclo 4) — confirmado vivo de primera mano en esta ronda, ajeno al rediseño, afecta potencialmente a cualquier superusuario real sin empresa asociada en producción.
5. Acciones irreversibles de Admin Panel (Desactivar/Eliminar cuenta) y "Guardar configuración" — estilo verificado, acción final no ejecutada en ninguna ronda por no mutar datos destructivamente sin necesidad; bajo riesgo dado que ningún commit de diseño tocó lógica de `<script>`, pero sigue sin confirmación end-to-end explícita.

---

## 11. Encargo de seguimiento (2026-08-20) — Bloque 1 Control Horario + Bloque 2 TPV

El encargo cerrado en la sección 10 dejó dos bugs reales anotados (no solo
estéticos) para una vuelta adicional: el solapamiento/hueco vacío de Control
Horario, y el TPV sin terminar de pasar por la limpieza de iconos y jerarquía
visual del resto de la app. Esta sección documenta esa vuelta, ejecutada en
dos bloques atómicos separados.

### 11.1 Bloque 1 — Control Horario (commit `e113132`)

Bugs reales reportados por el usuario, no solo estética:

1. **Solapamiento en todos los anchos de pantalla, no solo móvil**: el botón
   "Volver al Dashboard" era `position:fixed` en `(20,20)`, exactamente donde
   arranca el título "Control Horario Universal" → se solapaban
   estructuralmente en cualquier ancho de viewport (el bug no era de
   breakpoint). Corregido pasándolo a flujo normal (mismo patrón que
   Seguros/Ajustes/agents: botón "volver" antes de la cabecera, con
   `margin-bottom`) — elimina la clase entera de solapamiento, no un parche
   puntual para móvil.

2. **Hueco vacío tras el scroll**: `.status-panel` y `.history-panel`
   comparten fila en un grid de 2 columnas sin `grid-column` propio → CSS
   Grid las estira por defecto (`align-items:stretch`) a la altura de la más
   alta de las dos. Cuando una lista es mucho más corta que la otra (pocos o
   ningún empleado dentro vs. varios registros de historial), la tarjeta
   corta quedaba con un hueco en blanco al final. Corregido con
   `align-items:start` en `.control-horario-main-interface`.

3. **Emojis → iconos SVG de línea limpia** en "Selecciona método de fichaje"
   (los 5: Facial/QR/Manual/Geolocalización/Remoto, no solo los 4
   mencionados literalmente en el encargo original). Criterio de icono:
   SVG inline (heroicons-style, sin dependencia nueva) en vez de instalar
   `lucide-vue-next` — FontAwesome ya está en `package.json` pero solo
   registrado en `main.js`, el entrypoint legacy que NO se usa (confirmado:
   `main.ts`, el real, no lo importa); arreglar ese registro habría
   significado tocar un archivo compartido fuera de alcance. El SVG inline
   además ya es el patrón establecido en el repo (`Login.vue`,
   `Register.vue`, `LandingPage.vue`).

4. **Verificación real de los 5 métodos de fichaje** (no solo que el botón
   cambia de estado visual):
   - **Geolocalización**: real — usa la Geolocation API real del navegador.
   - **Código Manual (PIN)**: real — el PIN se valida de verdad contra el
     backend; confirmado que un PIN incorrecto lo rechaza.
   - **Reconocimiento Facial**: **COSMÉTICO**. Está mapeado internamente al
     mismo tipo genérico `"device"` que Remoto
     (`V1_METHOD_MAP.face === V1_METHOD_MAP.remote`), sin pedir cámara ni
     capturar nada — confirmado con la consola del navegador: cero actividad
     de cámara al seleccionarlo.
   - **Código QR**: **COSMÉTICO**. Genera un token fabricado en el cliente
     (`ui-{empleado}-{timestamp}`) sin escanear nada, y el backend solo
     valida que el string no esté vacío — confirmado con `POST` directo a
     `/api/v1/checkin`: acepta cualquier string como `qr_token` válido.
   - Reportado explícitamente, no oculto, no corregido en esta vuelta
     (arreglar biometría/scanner real es un cambio de alcance mucho mayor,
     fuera de esta tarea de diseño). Verificado en vivo con Playwright
     (`test.gestoria@example.com`) combinando interacción real en navegador
     (consola sin actividad de cámara) y llamadas `POST` directas a
     `/api/v1/checkin` con los mismos payloads exactos que construye el
     frontend (`services/time_cost_engine_v1.py` confirma la lógica real de
     validación/no-validación del lado del servidor).

5. **De paso** (pendiente anotado en Ronda 3): botón "Actualizar" verde
   plano → secundario blanco/borde (no es la acción de mayor jerarquía de la
   vista). También corregido en el mismo bloque: la barra `::after` con
   gradiente del selector de método activo usaba el valor obsoleto de 4
   paradas con naranja de Ronda 1 (ni coincidía con `--zeus-accent-gradient`
   actual) y violaba la regla de "selección dentro de un grupo = sin
   gradiente" → eliminada, queda solo borde+fondo con tinte índigo.

**Archivo tocado**: `frontend/src/views/ControlHorario.vue` (98 líneas, +58/-40).
**Commit**: `e1131324b27afdc3fa8df380ad69c273d8a4e4ef`.

### 11.2 Bloque 2 — TPV (este agente, commit ver 11.4)

Trabajo retomado de una sesión anterior cortada por límite de API: había un
diff parcial sin commitear (132 inserciones / 61 borrados) que ya cubría el
grueso de la sustitución de emojis del header y del carrito. Esta vuelta lo
completó y verificó de punta a punta.

**1. Emojis → SVG, barrido completo del archivo.** Además de lo que ya traía
el diff parcial (📊 dashboard, 💳 título, 🪑 mesas, 🔗 compartir, 🔄 refrescar,
✏️/🗑️ CRUD de producto, ➕/➖ cantidad, 🖨️/🏷️/✅ acciones de venta), se
localizaron y reemplazaron con un escaneo Unicode completo del archivo
(no solo grep de emojis conocidos, un rango `>= U+2190` completo para no
depender de una lista de memoria):
- Botones "Mesas"/"Cancelar" con flecha `←` → SVG de flecha.
- `📦`/`⚠️` en mensajes vacíos y de error de la grilla de productos.
- `📅` en "Reservas del día".
- `🟢 Ocupada` / `⚪ Libre` de las tarjetas de mesa → sustituido por un punto
  de estado CSS (`.table-status-dot`, color por clase `.occupied`/`.free`)
  en vez de emoji, más consistente con cómo el resto de la app comunica
  estado (ver verificación visual en 11.3).
- `🛒`/`💡` del carrito vacío, `🆕`/`🧾` de "Nueva venta"/"Generar factura",
  `❌` del overlay de error, `✏️`/`➕`/`✕` del modal de producto (título y
  botón cerrar), `✕` del modal de cambio de operador.
- **Iconos de categoría de producto** (`getProductIcon`/`getIconEmoji`, ~17
  categorías: bebida, alcohol, café, bocadillo, pizza, tapa, plato, postre,
  ensalada, servicio, consulta, tratamiento, corte, repuesto, entrada,
  medicamento, envío/genérico): antes devolvían directamente el carácter
  emoji; ahora devuelven una *clave* (`getProductIconKey`/`getIconKey`) que
  indexa un diccionario `PRODUCT_ICON_PATHS` de paths SVG, renderizados con
  `v-for` sobre `<path>` en el template. La lógica de detección por palabra
  clave (`normalizeCategory`, reglas de coincidencia) se mantuvo 100%
  intacta — es un cambio de *representación* del icono, no de la lógica de
  categorización, verificado en vivo (ver 11.3: "Bebidas" muestra un vaso,
  "Tapas" muestra una brocheta con dos piezas).

**No tocado deliberadamente**: los símbolos `⌫` (borrar) y `✓` (enter) del
teclado numérico tipo calculadora (`keyboardLayout`, `handleKeyPress`) — son
el propio texto funcional de las teclas de un teclado numérico, mismo
patrón que cualquier calculadora, no emoji decorativo. Tampoco se tocaron
los emojis dentro de `console.log`/`console.warn`/`console.error` (~60
apariciones) — son prefijos de depuración interna sin salida visible para
el usuario final, fuera del alcance de un rediseño de UI; tocarlos habría
sido una limpieza no pedida en ~60 líneas sin relación con el encargo.

**2. Jerarquía visual / flujo de venta.** Revisado explícitamente: el botón
de cobro (`REVISAR Y PAGAR` → `CONFIRMAR PAGO` → `FINALIZAR PAGO` según el
estado `CART`/`PRE_PAYMENT`/`PAYMENT`) ya era, de rondas anteriores, la
única acción con `.pay-btn` (gradiente de 3 paradas teal→morado→rosa,
`--zeus-accent-gradient`); el resto de acciones (Imprimir Comanda,
Descuento, Volver al Carrito, Cancelar, Generar Factura) ya usaban
`.secondary-btn`/`.header-btn` neutro blanco/borde. Es decir, la regla de
"un solo botón vibrante por vista" que rige el resto del rediseño **ya
estaba aplicada correctamente en TPV desde antes** — no fue necesario
reestructurar la jerarquía, solo confirmarla en vivo (ver 11.3) y terminar
de vestirla con iconos SVG. La agrupación de categorías (pestañas
Bebidas/Tapas/Todos) y la tarjeta "Añadir Producto" ya existían y se
mantienen igual.

**3. Tokens `--zeus-*`.** Auditado el bloque `<style scoped>` completo
buscando colores hexadecimales fuera de `var(--zeus-*)`: se encontraron 37
apariciones heredadas de rondas anteriores (no introducidas por este
diff). De ellas:
- `background: #ffffff` (12×) → `var(--zeus-surface, #ffffff)` — sin
  cambio visual, `--zeus-surface` ya vale `#ffffff`.
- `color: #fff` (8×, texto sobre fondo de acento) → `var(--zeus-text-on-accent, #fff)` — sin cambio visual, mismo valor.
- `border: 1px solid #D1D5DB` (7×, borde de campos de formulario) →
  `var(--zeus-border-strong, #D1D5DB)` — diferencia de color imperceptible
  (`#D1D5DB` vs. `#cdd3db`, mismo gris neutro), pero ahora sigue el token
  compartido en vez de un valor suelto.
- El nuevo `.table-status-dot` (introducido en este bloque) también se
  tokenizó igual: `var(--zeus-border-strong, #cbd5e1)`.
- **No tocado deliberadamente**: `border-color: #9aa2af` (9×, estado
  `:hover`/`:focus` de esos mismos campos). No hay token compartido que
  represente ese nivel de contraste — `--zeus-border-strong` (`#cdd3db`) es
  visiblemente más claro y habría debilitado el feedback de hover existente.
  Introducir un token nuevo para esto sería trabajo de sistema de diseño
  fuera del alcance de esta tarea (y la instrucción explícita de no hacer
  refactors no pedidos); se deja anotado como pendiente menor, no bloqueante.

**Archivo tocado**: `frontend/src/views/TPV.vue`.

### 11.3 Verificación en vivo — flujo de venta completo (Bloque 2)

Bloqueo inicial real, no simulado: al confirmar el primer pago, el backend
devolvió `502 Bad Gateway` con
`Error de persistencia fiscal: 'charmap' codec can't encode characters in
position 0-1: character maps to <undefined>`. Rastreado en el log del
servidor hasta un `print()` con emoji (`🏛️ [ZEUS] Agente RAFAEL...`) en
`backend/agents/base_agent.py:41`, disparado la primera vez que se
instancia el agente RAFAEL (patrón singleton perezoso en
`services/rafael_service.py:get_rafael_agent()`), que revienta porque la
consola de Windows de este entorno no usa UTF-8 por defecto (`cp1252`).
**Es un bug de backend preexistente y no relacionado con este diff** (el
diff de este bloque es 100% `frontend/src/views/TPV.vue`; confirmado además
que la venta se revirtió correctamente — `TPV venta revertida: error
fiscal` — sin dejar estado corrupto). Para no quedar bloqueado en la
verificación del flujo, se reinició el backend con
`PYTHONIOENCODING=utf-8` (no es un fix del bug, solo una forma de rodearlo
para esta sesión de pruebas) — con eso el resto del flujo se completó real
contra el backend real:

- Cuenta de prueba creada de verdad vía `POST /api/v1/auth/register`
  (`tpv.redesign.test@example.com`, empresa `restaurant`), no un insert
  directo en BD.
- Login real, navegación a `/tpv`, carga real de 4 productos desde
  `GET /api/v1/tpv/products` (log del servidor: `Listando 4 productos para
  usuario 2`).
- **Añadir producto → carrito**: clic en "Refresco" (categoría "Bebidas",
  icono SVG de vaso renderizado correctamente) → aparece en el carrito con
  cantidad 1, subtotal/IVA/total recalculados en vivo.
- **Cobro completo**: `REVISAR Y PAGAR` → `PRE_PAYMENT` → `CONFIRMAR PAGO` →
  `PAYMENT` → `FINALIZAR PAGO` → `POST /api/v1/tpv/sale` responde `200 OK`
  real. Toast de éxito real: *"Pago procesado exitosamente. Ticket
  #TICKET_20260820115515. Total: EUR 5,32. Esta venta se ha registrado
  automáticamente con RAFAEL."* Confirmado en el log del servidor: entrada
  real en `cashflow_ledger_service` (`entry id=1 company=1 in 5.32 source=TPV`),
  actividad real registrada por RAFAEL y JUSTICIA (`[ACTIVITY] RAFAEL: Venta
  TPV registrado en RAFAEL: TICKET_20260820115515`), no un mock.
- **Modo Mesas**: seleccionada Mesa 1 (estado inicial "Libre", punto gris),
  añadido un producto a la mesa, vuelto a la vista de mesas → Mesa 1 pasó a
  "Ocupada" con el punto verde y el total real (`€1,65`) — confirma que el
  nuevo `.table-status-dot` (reemplazo del emoji 🟢/⚪) refleja el estado
  real del backend, no un valor fijo.
- Consola del navegador revisada tras cada paso: sin warnings de Vue
  (duplicidad de `key`, componente no resuelto, etc.) atribuibles a los
  cambios de este bloque; los únicos errores presentes en el buffer son
  preexistentes y ajenos (`shouldShowTPV is not defined` en
  `DashboardProfesional.vue`, claves de i18n `tpv.shareComandero` sin
  traducir, y el error fiscal de antes del reinicio con `PYTHONIOENCODING`).

**Confirmación de que el preview servía este worktree y no el checkout
compartido**: antes de fiarse de cualquier captura, se hizo
`curl http://localhost:5173/src/views/TPV.vue | grep getProductIconPaths`
(y `table-status-dot`) contra el servidor Vite ya corriendo en el puerto
5173 — ambos marcadores únicos de esta sesión aparecieron, confirmando que
el dev server servía el árbol de trabajo de este worktree.

**Regresión — suite de tests backend**: baseline conocido
`7 failed, 214 passed, 2 skipped, 3 errors`. Ejecutada tras el bloque 2:
resultado idéntico, `7 failed, 214 passed, 2 skipped, 3 errors` — mismos 7
tests fallidos, mismos 3 errores, ninguna diferencia. Sin regresión (y
esperable: el diff de este bloque no toca ningún archivo de `backend/`).

### 11.4 Estado de commits y pendientes de esta vuelta

- Bloque 1 (Control Horario): commit `e1131324b27afdc3fa8df380ad69c273d8a4e4ef`, ya en la rama antes de que empezara este agente.
- Bloque 2 (TPV): commit atómico separado, creado por este agente tras esta verificación (ver mensaje de commit para el hash exacto).
- Rama: `feature/rediseno-completo`. Sin merge ni push a `main` en ningún momento.

**Hallazgo nuevo para decisión del usuario (no corregido en esta vuelta,
fuera de alcance de un encargo de diseño frontend)**: el bug de
codificación `charmap`/`cp1252` en `backend/agents/base_agent.py:41`
(`print()` con emoji sin forzar UTF-8) puede tumbar **cualquier venta real
de TPV** la primera vez que se instancia el agente RAFAEL, en cualquier
entorno Windows donde el proceso Python no tenga `PYTHONIOENCODING=utf-8`
explícito — incluyendo, potencialmente, un despliegue en un contenedor o
servicio Windows en producción con la misma configuración regional por
defecto. Es un bug de infraestructura/backend real, no de este rediseño;
requiere decidir si se corrige ahora (candidato sencillo: forzar
`sys.stdout.reconfigure(encoding="utf-8")` al arrancar la app, o quitar los
emojis de los `print()` de arranque de agentes) o se deja anotado como
tarea nueva para el flujo de auditoría de producción.

**Pendiente menor, no bloqueante**: `border-color: #9aa2af` en TPV (9
apariciones, estado hover/focus de campos de formulario) sin token
`--zeus-*` equivalente — ver 11.2.

---

## 12. Revisión independiente de los Bloques 1+2 — Control Horario y TPV (2026-08-20)

**Veredicto: ✅ APROBADO.**

Verificación 100% independiente, con tenants propios distintos a los del ejecutor en cada prueba. Diff confirmado exacto (`ControlHorario.vue`, `TPV.vue`, doc). Fix del solapamiento confirmado estructural (no depende de breakpoint). Fix del hueco vacío confirmado por código/semántica CSS (`align-items:start` es la corrección estándar e inequívoca); no se pudo capturar visualmente el grid de 2 columnas por una limitación de viewport del propio navegador de revisión (629px, por debajo del breakpoint de 768px) — limitación del entorno de revisión, no del fix.

**Punto más importante — honestidad de los 5 métodos de fichaje, verificado de forma independiente y multi-ángulo:** confirmado por código (`face === remote` en `V1_METHOD_MAP`, sin ningún `getUserMedia` en todo el archivo), por backend (`qr_token` sin validar contenido real, `pin` sí verificado con bcrypt), y **por prueba propia con curl** contra un tenant nuevo: `POST /checkin` con un `qr_token` inventado → `200 OK`, confirmando sin ambigüedad que el backend acepta cualquier string. PIN incorrecto correctamente rechazado (`422`). De paso, probó también aislamiento multi-tenant en este endpoint (no pedido explícitamente) — confirmado correcto en ambas direcciones.

**Venta TPV verificada de extremo a extremo con tenant propio**: `POST /tpv/sale` real, ticket real, `accounting_sent:true`, `fiscal_document_persisted:true`, actividad real de RAFAEL/JUSTICIA en logs.

**Bug de codificación `cp1252` — severidad AGRAVADA respecto al informe original**: reproducido de forma independiente (backend reiniciado sin `PYTHONIOENCODING=utf-8`, mismo 502 con el mismo traceback exacto). El revisor fue más allá y repitió la venta una segunda vez: **volvió a fallar** — el bug no es "solo la primera vez", es **permanente**, porque el singleton `_rafael_instance` nunca llega a asignarse (la excepción salta dentro del propio constructor). **El 100% de las ventas TPV quedan bloqueadas en cualquier entorno Windows sin UTF-8 forzado**, no solo el intento inicial. Confirmado que la venta se revierte limpiamente sin dejar estado corrupto.

Suite de tests idéntica al baseline. `border-color:#9aa2af` sin token (9 apariciones, hover) confirmado como pendiente menor no bloqueante.

## Bloques 1+2 — CERRADOS

**Rama final:** `feature/rediseno-completo`, commits `e113132` (Control Horario) + `0081145` (TPV) + `447995d` (docs) sobre `4b50ae3` (cierre de las 4 rondas). Sin merge ni push a `main`.

### 🔴 Recomendación de prioridad alta del revisor, no bloqueante para este cierre pero urgente para producción

`backend/agents/base_agent.py:41` — un `print()` con emoji revienta la consola en Windows (cp1252) al instanciar RAFAEL, bloqueando el 100% de las ventas TPV de forma permanente en cualquier despliegue Windows sin `PYTHONIOENCODING=utf-8` explícito. Afecta a RAFAEL, agente compartido por más de una vertical (Facturación, TPV, y potencialmente Seguros al reutilizar el mismo motor fiscal). Candidato a tarea de máxima prioridad en el flujo de producción del núcleo, fuera del alcance de esta rama de diseño frontend.
