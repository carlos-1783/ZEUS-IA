# Auditoría — Rediseño de tarjetas de agente (Dashboard + /agents)

Rama: `feature/consolidacion-final`
Commits de esta tarea:
- `faf05b6` — style(design-system): fondo compartido con más contraste de metal cepillado
- `5bae5bd` — feat(dashboard): estado real, badge BETA, dinamismo CSS y grid 2 columnas en tarjetas de agente
- `6cec4fb` — feat(agents): convertir lista plana en tarjetas de agente con avatar, estado real y grid 2 columnas

No se tocó `main`, no se hizo push, no se creó rama nueva (se trabajó en `feature/consolidacion-final`, ya existente, partiendo del commit `6f09903`).

## 0. Contexto y limitación explícita

No había ninguna referencia visual adjunta para este encargo (se mencionó al
principio pero nunca se adjuntó). Las decisiones de diseño de abajo se
tomaron con el criterio de `frontend-design`, siempre copiando literalmente
los tokens ya definidos en `frontend/src/assets/styles/zeus-light-system.css`
y el patrón ya aprobado en `frontend/src/views/InsuranceView.vue` — no se
inventó ningún color, curva de movimiento o patrón de layout nuevo.

**Limitación acordada con el usuario**: no hay modelo de generación de
imágenes disponible en este entorno. Los avatares de agente
(`frontend/public/images/avatars/*.jpg`) son fotos/renders ya existentes y
no se podían sustituir por ilustraciones nuevas. La instrucción explícita
fue aplicar **efectos CSS sobre las imágenes ya existentes** para sugerir
personalidad/dinamismo — eso es lo que se implementó (ver punto 2).

## 1. Dónde viven las tarjetas de agente (auditoría antes de tocar)

- `/dashboard` → `OlymposDashboard.vue` (ver `frontend/src/router/index.js:214-222`).
  Este componente tiene dos modos: `firstPersonMode` (3D, por defecto) que
  monta `DashboardProfesional.vue`, y un modo 2D (`v-else`) con "agentes
  paseando". **`firstPersonMode` está fijado a `true` en un `ref()` y nunca
  se reasigna en ningún sitio del archivo** (`grep firstPersonMode` solo
  devuelve la declaración y los dos usos en el propio `v-if`/`v-else`) — el
  modo 2D es código muerto, nunca se renderiza. Las tarjetas reales que ve
  cualquier usuario están en `frontend/src/components/DashboardProfesional.vue`,
  bloque `<section class="agents-grid executive-agents-grid">`
  (línea ~192 antes de este cambio).
- `/agents` → `frontend/src/views/kpi/KpiAgentsView.vue` (ver
  `frontend/src/router/index.js:267-272`), un componente **distinto** al
  del Dashboard, tal como advertía el encargo. Antes de este cambio no
  tenía tarjetas en absoluto: era una lista de filas de texto
  (`<ul class="kpi-list"><li class="kpi-list-item">`) sin avatar, sin punto
  de estado y sin badge — solo nombre, rol, pill de estado y tres métricas
  en columnas.

Ambas vistas consumen el mismo endpoint real `GET /api/v1/agents/status`
(`backend/app/api/v1/endpoints/agents.py`), que calcula `status` (online si
hay actividad en las últimas 24h, idle si hay actividad en 30 días pero no
en 24h, offline si no hay ninguna) directamente desde `agent_activities` —
confirmado leyendo el código del endpoint, no asumido.

## 2. Cambios implementados

### 2.1 Fondo compartido — metal cepillado con más contraste
`frontend/src/assets/styles/zeus-light-system.css:18-33`

- `--zeus-bg-bands`: mismas 6 paradas/posiciones de banda, valores más
  extremos (highlights hacia `#FAFBFC`, sombras hacia `#B8BCC2`, antes
  `#F5F6F7`/`#C9CCD0`) → bandas verticales más definidas.
