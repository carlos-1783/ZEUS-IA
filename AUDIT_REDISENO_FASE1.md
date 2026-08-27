# AUDIT_REDISENO_FASE1.md

**Rama**: `feature/rediseno-frontend-fase1` (desde `main`)
**Fecha**: 2026-08-15/16
**Objetivo**: Fase 1 del rediseño visual — estilo claro/futurista tipo Stripe/Linear/Vercel
en vez del panel oscuro anterior, para transmitir confianza a un público de aseguradoras.
Alcance: Dashboard principal, `/agents`, modal animado de interacción con agentes,
y el workspace compartido de los 6 agentes (con RAFAEL y PERSEO como ejemplos
representativos).

Sin cambios de lógica de negocio ni llamadas nuevas al backend — es una capa
visual sobre datos y funcionalidad que ya eran reales.

---

## 1. Sistema de diseño — guía para fases futuras

### 1.1 Color

La paleta se ancló al color de marca **real**, confirmado visitando la landing
de producción (`zeus-ia-production-16d8.up.railway.app`) con el navegador antes
de diseñar nada — no es un azul/violeta inventado:

| Token | Valor | Uso |
|---|---|---|
| `--zeus-accent` | `#4f46e5` | Botón primario, acento — es el mismo `#4f46e5` del botón "Comenzar ahora" en la landing pública |
| `--zeus-accent-hover` | `#4338ca` | Hover del acento |
| `--zeus-accent-soft` / `--zeus-accent-2-soft` | `#eef1ff` / `#eef2ff` | Fondos suaves para chips/estados activos |
| `--zeus-accent-2` | `#6366f1` | Variación de acento (mismo tono que los chips de icono de la landing) |
| `--zeus-bg` | `linear-gradient(180deg, #fbfbfd 0%, #eef0f3 55%, #e3e6eb 100%)` | Fondo general de página — degradado "platino" sutil, no plano |
| `--zeus-surface` | `#ffffff` | Tarjetas y paneles, planos, flotando sobre el fondo platino |
| `--zeus-text` / `--zeus-text-secondary` / `--zeus-text-muted` | `#0f172a` / `#52607a` / `#8792a6` | Jerarquía de texto |
| `--zeus-success` / `--zeus-warning` / `--zeus-danger` / `--zeus-info` | `#10b981` / `#f59e0b` / `#ef4444` / `#3b82f6` | Estado, ya usados en el resto de la app |

Definidos en `frontend/src/assets/styles/zeus-light-system.css`, importado
globalmente desde `main.scss`. Los colores de identidad por agente (ámbar para
RAFAEL/fiscal, por ejemplo) se mantienen como acento local de cada workspace,
no como parte del sistema base — mismo patrón que ya usaban los badges de
THALOS/AFRODITA.

### 1.2 Tipografía

**Hallazgo real, no cosmético**: Inter estaba referenciada en el CSS de toda
la app (`font-family: 'Inter', ...`) pero **nunca se cargaba de verdad** — no
había ningún `<link>` de Google Fonts ni `@font-face`, solo el `preconnect`.
Todo este tiempo se veía la fuente por defecto del sistema operativo, no
Inter. Se corrige en `frontend/index.html` con un `<link>` real a Google
Fonts (pesos 400/500/600/700).

### 1.3 Espaciado, radio, sombra

Escala de 4px (`--zeus-space-1` a `--zeus-space-8`), radios (`--zeus-radius-sm`
8px / `--zeus-radius` 12px / `--zeus-radius-lg` 16px / `--zeus-radius-full`
píldora), y dos familias de sombra:
- `--zeus-shadow-*`: sutil, para tarjetas/superficies (el contraste lo da
  sobre todo el borde).
- `--zeus-shadow-btn-*`: con más presencia y un tinte del color de acento
  (no gris plano) — para que los botones tengan profundidad real y no se
  fundan con el fondo platino.

### 1.4 Botones reutilizables

Clases globales en `zeus-light-system.css` (`.zeus-btn`, `.zeus-btn-primary`,
`.zeus-btn-ghost`) pensadas para añadirse junto a las clases propias de cada
componente en fases futuras, en vez de reinventar el botón en cada sitio.

