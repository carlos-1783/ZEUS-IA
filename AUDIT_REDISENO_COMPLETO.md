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
