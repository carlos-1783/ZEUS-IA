<template>
  <KpiPageShell
    title="Auditoría de automatizaciones"
    subtitle="Modo observabilidad — solo lectura"
    :loading="loading"
    :error="error"
  >
    <p v-if="data?.read_only" class="audit-badge">🔒 Modo auditoría — solo lectura</p>

    <div class="phase-b-actions">
      <button
        type="button"
        class="phase-b-btn"
        :disabled="phaseBRunning"
        @click="runPhaseBTest"
      >
        {{ phaseBRunning ? 'Ejecutando…' : '🚀 Test flujo RRHH' }}
      </button>
      <button
        type="button"
        class="phase-c-btn"
        :disabled="phaseCRunning"
        @click="runPhaseCTest"
      >
        {{ phaseCRunning ? 'Evaluando…' : '💰 Test Payment Risk' }}
      </button>
      <p v-if="phaseBResult" class="phase-b-result" :class="{ ok: phaseBResult.triggered, warn: !phaseBResult.triggered }">
        {{ phaseBMessage }}
      </p>
      <p v-if="phaseCResult" class="phase-c-result" :class="{ ok: phaseCResult.triggered, warn: !phaseCResult.triggered }">
        {{ phaseCMessage }}
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
const phaseCRunning = ref(false)
const phaseCResult = ref(null)

const phaseCMessage = computed(() => {
  const r = phaseCResult.value
  if (!r) return ''
  if (r.triggered) {
    const risk = r.risk?.risk || r.event?.amount
    return `Payment risk: ${risk || 'ok'}`
  }
  return r.reason || r.hint || 'No disparado — revisa flags Phase C'
})

const runPhaseCTest = async () => {
  phaseCRunning.value = true
  phaseCResult.value = null
  try {
    const api = (await import('@/services/api')).default
    phaseCResult.value = await api.post('/api/v1/test/payment-risk', {})
    if (phaseCResult.value?.triggered) {
      const audit = await api.get('/api/v1/automations/audit?limit=100')
      if (audit?.success !== false) data.value = audit
    }
  } catch (e) {
    phaseCResult.value = { triggered: false, reason: e?.message || 'Error en test' }
  } finally {
    phaseCRunning.value = false
  }
}

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
  background: var(--zeus-info-soft, #eaf2ff);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: var(--zeus-text-xs, 12px);
  color: var(--zeus-text-secondary, #52607a);
}

.phase-b-actions {
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

/* Unico acento de la vista: "Test flujo RRHH" es la accion principal.
   "Test Payment Risk" queda como accion secundaria/neutra para no
   competir con ella (antes: verde vs naranja compitiendo). */
.phase-b-btn {
  padding: 10px 16px;
  border-radius: var(--zeus-radius-sm, 8px);
  border: none;
  background: var(--zeus-accent-gradient);
  color: #ffffff;
  box-shadow: var(--zeus-accent-gradient-shadow);
  font-size: 14px;
  font-weight: var(--zeus-weight-semibold, 600);
  cursor: pointer;
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.phase-b-btn:hover:not(:disabled) {
  box-shadow: var(--zeus-accent-gradient-shadow-hover);
  transform: translateY(-1px);
}

.phase-c-btn {
  padding: 10px 16px;
  border-radius: var(--zeus-radius-sm, 8px);
  border: 1px solid #D1D5DB;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  font-size: 14px;
  font-weight: var(--zeus-weight-medium, 500);
  cursor: pointer;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.phase-c-btn:hover:not(:disabled) {
  border-color: #9aa2af;
}

.phase-b-btn:disabled,
.phase-c-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.phase-b-result,
.phase-c-result {
  flex-basis: 100%;
  margin: 0;
  font-size: 13px;
}

.phase-b-result.ok,
.phase-c-result.ok {
  color: var(--zeus-success, #10b981);
}

.phase-b-result.warn,
.phase-c-result.warn {
  color: var(--zeus-warning, #f59e0b);
}

.audit-section {
  margin-bottom: 28px;
}

.audit-section h2 {
  font-size: var(--zeus-text-lg, 18px);
  color: var(--zeus-text, #0f172a);
  margin: 0 0 12px;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  color: var(--zeus-text, #0f172a);
}

.audit-table th,
.audit-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--zeus-border, #e1e5eb);
  text-align: left;
}

.audit-table th {
  color: var(--zeus-text-secondary, #52607a);
  font-weight: var(--zeus-weight-semibold, 600);
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
  background: var(--zeus-surface, #fff);
  border-radius: var(--zeus-radius-sm, 8px);
  border: 1px solid var(--zeus-border, #e1e5eb);
}

.log-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  font-size: 13px;
  color: var(--zeus-text, #0f172a);
}

.pill.success {
  color: var(--zeus-success, #10b981);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.pill.partial {
  color: var(--zeus-warning, #f59e0b);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent {
  color: var(--zeus-text-secondary, #52607a);
  font-size: 12px;
}

.log-meta {
  margin-top: 6px;
  font-size: 11px;
  color: var(--zeus-text-muted, #8792a6);
}

.empty {
  color: var(--zeus-text-secondary, #52607a);
}

.audit-link {
  color: var(--zeus-accent, #4f46e5);
  text-decoration: none;
  font-size: 14px;
}

.audit-link:hover {
  text-decoration: underline;
}
</style>
