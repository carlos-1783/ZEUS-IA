<template>
  <KpiPageShell
    title="Automatizaciones"
    :subtitle="`Activas: ${total}`"
    :loading="loading"
    :error="error"
  >
    <ul v-if="automations.length" class="kpi-list">
      <li v-for="a in automations" :key="a.id || a.name" class="kpi-list-item">
        <strong>{{ a.name }}</strong>
        <span class="pill" :class="a.status">{{ a.status }}</span>
        <span class="last">{{ a.last_run ? formatDate(a.last_run) : 'Sin ejecución' }}</span>
      </li>
    </ul>
    <p v-else class="empty">No hay automatizaciones registradas.</p>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const automations = ref([])
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
    const data = await api.get('/api/v1/analytics/automations')
    automations.value = data.automations || []
    total.value = data.total ?? automations.value.length
  } catch (e) {
    error.value = e?.message || 'Error cargando automatizaciones'
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
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  font-size: 13px;
}

.pill.active {
  color: #10b981;
  font-weight: 600;
  font-size: 12px;
}

.last {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  text-align: right;
}

.empty {
  color: rgba(255, 255, 255, 0.5);
}

@media (max-width: 768px) {
  .kpi-list-item {
    grid-template-columns: 1fr;
  }
}
</style>
