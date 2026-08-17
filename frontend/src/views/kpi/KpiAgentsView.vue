<template>
  <KpiPageShell
    title="Agentes activos"
    subtitle="Olimpo ZEUS — 6 agentes operativos"
    :loading="loading"
    :error="error"
  >
    <ul class="kpi-list">
      <li v-for="agent in agents" :key="agent.name" class="kpi-list-item">
        <strong>{{ agent.name }}</strong>
        <span>{{ agent.role }}</span>
        <span class="pill" :class="agent.status">{{ statusLabel(agent.status) }}</span>
      </li>
    </ul>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')

// Metadata local solo para el nombre/rol mostrado mientras carga; el
// estado real (status) llega siempre del backend, nunca queda fijo.
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

onMounted(async () => {
  try {
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/agents/status')
    const backendAgents = data?.agents || {}

    agents.value = agents.value.map((agent) => {
      const info = backendAgents[agent.name]
      if (!info) return agent
      return {
        ...agent,
        role: info.role || agent.role,
        status: info.status || 'offline',
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
  grid-template-columns: 1fr 1fr auto;
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
  color: #f59e0b;
}

.pill.offline {
  color: #ef4444;
}

.pill.loading {
  color: rgba(255, 255, 255, 0.5);
}

@media (max-width: 768px) {
  .kpi-list-item {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
