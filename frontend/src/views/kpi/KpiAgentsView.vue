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
        <span class="pill" :class="agent.status">{{ agent.status === 'online' ? 'Online' : 'Idle' }}</span>
        <span class="metric">{{ agent.uptime || 'Sin datos' }}</span>
        <span class="metric">{{ agent.decisionsToday }} hoy</span>
        <span class="last-activity">{{ formatDate(agent.lastActivity) }}</span>
      </li>
      <li v-if="!agents.length" class="empty">Sin agentes registrados.</li>
    </ul>
  </KpiPageShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const agents = ref([])

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
    agents.value = Object.entries(data?.agents || {}).map(([name, info]) => ({
      name,
      role: info.role,
      status: info.status,
      uptime: info.uptime,
      decisionsToday: info.decisions_today ?? 0,
      lastActivity: info.last_activity,
    }))
  } catch (e) {
    error.value = e?.message || 'Error cargando estado de agentes'
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
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  font-size: 14px;
}

.pill {
  font-size: 12px;
  font-weight: 600;
}

.pill.online {
  color: #10b981;
}

.pill.idle {
  color: rgba(255, 255, 255, 0.4);
}

.metric {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  white-space: nowrap;
}

.last-activity {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
  text-align: right;
}

.empty {
  color: rgba(255, 255, 255, 0.5);
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
