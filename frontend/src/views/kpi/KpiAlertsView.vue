<template>
  <KpiPageShell
    title="Alertas activas"
    :subtitle="`Total: ${total}`"
    :loading="loading"
    :error="error"
  >
    <ul v-if="alerts.length" class="kpi-list">
      <li v-for="a in alerts" :key="a.id" class="kpi-list-item" :class="a.level">
        <span class="level">{{ a.level }}</span>
        <span class="msg">{{ a.message }}</span>
        <time>{{ formatDate(a.created_at) }}</time>
      </li>
    </ul>
    <p v-else class="empty">No hay alertas activas.</p>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const alerts = ref([])
const total = ref(0)

const formatDate = (iso) => {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(async () => {
  try {
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/analytics/alerts')
    alerts.value = data.alerts || []
    total.value = data.total ?? alerts.value.length
  } catch (e) {
    error.value = e?.message || 'Error cargando alertas'
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
  gap: 8px;
}

.kpi-list-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border-left: 3px solid rgba(245, 158, 11, 0.6);
}

.kpi-list-item.high {
  border-left-color: #ef4444;
}

.level {
  font-size: 11px;
  text-transform: uppercase;
  font-weight: 700;
  color: #f59e0b;
}

.empty {
  color: rgba(255, 255, 255, 0.5);
}
</style>