- `--zeus-bg-sheen`: veta diagonal de 12%→0% a 24%→6%→0% en tres paradas →
  reflejo direccional más marcado.
- Es la misma variable `--zeus-bg` que ya se re-declaraba pantalla por
  pantalla (`background-image: var(--zeus-bg)`), así que el cambio se
  propaga automáticamente a toda la app sin tocar ningún componente.

### 2.2 Dinamismo CSS sobre avatares reales (sin arte nuevo)
`frontend/src/components/DashboardProfesional.vue` y
`frontend/src/views/kpi/KpiAgentsView.vue` (mismas clases, mismo criterio en
ambos archivos, duplicado deliberadamente porque son dos componentes sin
un ancestro común que las comparta — ver "qué queda pendiente"):

| Agente | Tratamiento | Por qué |
|---|---|---|
| PERSEO | Encuadre inclinado (-5°) + zoom 1.14 + líneas de velocidad (`repeating-linear-gradient` enmascarado con `mask-image`) que se desvanecen desde el borde izquierdo | "Estratega de Crecimiento", más atlético/dinámico — sugiere movimiento sin animación permanente |
| RAFAEL | Marco recto (`border-radius: 10px` en vez del círculo genérico), borde de un solo tono neutro, sin gradiente | "Guardián Fiscal" — actitud ejecutiva/sobria |
| THALOS | Aura fría estática (`box-shadow` en azul índigo, sin animación) | "Defensor Cibernético" — un escudo no parpadea |
| JUSTICIA | Doble exposición: una segunda copia de la misma foto (`<img aria-hidden>`), desplazada 6-7px y difuminada, detrás de la nítida | "Asesora Legal" con foto ya en pose de movimiento — ghost trail sutil |
| AFRODITA | Aura cálida (`--zeus-warning` en baja opacidad, token ya existente, ningún color nuevo) | "RRHH y Logística" — la única sin instrucción explícita del encargo; se decidió con criterio dado que RRHH es la función más "cercana/cálida" del set, reutilizando el único tono cálido ya en el sistema (ámbar) |
| ZEUS CORE | Sin tratamiento nuevo (mantiene su propio diseño ya diferenciado: tarjeta destacada de mayor tamaño, no forma parte del grid) | No estaba en la lista del encargo y ya tiene jerarquía visual propia |

Todos los efectos son transformaciones CSS puras sobre `<img>` reales
(`transform`, `border-radius`, `box-shadow`, `mask-image`) o una segunda
`<img>` con el mismo `src` — ningún asset se sustituyó, ninguna imagen se
generó.

### 2.3 Indicador de estado real (online/idle/offline)
`DashboardProfesional.vue` (función `loadAgentsStatus`, ~línea 1057 tras el
cambio) y `KpiAgentsView.vue` (ya existente, sin tocar su lógica de carga).

- Punto de color superpuesto en la esquina inferior derecha del avatar
  (`.status-dot`), no solo texto: verde=online, ámbar=idle, gris=offline.
- Pulso (`@keyframes status-dot-pulse`) solo cuando `status === 'online'`,
  envuelto en `@media (prefers-reduced-motion: reduce) { animation: none }`
  — mismo patrón ya usado en `.agent-modal-*` y `.btn-interact` en el mismo
  archivo.
- **Antes**: en `DashboardProfesional.vue` el stat "Estado" mostraba
  siempre el texto fijo `t('dashboardPro.agentCard.online')` con clase
  `.status-active`, sin llamar a ningún endpoint — un placeholder
  permanente. Se sustituye por una llamada real a
  `GET /api/v1/agents/status` (mismo endpoint que ya usaban
  `OlymposDashboard.vue` y `KpiAgentsView.vue`), cargada al montar
  (inmediata, sin esperar al primer poll) y refrescada en el ciclo de poll
  existente cada 60s.