### 1.5 Patrón de modal animado

`DashboardProfesional.vue` envuelve el overlay de "Interactuar" en
`<Transition name="agent-modal">`:
- Entrada/salida ~220-240ms, `cubic-bezier(0.4, 0, 0.2, 1)`.
- Solo anima `opacity` y `transform` (backdrop en fade, panel con
  fade + escala 0.98→1 + desplazamiento sutil) — nunca `width`/`height`/
  `top`/`left`.
- Cierra con click fuera (`@click.self`, ya existía), botón ✕ (ya existía) y
  **tecla Esc** (nuevo — listener en `window`, limpiado en `onUnmounted`).
- `@media (prefers-reduced-motion: reduce)`: duración recortada a 1ms y sin
  `transform`, nunca fuerza movimiento a quien lo tiene desactivado en el
  sistema.

---

## 2. Pantallas — antes / después

### 2.1 Dashboard principal (`DashboardProfesional.vue` + `KPIBar.vue`)
**Antes**: panel oscuro (`#0a0e1a`/`#0f1419`/`#1a1f2e`), texto blanco,
tarjetas con gradiente oscuro y borde `rgba(255,255,255,0.1)`.
**Después**: fondo platino, sidebar y tarjetas blancas con borde sutil y
sombra suave, texto oscuro sobre claro preservando la misma jerarquía de
opacidad que tenía el tema oscuro (mapeo directo de blanco-sobre-negro a
tinta-oscura-sobre-blanco). Acentos de color (azul, violeta, esmeralda,
ámbar) intactos — ya funcionaban bien y son los "toques de color puntuales"
pedidos. Verificado con Playwright real (`test.gestoria@example.com`): datos
reales de KPIs, actividades de agentes y el overlay de interacción, todo
funcionando igual que antes del cambio visual.

### 2.2 Vista de Agentes activos (`/agents`, `KpiAgentsView.vue` + `KpiPageShell.vue`)
**Antes**: fondo oscuro, lista con overlay translúcido sobre negro.
**Después**: fondo claro, tarjetas blancas con sombra, badge "Online" como
chip verde suave. Mismos 6 agentes, mismos datos reales del Bloque 3 (sin
tocar el array de agentes ni su origen).

### 2.3 Modal animado de interacción (`DashboardProfesional.vue`)
Sustituye el `v-if` seco anterior (aparecía/desaparecía de golpe) por el
patrón de motion descrito en 1.5. Verificado en vivo con Playwright:
- Computado real de la transición: `opacity 0.24s cubic-bezier(0.22, 1,
  0.36, 1) / cubic-bezier(0.4, 0, 1, 1)` (entrada/salida) — dentro del rango
  200-300ms pedido en iteraciones posteriores del diseño.
- Los 3 mecanismos de cierre probados por separado y confirmados por estado
  computado, no solo visualmente: botón ✕, tecla Esc, click fuera del panel.

### 2.4 Workspace compartido de los 6 agentes (`AgentActivityPanel.vue`)
**Antes**: header, toggle Texto/Voz, tabs (Workspace/Chat/Actividad/
Métricas), timeline de actividad y tarjetas de métricas, todo en tema oscuro.
**Después**: fondo platino (el mismo contenedor que usan los 6 agentes),
toggle y tabs como controles segmentados blancos con sombra, estado activo
en índigo sólido con sombra propia (no un tinte plano) — el acento destaca
con claridad sobre el gris del fondo, como se pidió explícitamente en una
iteración posterior del diseño.

### 2.5 RAFAEL — workspace (`RafaelWorkspace.vue`)
Este componente **ya era mayormente claro** antes de esta fase (se construyó
aparte, con identidad ámbar/dorada para lo fiscal) — no tenía el problema de
"panel oscuro". Se alinearon sus grises neutros (texto, bordes, sombras,
radios) a los tokens `--zeus-*` para consistencia con el resto del sistema,
y se le dio profundidad real a sus botones (sombra con tinte ámbar, estados
hover/press) sin tocar el acento ámbar que le da identidad propia.

