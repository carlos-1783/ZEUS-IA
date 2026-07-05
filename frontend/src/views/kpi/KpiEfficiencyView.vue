<template>
  <KpiPageShell title="Eficiencia operativa" :loading="loading" :error="error">
    <div v-if="metrics" class="efficiency-grid">
      <div class="metric-card">
        <span class="label">Eficiencia</span>
        <span class="value">{{ metrics.efficiency }}%</span>
      </div>
      <div class="metric-card">
        <span class="label">Eventos 24h</span>
        <span class="value">{{ metrics.tasks24h }}</span>
      </div>
      <div class="metric-card">
        <span class="label">Éxitos 24h</span>
        <span class="value">{{ metrics.success_events_24h }}</span>
      </div>
      <div class="metric-card">
        <span class="label">Fuente</span>
        <span class="value small">{{ metrics.real_data ? 'BD real' : 'fallback' }}</span>
      </div>
    </div>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const metrics = ref(null)

onMounted(async () => {
  try {
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/analytics/executive')
    metrics.value = data
  } catch (e) {
    error.value = e?.message || 'Error cargando eficiencia'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.efficiency-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 20px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  text-transform: uppercase;
}

.value {
  font-size: 28px;
  font-weight: 700;
}

.value.small {
  font-size: 16px;
}
</style>