- En `KpiAgentsView.vue` el estado real ya se cargaba correctamente antes
  de este cambio (no era un hallazgo) — solo se le añadió el punto visual
  sobre el avatar, que antes no existía (solo había un pill de texto).

### 2.4 Badge BETA
- **No existe ningún campo real** en el backend que marque un agente como
  "beta". Se revisó `AGENT_REGISTRY` en
  `backend/app/api/v1/endpoints/agents.py` (la fuente de metadata real de
  cada agente) y no tiene ningún campo de versión/estabilidad.
- Decisión: se aplica un flag `beta: true` **hardcodeado solo en ZEUS
  CORE**, documentado en comentario en el propio código
  (`DashboardProfesional.vue` y `KpiAgentsView.vue`, junto a la
  declaración de `agentsData`/`agents`). Justificación: es una etiqueta
  puramente informativa de producto (ZEUS CORE es el orquestador, el
  componente más nuevo y menos rodado del núcleo), no una condición de
  negocio ni un dato que deba venir de una fuente de verdad — no aplica
  el mismo umbral de "no simules datos" que a métricas operativas
  (estado, actividad, uptime), que sí siguen siendo 100% reales.
- Si en el futuro el backend expone un campo real de versión/estabilidad
  por agente, este flag debe leerse de ahí en vez de estar hardcodeado —
  se deja anotado en el propio comentario del código.

### 2.5 Grid de 2 columnas
- `DashboardProfesional.vue`: `.agents-grid` pasa de `repeat(3, 1fr)` +
  `repeat(2, 1fr)` filas fijas a `repeat(2, 1fr)` columnas +
  `grid-auto-rows` + `overflow-y: auto` (5 tarjetas sin ZEUS CORE, que
  tiene su propia fila destacada arriba, ya no caben en una rejilla 3×2
  sin overflow). El breakpoint intermedio (769–1024px) que antes colapsaba
  a **1** columna pasa también a 2, por consistencia y porque con solo 5
  tarjetas 1 columna desperdicia el ancho disponible en tablet. Móvil
  (≤768px) ya estaba en 2 columnas antes de este cambio y se mantiene sin
  tocar.
- `KpiAgentsView.vue`: nueva rejilla `.agents-grid` en 2 columnas, con un
  colapso a 1 columna propio en ≤560px (más estrecho que el breakpoint del
  Dashboard) — decisión deliberada: estas tarjetas llevan más densidad de
  datos (pill de estado + 3 filas de métricas con fecha/hora) que las del
  Dashboard (avatar + 2 stats cortos + botón), así que necesitan más ancho
  mínimo antes de colapsar.

## 3. Qué se probó y cómo

Entorno de este worktree, verificado con marcador real (no un checkout
compartido):

- Backend: `uvicorn app.main:app --port 8000` desde
  `C:\Users\Acer\ZEUS-IA\.claude\worktrees\consolidacion-final\backend`
  (sqlite local `backend/zeus.db` de este worktree).
- Frontend: `npx vite --port 5193 --strictPort` desde
  `.../consolidacion-final/frontend`.
- Antes de arrancar se confirmó que el puerto 5173 (el de
  `.claude/launch.json`) ya estaba ocupado por el checkout **compartido**
  `C:\Users\Acer\ZEUS-IA\frontend` (verificado con
  `Get-CimInstance Win32_Process` sobre el PID en escucha) — se usó 5193
  en su lugar precisamente para no verificar sobre el checkout equivocado.
- Se registró un usuario real vía `POST /api/v1/auth/register`
  (`zeus.verificador.consolidacion@example.com`) contra el backend de este
  worktree y se promovió a superusuario directamente en el sqlite de este
  worktree para poder ver el agregado global de `agent_activities` (dato
  real ya sembrado en runs anteriores de este mismo sqlite, no
  fabricado para la ocasión).

Comprobado con Playwright/Browser real:

1. **Datos reales, no placeholders**: en `/dashboard` y `/agents`, nombre,
   rol, estado, `uptime`, `decisiones hoy` y `última actividad` vienen del
   backend (confirmado vía `read_network_requests`: `GET
   /api/v1/agents/status` → 200, contenido con fechas y contadores reales
   distintos por agente).
2. **Cambio de estado real reflejado**: se forzó en el sqlite del
   worktree que todas las `agent_activities` de AFRODITA tuvieran fecha
   `2020-01-01` (`UPDATE agent_activities SET created_at=... WHERE
   agent_name LIKE 'AFRODITA%'`). Se confirmó primero por API
   (`GET /api/v1/agents/status` → `AFRODITA.status = "offline"`) y después
   recargando ambas vistas: el punto de estado de AFRODITA pasó de verde
   ("En línea"/"Online") a gris ("Desconectado"/"Offline") en **ambas**
   pantallas, y `KpiAgentsView.vue` mostró `Uptime: Sin datos` /
   `Última actividad: Sin actividad` — sin tocar ni una línea de código
   entre el antes y el después, solo el dato real cambió.
3. **Capturas antes/después** (descritas, no adjuntas como archivo):
   - `/dashboard` antes del cambio: grid 3×2, sin punto de estado, sin
     badge, avatares circulares idénticos entre sí salvo la foto.
   - `/dashboard` después: grid 2 columnas, ZEUS CORE con badge BETA y
     punto verde pulsante, PERSEO con encuadre inclinado, RAFAEL con
     marco recto (visible claramente en captura: esquinas rectas vs.
     círculo de PERSEO/JUSTICIA), THALOS con halo azul visible, JUSTICIA
     con ghost trail sutil, AFRODITA con halo ámbar y punto gris tras
     forzar el estado offline.
   - `/agents` antes: lista de filas de texto sin avatar.
   - `/agents` después: mismas tarjetas que en Dashboard (avatar + efecto
     + punto de estado + badge + pill + métricas), grid 2 columnas.
4. **Fondo metálico**: confirmado visualmente en `/dashboard`, `/agents`,
   `/insurance` (Seguros, pantalla de referencia) y `/tpv` — bandas
   verticales más marcadas y veta diagonal más visible en las cuatro,
   sin pérdida de contraste de texto (todo el texto sigue en
   `--zeus-text`/`--zeus-text-secondary` sobre tarjetas blancas
   `--zeus-surface`, el fondo de bandas solo se ve en los huecos entre
   tarjetas).
5. **Grid responsive**: el viewport del Browser pane (629px de ancho) cae
   ya por debajo del breakpoint de 768px, así que sirvió como verificación
   del comportamiento "móvil" real: ambas vistas mantienen 2 columnas a
   ese ancho, como estaba decidido. No se pudo emular un ancho aún más
   estrecho (p. ej. 375px) con las herramientas disponibles en esta
   sesión — el colapso a 1 columna de `KpiAgentsView.vue` en ≤560px se
   verificó por inspección de código, no visualmente.
6. **Funcionalidad intacta**: clic en una tarjeta (`JUSTICIA`) abrió el
   mismo `AgentActivityPanel` con pestañas Chat/Actividad/Métricas reales,
   igual que antes del cambio — se cerró con el botón ✕ sin errores.
7. **Consola**: revisada con `read_console_messages` tras cada
   navegación. Los únicos errores presentes son ruido pre-existente del
   propio entorno de verificación: el cliente HMR de Vite intenta conectar
   a `ws://localhost:5173` (puerto hardcodeado en algún sitio del cliente
   de Vite) mientras el servidor real corre en `5193` — Content-Security-
   Policy (definida en `frontend/index.html`, no tocada en esta tarea)
   bloquea esa conexión de HMR. Es un artefacto de haber elegido un puerto
   no estándar para no chocar con el checkout compartido, no una regresión
   de este cambio — no aparece ningún error de Vue, de red 4xx/5xx real
   (fuera de ese ruido) ni de JavaScript en las vistas tocadas.