**Hallazgo real durante la verificación en navegador**: el botón "Actualizar"
salía sólido negro pese a que tanto este componente como `TeamFlowPanel.vue`
lo definen con estilos claros. Causa: `css_system_enforcer_v1.css` (un parche
global preexistente para AFRODITA/THALOS) tiene una regla
`[class$='-workspace'] button { background:#111827 !important; color:#fff
!important }` con selector comodín sin scope de componente, que también
pillaba a `.rafael-workspace` y `.perseo-workspace`. Se excluyeron ambas
clases de esas reglas (`:not()`), documentado con comentario en el propio
archivo — el resto de workspaces (afrodita/justicia/thalos/zeus) no se
tocan en esta fase.

### 2.6 PERSEO — workspace (`PerseoWorkspace.vue`)
Igual que RAFAEL, ya era mayormente claro (identidad azul/índigo). Se aplicó
una primera pasada de alineación a los tokens `--zeus-*` (fondo, texto,
tarjeta de entregables, tipografía) — **parcial**: quedan valores hex sueltos
sin convertir en el resto del archivo (colores de estado, tags, tabla de
datos) que no bloquean nada visualmente pero no siguen aún la convención de
tokens. Pendiente de terminar en una fase posterior.

---

## 3. Exploración de dirección visual para RAFAEL — pendiente de aprobación final

Durante esta fase se iteró varias veces sobre una dirección visual específica
para el modal de RAFAEL (fondo de "metal cepillado" con capas de gradiente +
grano SVG, acento vibrante teal→morado→rosa, avatar real con anillo de
acento, motion con timing exacto) **completamente fuera del repositorio**,
en un archivo HTML estático aislado (`preview-rafael.html`, servido desde el
directorio de scratchpad de la sesión, nunca importado por la app) — tal
como se pidió explícitamente ("no toques el componente real hasta que
apruebe").

**Esa dirección NO está aplicada a `AgentActivityPanel.vue` ni a ningún
componente real.** Una versión anterior (nombre en serif "Fraunces" + anillo
de sello ámbar, sin el fondo metálico ni el acento vibrante) sí se llegó a
escribir directamente en `AgentActivityPanel.vue` en un punto intermedio,
pero quedó **revertida** antes de este commit al quedar superada por las
siguientes iteraciones — no se incluye en esta rama. Si se decide seguir con
la dirección de metal + acento vibrante, el siguiente paso es aplicarla
desde el preview aislado a `AgentActivityPanel.vue` (o a una variante scoped
por agente, como se hizo con el intento de serif) en un commit propio.

---

## 4. Verificación

Todo lo comprometido en esta rama se verificó con Playwright real, con
`test.gestoria@example.com`, tras cada cambio — no solo revisando el código:
- Dashboard, `/agents` y el modal de interacción: capturas y lectura de
  consola/red en el navegador, sin errores nuevos.
- Datos reales confirmados en cada pantalla (KPIs, actividades por agente,
  documentos y TeamFlow de RAFAEL) — nada de esto se tocó, solo la capa
  visual.
- El único error de consola presente (`ReferenceError: shouldShowTPV is not
  defined` en `DashboardProfesional.vue`) es un bug preexistente de `main`,
  ya diagnosticado y arreglado en otra rama (`feature/hallazgos-visuales`,
  aún sin fusionar) — no relacionado con este rediseño, no introducido aquí.

No se ha tocado nada en `backend/` en esta rama — es un cambio puramente de
frontend (Vue/CSS/HTML), por lo que no se ha vuelto a correr la suite de
tests de Python (sin cambios que pudieran afectarla).

---

## 5. Pendiente

1. Decisión sobre la dirección "metal cepillado + acento vibrante" para
   RAFAEL (§3) — aprobar o descartar antes de aplicarla al componente real.
2. Terminar la alineación de tokens en `PerseoWorkspace.vue` (§2.6).
3. Extender el sistema de diseño al resto de agentes (AFRODITA, THALOS,
   JUSTICIA, ZEUS CORE) y al resto de la app (CRM, TPV, Control Horario,
   Nóminas, Onboarding, Admin Panel) — explícitamente fuera de alcance en
   esta fase.
4. Aplicar la misma base a Seguros cuando se construya esa vertical.
