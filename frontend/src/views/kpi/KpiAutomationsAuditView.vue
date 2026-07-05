<template>
  <KpiPageShell
    title="Auditoría de automatizaciones"
    subtitle="Modo observabilidad — solo lectura"
    :loading="loading"
    :error="error"
  >
    <p v-if="data?.read_only" class="audit-badge">🔒 Read-only audit mode</p>

    <div class="phase-b-actions">
      <button
        type="button"
        class="phase-b-btn"
        :disabled="phaseBRunning"
        @click="runPhaseBTest"
      >
        {{ phaseBRunning ? 'Ejecutando…' : '🚀 Test flujo RRHH' }}
      </button>
      <p v-if="phaseBResult" class="phase-b-result" :class="{ ok: phaseBResult.triggered, warn: !phaseBResult.triggered }">
        {{ phaseBMessage }}
      </p>
    </div>

    <section v-if="summary.length" class="audit-section">
      <h2>Resumen</h2>
      <table class="audit-table">
        <thead>
          <tr>
            <th>Automatización</th>
            <th>Ejecuciones</th>
            <th>Última ejecución</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in summary" :key="row.automation_name">
            <td><code>{{ row.automation_name }}</code></td>
            <td>{{ row.total_runs }}</td>
            <td>{{ formatDate(row.last_run) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="audit-section">
      <h2>Últimos logs ({{ logs.length }})</h2>
      <ul v-if="logs.length" class="log-list">
        <li v-for="log in logs" :key="log.id" class="log-item">
          <div class="log-head">
            <strong>{{ log.automation_name }}</strong>
            <span class="pill" :class="log.status">{{ log.status }}</span>
            <span class="agent">{{ log.agent }}</span>
            <time>{{ formatDate(log.executed_at) }}</time>
          </div>
          <div class="log-meta">
            <span>trigger: {{ log.trigger_type }}</span>
          </div>
        </li>
      </ul>
      <p v-else class="empty">Sin logs de automatización todavía.</p>
    </section>

    <router-link class="audit-link" to="/automations">← Volver a automatizaciones</router-link>
  </KpiPageShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const loading = ref(true)
const error = ref('')
const data = ref(null)
const phaseBRunning = ref(false)
const phaseBResult = ref(null)

const phaseBMessage = computed(() => {
  const r = phaseBResult.value
  if (!r) return ''
  if (r.triggered) return `Flujo disparado: ${r.event?.contract_id || 'ok'}`
  return r.reason || r.hint || 'No disparado — revisa flags Phase B'
})

const runPhaseBTest = async () => {
  phaseBRunning.value = true
  phaseBResult.value = null
  try {
    const api = (await import('@/services/api')).default
    phaseBResult.value = await api.post('/api/v1/test/contract-flow', {})
    if (phaseBResult.value?.triggered) {
      const audit = await api.get('/api/v1/automations/audit?limit=100')
      if (audit?.success !== false) data.value = audit
    }
  } catch (e) {
    phaseBResult.value = { triggered: false, reason: e?.message || 'Error en test' }
  } finally {
    phaseBRunning.value = false
  }
}

const logs = computed(() => data.value?.logs || [])
const summary = computed(() => data.value?.summary || [])

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
    data.value = await api.get('/api/v1/automations/audit?limit=100')
    if (data.value?.success === false) {
      error.value = data.value.error || 'Error cargando auditoría'
    }
  } catch (e) {
    error.value = e?.message || 'Error cargando auditoría'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.audit-badge {
  display: inline-block;
  margin: 0 0 16px;
  padding: 6px 12px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  font-size: 12px;
  color: #93c5fd;
}

.phase-b-actions {
  margin-bottom: 20px;
}

.phase-b-btn {
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
  font-size: 14px;
  cursor: pointer;
}

.phase-b-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.phase-b-result {
  margin: 10px 0 0;
  font-size: 13px;
}

.phase-b-result.ok {
  color: #10b981;
}

.phase-b-result.warn {
  color: #f59e0b;
}

.audit-section {
  margin-bottom: 28px;
}

.audit-section h2 {
  font-size: 18px;
  margin: 0 0 12px;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.audit-table th,
.audit-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
}

.log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.log-item {
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.log-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  font-size: 13px;
}

.pill.success {
  color: #10b981;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.pill.partial {
  color: #f59e0b;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent {
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
}

.log-meta {
  margin-top: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

.empty {
  color: rgba(255, 255, 255, 0.5);
}

.audit-link {
  color: #3b82f6;
  text-decoration: none;
  font-size: 14px;
}

.audit-link:hover {
  text-decoration: underline;
}
</style>
