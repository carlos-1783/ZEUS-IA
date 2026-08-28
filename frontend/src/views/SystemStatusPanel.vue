<template>
  <div class="system-status-panel">
    <router-link to="/dashboard" class="back-link">← Volver al Dashboard</router-link>

    <header class="panel-header">
      <div>
        <h2>Estado del sistema</h2>
        <p class="subtitle">Visibilidad Phase A — flags Railway y clasificación por agente</p>
        <span class="system-badge">{{ systemStateLabel }}</span>
      </div>
      <button class="refresh-btn zeus-btn zeus-btn-accent" :disabled="loading" @click="load">
        {{ loading ? 'Actualizando…' : 'Refrescar' }}
      </button>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section v-if="status" class="flags-section">
      <h3>Flags Railway</h3>
      <ul class="flags-grid">
        <li v-for="(value, key) in status.flags" :key="key" :class="{ on: value, off: !value }">
          <span class="flag-label">{{ flagLabel(key) }}</span>
          <span>{{ value ? 'Activo' : 'Inactivo' }}</span>
        </li>
      </ul>
      <p v-if="status.zeus_core_orchestration_active" class="hint hint-ok">
        Orquestación ZEUS CORE activa — multi-agente en event bus.
      </p>
      <p v-else-if="status.ready_for_flags_activation" class="hint">
        Sistema listo para activación segura de flags (Fase B).
      </p>
      <p v-if="fixPassBlockers" class="blockers">{{ fixPassBlockers }}</p>
    </section>

    <section v-if="status" class="agents-section">
      <h3>Agentes</h3>
      <table>
        <thead>
          <tr>
            <th>Agente</th>
            <th>Estado</th>
            <th>Modo de ejecución</th>
            <th>Listo</th>
            <th>API</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="agent in status.agents" :key="agent.name">
            <td><strong>{{ agent.name }}</strong></td>
            <td><span class="status-pill" :class="agent.status.toLowerCase()">{{ agent.status }}</span></td>
            <td><span class="mode-pill">{{ agent.execution_mode }}</span></td>
            <td>{{ agent.execution_ready ? '✓' : '—' }}</td>
            <td class="api-cell"><code>{{ agent.api_prefix }}</code></td>
          </tr>
        </tbody>
      </table>
      <ul class="notes-list">
        <li v-for="agent in status.agents" :key="agent.name + '-note'">
          <strong>{{ agent.name }}:</strong> {{ agent.notes }}
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchSystemExecutionStatus,
  fetchSystemFixPass,
  type SystemExecutionStatusResponse,
} from '@/api/system_visibility_api'

const loading = ref(false)
const error = ref('')
const status = ref<SystemExecutionStatusResponse | null>(null)
const fixPass = ref<Record<string, unknown> | null>(null)

const fixPassBlockers = computed(() => {
  const blockers = fixPass.value?.critical_blockers
  if (!Array.isArray(blockers) || !blockers.length) return ''
  return `Bloqueos: ${blockers.join(' · ')}`
})

// El backend devuelve identificadores tecnicos crudos (system_state,
// nombres de flags de Railway) -- se traducen aqui a espanol antes de
// mostrarlos, con un formateo generico de fallback para cualquier
// valor no mapeado (nunca se muestra el string crudo del backend).
const SYSTEM_STATE_LABELS: Record<string, string> = {
  CONTROLLED_UNTRUSTED: 'Controlado — pendiente de confianza total',
  ORCHESTRATION_ACTIVE: 'Orquestación activa',
}

const systemStateLabel = computed(() => {
  const raw = status.value?.system_state
  if (!raw) return '…'
  return SYSTEM_STATE_LABELS[raw] || humanizeFlagKey(raw)
})

const FLAG_LABELS: Record<string, string> = {
  AFRODITA_EXECUTION_ENABLED: 'AFRODITA — ejecución real',
  AFRODITA_READ_ONLY_MODE: 'AFRODITA — modo solo lectura',
  THALOS_EXECUTION_ENABLED: 'THALOS — ejecución real',
  THALOS_REAL_LOGS_ENABLED: 'THALOS — logs reales',
  THALOS_BACKUP_ENABLED: 'THALOS — backup automático',
  JUSTICE_REAL_AUDIT_ENABLED: 'JUSTICIA — auditoría real',
  JUSTICE_READ_ONLY_MODE: 'JUSTICIA — modo solo lectura',
  ZEUS_CORE_ENABLED: 'ZEUS CORE — activado',
  ZEUS_AGENT_ENABLED: 'ZEUS — agente activado',
  RAFAEL_EXECUTION_ENABLED: 'RAFAEL — ejecución real',
  ZEUS_EVENT_BUS_ENABLED: 'ZEUS — bus de eventos',
  ZEUS_AUTOMATION_ENGINE_ENABLED: 'ZEUS — motor de automatizaciones',
}

