<template>
  <KpiPageShell
    title="Agentes activos"
    subtitle="Olimpo ZEUS — estado real, calculado desde agent_activities"
    :loading="loading"
    :error="error"
  >
    <section class="agents-grid">
      <article
        v-for="agent in agents"
        :key="agent.name"
        class="agent-card"
      >
        <div class="avatar-container" :class="agentAvatarFx(agent.name)">
          <img
            v-if="agent.name === 'JUSTICIA'"
            :src="agentImage(agent.name)"
            alt=""
            aria-hidden="true"
            class="avatar-ghost"
          />
          <img
            :src="agentImage(agent.name)"
            :alt="agent.name"
            class="avatar-image"
          />
          <span
            class="status-dot"
            :class="agent.status"
            :title="statusLabel(agent.status)"
            aria-hidden="true"
          ></span>
        </div>

        <div class="agent-card-body">
          <h3 class="agent-name">
            {{ agent.name }}
            <span v-if="agent.beta" class="beta-badge">BETA</span>
          </h3>
          <p class="agent-role">{{ agent.role }}</p>

          <span class="pill" :class="agent.status">{{ statusLabel(agent.status) }}</span>

          <dl class="agent-metrics">
            <div class="metric-row">
              <dt>Uptime (30d)</dt>
              <dd>{{ agent.uptime || 'Sin datos' }}</dd>
            </div>
            <div class="metric-row">
              <dt>Decisiones hoy</dt>
              <dd>{{ agent.decisionsToday }}</dd>
            </div>
            <div class="metric-row">
              <dt>Última actividad</dt>
              <dd>{{ formatDate(agent.lastActivity) }}</dd>
            </div>
          </dl>
        </div>
      </article>

      <p v-if="!agents.length" class="empty">Sin agentes registrados.</p>
    </section>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')

// Metadata local solo para el nombre/rol mostrado mientras carga; el
// estado real (status, uptime, decisiones, última actividad) llega siempre
// del backend (GET /api/v1/agents/status), nunca queda fijo.
// `beta`: no existe ningún campo real de "versión/estabilidad" en el
// backend para agentes (ver AGENT_REGISTRY en
// backend/app/api/v1/endpoints/agents.py) — se marca a mano solo en
// ZEUS CORE por ser puramente informativo de producto, igual que en
// DashboardProfesional.vue (mismo criterio documentado en
// AUDIT_REDISENO_TARJETAS_AGENTE.md).
const agents = ref([
  { name: 'ZEUS CORE', role: 'Supreme Orchestrator', status: 'loading', beta: true },
  { name: 'PERSEO', role: 'Growth Strategist', status: 'loading' },
  { name: 'RAFAEL', role: 'Fiscal Guardian', status: 'loading' },
  { name: 'THALOS', role: 'Cybersecurity Defender', status: 'loading' },
  { name: 'JUSTICIA', role: 'Legal & GDPR Advisor', status: 'loading' },
  { name: 'AFRODITA', role: 'HR & Logistics Manager', status: 'loading' },
])

const AGENT_IMAGES = {
  'ZEUS CORE': '/images/avatars/Zeus-avatar.jpg',
  PERSEO: '/images/avatars/Perseo-avatar.jpg',
  RAFAEL: '/images/avatars/Rafael-avatar.jpg',
  THALOS: '/images/avatars/Thalos-avatar.jpg',
  JUSTICIA: '/images/avatars/Justicia-avatar.jpg',
  AFRODITA: '/images/avatars/Afrodita-avatar.jpg',
}

const agentImage = (name) => AGENT_IMAGES[name] || '/images/avatars/Zeus-avatar.jpg'

// Mismo tratamiento visual por agente que en DashboardProfesional.vue
// (sin arte nuevo, transformaciones CSS sobre la misma foto real).
const AGENT_AVATAR_FX = {
  PERSEO: 'avatar-fx-perseo',
  RAFAEL: 'avatar-fx-rafael',
  THALOS: 'avatar-fx-thalos',
  JUSTICIA: 'avatar-fx-justicia',
  AFRODITA: 'avatar-fx-afrodita',
}

const agentAvatarFx = (name) => AGENT_AVATAR_FX[name] || ''

const statusLabel = (status) => {
  switch (status) {
    case 'online':
      return 'Online'
    case 'idle':
      return 'Inactivo'
    case 'offline':
      return 'Offline'
    default:
      return 'Cargando…'
  }
}

