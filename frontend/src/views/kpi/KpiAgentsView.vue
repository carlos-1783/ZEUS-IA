<template>
  <KpiPageShell
    title="Agentes activos"
    subtitle="Olimpo ZEUS — estado real, calculado desde agent_activities"
    :loading="loading"
    :error="error"
  >
    <ul class="kpi-list">
      <li v-for="agent in agents" :key="agent.name" class="kpi-list-item">
        <strong>{{ agent.name }}</strong>
        <span>{{ agent.role }}</span>
        <span class="pill" :class="agent.status">{{ statusLabel(agent.status) }}</span>
        <span class="metric">{{ agent.uptime || 'Sin datos' }}</span>
        <span class="metric">{{ agent.decisionsToday }} hoy</span>
        <span class="last-activity">{{ formatDate(agent.lastActivity) }}</span>
      </li>
      <li v-if="!agents.length" class="empty">Sin agentes registrados.</li>
    </ul>
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
const agents = ref([
  { name: 'ZEUS CORE', role: 'Supreme Orchestrator', status: 'loading' },
  { name: 'PERSEO', role: 'Growth Strategist', status: 'loading' },
  { name: 'RAFAEL', role: 'Fiscal Guardian', status: 'loading' },
  { name: 'THALOS', role: 'Cybersecurity Defender', status: 'loading' },
  { name: 'JUSTICIA', role: 'Legal & GDPR Advisor', status: 'loading' },
  { name: 'AFRODITA', role: 'HR & Logistics Manager', status: 'loading' },
])

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
    // Mismo endpoint que consume OlymposDashboard.vue — GET /api/v1/agents/status
    // ahora calcula status/uptime/last_activity/decisions_today desde
    // agent_activities en vez de devolver valores fijos (Bloque 3, tarea 2).
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
.kpi-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.kpi-list-item {
  display: grid;
  grid-template-columns: 1fr 1fr auto auto auto 1fr;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e5e9f0);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow-sm);
  font-size: 14px;
  color: var(--zeus-text-secondary, #52607a);
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.kpi-list-item:hover {
  box-shadow: var(--zeus-shadow);
  border-color: var(--zeus-border-strong, #d7dce5);
}

.kpi-list-item strong {
  color: var(--zeus-text, #0f172a);
}

.pill {
  font-size: 12px;
  font-weight: 600;
  justify-self: end;
  padding: 4px 10px;
  border-radius: var(--zeus-radius-full, 999px);
}

/* Plano, no gradiente: hay 6 filas de agentes en esta vista y el
   acento vibrante debe aparecer como mucho una vez por vista, no
   repetido en cada fila. */
.pill.online {
  color: #0d9668;
  background: var(--zeus-success-soft, #e9faf3);
}

.pill.idle {
  color: #b45309;
  background: var(--zeus-warning-soft, #fef3e2);
}

.pill.offline {
  color: #b91c1c;
  background: var(--zeus-danger-soft, #fde8e8);
}

.pill.loading {
  color: var(--zeus-text-secondary, #52607a);
  background: var(--zeus-surface-muted, #f1f4f8);
}

.metric {
  color: var(--zeus-text-secondary, #52607a);
  font-size: 13px;
  white-space: nowrap;
}

.last-activity {
  color: var(--zeus-text-tertiary, #8a93a6);
  font-size: 12px;
  text-align: right;
}

.empty {
  color: var(--zeus-text-secondary, #52607a);
  padding: 14px 16px;
}

@media (max-width: 768px) {
  .kpi-list-item {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .last-activity {
    text-align: left;
  }
}
</style>