8. **`prefers-reduced-motion`**: verificado por inspección de código,
   siguiendo exactamente el mismo patrón ya usado en `.agent-modal-*` y
   `.btn-interact` del mismo archivo (`@media (prefers-reduced-motion:
   reduce) { animation: none; display: none; }` sobre `.status-dot.online
   ::after`). No se pudo alternar la preferencia de SO/navegador dentro de
   esta sesión para comprobarlo visualmente en runtime.

## 4. Qué NO se pudo verificar

- Viewport móvil real por debajo de 768px con las herramientas de este
  entorno (el Browser pane no permite fijar un ancho de viewport
  arbitrario) — se verificó únicamente el comportamiento a 629px de ancho
  y por inspección de código para anchos menores.
- Alternar `prefers-reduced-motion` en runtime (verificado solo por
  inspección de código, siguiendo el patrón ya validado en el resto del
  archivo).
- No se probó en un navegador distinto a Chromium (el que usa el Browser
  pane).
- El modo 2D "agentes paseando" de `OlymposDashboard.vue` no se tocó ni se
  verificó a fondo porque es código muerto (`firstPersonMode` nunca es
  `false`) — se documenta como hallazgo, no como parte de esta tarea.

## 5. Qué queda pendiente / hallazgos nuevos

- **Hallazgo, fuera de alcance de esta tarea**: `KpiPageShell.vue`
  (`frontend/src/components/kpi/KpiPageShell.vue`, usado por
  `KpiAgentsView.vue` y el resto de vistas `Kpi*View`) tiene un bug de
  layout **pre-existente**, no introducido por este cambio: cuando el
  contenido de la página excede la altura del viewport, el fondo de
  bandas metálicas deja de cubrir el resto del scroll y se ve el fondo
  oscuro global de `body` (`frontend/src/style.css`, regla
  `@media (prefers-color-scheme: dark) { body { background-color:
  var(--color-bg) } }` con `--color-bg: #1a1a1a`) en su lugar. Se
  reprodujo en `/agents` tras el rediseño (al tener más contenido por
  tarjeta que la lista original, se hace más visible), pero la causa raíz
  está en `#app` (`frontend/src/style.css:87-95`, `flex:1` dentro de un
  `body` en `display:flex; flex-direction:column`) y no en
  `KpiAgentsView.vue` ni en `KpiPageShell.vue` en sí — se confirmó que
  `/dashboard` y `/tpv` (que no usan `KpiPageShell`, tienen su propio
  contenedor con scroll interno) no lo sufren. No se corrigió en esta
  tarea porque es un componente compartido por todas las páginas
  `Kpi*View` y el encargo pedía cambios acotados a las tarjetas de
  agente — se recomienda una tarea aparte.
- **Código muerto detectado**: el modo 2D de `OlymposDashboard.vue`
  (`agents-panel`, `.agent-card` con hologramas, "agentes paseando") no es
  alcanzable (`firstPersonMode` fijo a `true`). No se tocó porque no forma
  parte de las tarjetas realmente visibles, pero es candidato a limpieza
  o a reactivación intencional en una tarea futura.
- **Duplicación deliberada**: los estilos y helpers de efecto por agente
  (`agentAvatarFx`, `.avatar-fx-*`, `.status-dot`, `.beta-badge`) están
  duplicados entre `DashboardProfesional.vue` y `KpiAgentsView.vue` en vez
  de extraídos a un componente compartido (`AgentAvatar.vue` ya existe en
  el repo pero no se usa en ningún sitio — se comprobó con `grep` antes de
  tocar nada). No se refactorizó a un componente común en esta tarea para
  no mezclar un refactor no pedido con el fix visual — es un candidato
  razonable para una tarea de consolidación futura si se quiere evitar
  que los dos archivos diverjan.

No me declaro cerrado — pendiente de verificación independiente por
`revisor-frontend`.
