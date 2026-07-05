<template>
  <KpiPageShell
    title="Tareas últimas 24h"
    :subtitle="`Total: ${total}`"
    :loading="loading"
    :error="error"
  >
    <ul v-if="events.length" class="kpi-list">
      <li v-for="ev in events" :key="ev.id" class="kpi-list-item">
        <code>{{ ev.type }}</code>
        <span>{{ ev.agent }}</span>
        <span class="pill" :class="ev.status">{{ ev.status }}</span>
        <time>{{ formatDate(ev.created_at) }}</time>
      </li>
    </ul>
    <p v-else class="empty">Sin eventos en las últimas 24 horas.</p>
  </KpiPageShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const events = ref([])
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
    const data = await api.get('/api/v1/analytics/events?hours=24')
    events.value = data.events || []
    total.value = data.total ?? events.value.length
  } catch (e) {
    error.value = e?.message || 'Error cargando tareas'
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
  grid-template-columns: 1.2fr 0.8fr auto 1fr;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  font-size: 13px;
}

.pill.success {
  color: #10b981;
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