const formatDate = (iso) => {
  if (!iso) return 'Sin actividad'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(async () => {
  try {
    const api = (await import('@/services/api')).default
    // Mismo endpoint que consume OlymposDashboard.vue y DashboardProfesional.vue
    // — GET /api/v1/agents/status calcula status/uptime/last_activity/
    // decisions_today desde agent_activities en vez de devolver valores fijos.
    const data = await api.get('/api/v1/agents/status')
    const backendAgents = data?.agents || {}

    agents.value = agents.value.map((agent) => {
      const info = backendAgents[agent.name]
      if (!info) return { ...agent, status: 'offline' }
      return {
        ...agent,
        role: info.role || agent.role,
        status: info.status || 'offline',
        uptime: info.uptime,
        decisionsToday: info.decisions_today ?? 0,
        lastActivity: info.last_activity,
      }
    })
  } catch (e) {
    error.value = e?.message || 'Error cargando el estado de los agentes'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* Rejilla de tarjetas de agente — 2 columnas en todos los tamaños
   (igual criterio que executive-agents-grid en DashboardProfesional.vue):
   con 6 agentes, 1 columna en móvil desperdicia ancho y 3+ columnas en
   desktop deja las tarjetas demasiado estrechas para avatar + métricas. */
.agents-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.agent-card {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 20px;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  /* Lámina metálica (platino / grafito según tema), igual que el panel */
  background: var(--metal-face, var(--zeus-surface, #fff));
  border: 1px solid var(--metal-edge, var(--zeus-border, #e5e9f0));
  border-bottom-color: var(--metal-edge-bottom, var(--zeus-border, #e5e9f0));
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--metal-shadow, var(--zeus-shadow-sm));
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.agent-card::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background: var(--metal-sheen, none);
  opacity: var(--metal-sheen-opacity, 0);
  mix-blend-mode: screen;
  pointer-events: none;
}

.agent-card:hover {
  box-shadow: var(--metal-shadow-hover, var(--zeus-shadow));
}

.agent-card-body {
  min-width: 0;
  flex: 1;
}

/* ---- Avatar con tratamiento de dinamismo por agente (mismo asset real,
   sin arte nuevo — ver AUDIT_REDISENO_TARJETAS_AGENTE.md) ---- */
.avatar-container {
  position: relative;
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid rgba(59, 130, 246, 0.18);
  background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, transparent 70%);
}

.avatar-image {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* PERSEO — atlético: encuadre inclinado + líneas de velocidad que se
   desvanecen desde el borde izquierdo. */
.avatar-container.avatar-fx-perseo .avatar-image {
  transform: rotate(-5deg) scale(1.14);
  object-position: 55% 30%;
}

.avatar-container.avatar-fx-perseo::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: repeating-linear-gradient(
    100deg,
    transparent 0px, transparent 6px,
    rgba(255, 255, 255, 0.5) 6px, rgba(255, 255, 255, 0.5) 8px,
    transparent 8px, transparent 20px
  );
  -webkit-mask-image: linear-gradient(90deg, black 0%, transparent 40%);
  mask-image: linear-gradient(90deg, black 0%, transparent 40%);
}

/* RAFAEL — ejecutivo/sobrio: marco recto, sin gradiente. */
.avatar-container.avatar-fx-rafael {
  border-radius: 10px;
  border-color: rgba(82, 96, 122, 0.45);
}

.avatar-container.avatar-fx-rafael .avatar-image {
  border-radius: 7px;
}

/* THALOS — defensivo: aura fría estática. */
.avatar-container.avatar-fx-thalos {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 5px rgba(59, 130, 246, 0.14), 0 0 18px rgba(59, 130, 246, 0.28);
}

/* JUSTICIA — doble exposición / ghost trail. */
.avatar-ghost {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.4;
  filter: blur(2px) grayscale(0.15);
  transform: translateX(-6px) scale(1.06);
}

/* AFRODITA — cálida: aura ámbar suave (token ya existente
   --zeus-warning, sin introducir un color nuevo). */
.avatar-container.avatar-fx-afrodita {
  border-color: rgba(245, 158, 11, 0.35);
  box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.1);
}

/* ---- Indicador de estado real (online/idle/offline), con pulso sutil
   solo cuando está realmente online — respeta prefers-reduced-motion. ---- */
.status-dot {
  position: absolute;
  bottom: 1px;
  right: 1px;
  z-index: 3;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid var(--sheet, var(--zeus-surface, #fff));
  background: var(--off, #cbd5e1);
}

.status-dot.online {
  background: var(--ok, #10b981);
}

.status-dot.idle {
  background: var(--warn, #f59e0b);
}

.status-dot.offline {
  background: var(--off, #94a3b8);
}

.status-dot.online::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid #10b981;
  opacity: 0.55;
  animation: status-dot-pulse 1.8s ease-out infinite;
}

@keyframes status-dot-pulse {
  0% { transform: scale(0.55); opacity: 0.55; }
  100% { transform: scale(1.7); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot.online::after {
    animation: none;
    display: none;
  }
}

.agent-name {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 2px;
  font-size: 16px;
  font-weight: 700;
  color: var(--zeus-text, #0f172a);
}

.beta-badge {
  display: inline-block;
  padding: 2px 7px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--volt-ink, var(--zeus-accent, #4f46e5));
  background: var(--volt-soft, var(--zeus-accent-soft, #eef1ff));
  border-radius: var(--zeus-radius-full, 999px);
  line-height: 1.4;
}

.agent-role {
  margin: 0 0 10px;
  color: var(--ink-2, var(--zeus-text-secondary, #52607a));
  font-size: 13px;
}

.pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: var(--zeus-radius-full, 999px);
  margin-bottom: 12px;
}

/* Plano, no gradiente: hay 6 tarjetas de agente en esta vista y el
   acento vibrante debe aparecer como mucho una vez por vista, no
   repetido en cada tarjeta. */
.pill.online {
  color: var(--zeus-success-text);
  background: var(--zeus-success-soft, #e9faf3);
}

.pill.idle {
  color: var(--zeus-warning-text);
  background: var(--zeus-warning-soft, #fef3e2);
}

/* Desconectado / cargando: grabado neutro en la chapa (mismo criterio que
   el panel: el estado apagado no es un error). */
.pill.offline,
.pill.loading {
  color: var(--ink-2, var(--zeus-text-secondary, #52607a));
  background: var(--metal-well, var(--zeus-surface-muted, #f1f4f8));
  box-shadow: var(--metal-well-shadow, none);
}

.agent-metrics {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.metric-row dt {
  color: var(--ink-3, var(--zeus-text-muted, #8a93a6));
}

.metric-row dd {
  margin: 0;
  color: var(--ink, var(--zeus-text-secondary, #52607a));
  font-weight: 600;
  text-align: right;
}

.empty {
  grid-column: 1 / -1;
  color: var(--zeus-text-secondary, #52607a);
  padding: 14px 16px;
}

@media (max-width: 560px) {
  .agents-grid {
    grid-template-columns: 1fr;
  }
}
</style>