function humanizeFlagKey(key: string): string {
  return key
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function flagLabel(key: string): string {
  return FLAG_LABELS[key] || humanizeFlagKey(key)
}

const load = async () => {
  error.value = ''
  loading.value = true
  try {
    const [execStatus, fix] = await Promise.all([
      fetchSystemExecutionStatus(),
      fetchSystemFixPass(),
    ])
    status.value = execStatus
    fixPass.value = fix
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* Fondo de bandas metalicas obligatorio en toda pagina (ver
   zeus-light-system.css) -- este panel no tenia ningun token del
   sistema nuevo. */
.system-status-panel {
  position: relative;
  min-height: 100vh;
  max-width: none;
  margin: 0;
  padding: 32px 24px 64px;
  background-image: var(--zeus-bg);
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  color: var(--zeus-text, #0f172a);
  box-sizing: border-box;
}

.system-status-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}

.system-status-panel > * {
  position: relative;
  max-width: 960px;
  margin-left: auto;
  margin-right: auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 16px;
  color: var(--zeus-accent, #4f46e5);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
}

.back-link:hover {
  text-decoration: underline;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.panel-header h2 {
  margin: 0 0 4px;
  font-size: var(--zeus-text-xl, 26px);
  color: var(--zeus-text, #0f172a);
}

.subtitle {
  margin: 0 0 8px;
  color: var(--zeus-text-secondary, #52607a);
  font-size: 14px;
}

.system-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: var(--zeus-radius-sm, 6px);
  background: var(--zeus-warning-soft, #fef6e7);
  color: #b45309;
}

.refresh-btn {
  white-space: nowrap;
}

.error-banner {
  padding: 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--zeus-danger-soft, #fdecec);
  color: #b91c1c;
  margin-bottom: 16px;
}

.flags-section,
.agents-section {
  margin-bottom: 28px;
  padding: 20px;
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius, 12px);
  background: var(--zeus-surface, #fff);
  box-shadow: var(--zeus-shadow-sm, 0 1px 2px rgba(15, 23, 42, 0.04));
}

.flags-section h3,
.agents-section h3 {
  margin: 0 0 14px;
  font-size: var(--zeus-text-md, 16px);
  color: var(--zeus-text, #0f172a);
}

.flags-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

.flags-grid li {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: 12px;
}

.flags-grid li.on {
  background: var(--zeus-success-soft, #e9faf3);
  color: #15803d;
}

.flags-grid li.off {
  background: var(--zeus-bg-subtle, #eef1f6);
  color: var(--zeus-text-secondary, #52607a);
}

.flag-label {
  font-size: 12px;
}

.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--zeus-text-secondary, #52607a);
}

.hint-ok {
  color: #15803d;
  font-weight: 600;
}

.blockers {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b91c1c;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  color: var(--zeus-text, #0f172a);
}

th,
td {
  border-bottom: 1px solid var(--zeus-border, #e1e5eb);
  padding: 10px 8px;
  text-align: left;
}

th {
  color: var(--zeus-text-secondary, #52607a);
  font-weight: var(--zeus-weight-semibold, 600);
}

.status-pill,
.mode-pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--zeus-radius-sm, 6px);
}

.status-pill.partial { background: var(--zeus-warning-soft, #fef6e7); color: #b45309; }
.status-pill.fake { background: var(--zeus-danger-soft, #fdecec); color: #b91c1c; }
.status-pill.disconnected { background: var(--zeus-bg-subtle, #eef1f6); color: var(--zeus-text-secondary, #52607a); }
.status-pill.real { background: var(--zeus-success-soft, #e9faf3); color: #15803d; }

.mode-pill {
  background: var(--zeus-accent-2-soft, #eef2ff);
  color: #3730a3;
}

.api-cell code {
  font-size: 11px;
}

.notes-list {
  margin: 16px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--zeus-text-secondary, #52607a);
}
</style>
