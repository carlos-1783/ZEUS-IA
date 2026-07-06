<template>
  <div class="system-status-panel">
    <router-link to="/dashboard" class="back-link">← Volver al Dashboard</router-link>

    <header class="panel-header">
      <div>
        <h2>Estado del sistema</h2>
        <p class="subtitle">Visibilidad Phase A — flags Railway y clasificación por agente</p>
        <span class="system-badge">{{ status?.system_state || '…' }}</span>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="load">
        {{ loading ? 'Actualizando…' : 'Refrescar' }}
      </button>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section v-if="status" class="flags-section">
      <h3>Flags Railway</h3>
      <ul class="flags-grid">
        <li v-for="(value, key) in status.flags" :key="key" :class="{ on: value, off: !value }">
          <code>{{ key }}</code>
          <span>{{ value ? 'ON' : 'OFF' }}</span>
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
            <th>Status</th>
            <th>execution_mode</th>
            <th>Ready</th>
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
  return `Blockers: ${blockers.join(' · ')}`
})

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
.system-status-panel {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.back-link {
  display: inline-block;
  margin-bottom: 16px;
  color: #2563eb;
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
  font-size: 26px;
  color: #0f172a;
}

.subtitle {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 14px;
}

.system-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  background: #fef3c7;
  color: #b45309;
  text-transform: uppercase;
}

.refresh-btn {
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(15, 23, 42, 0.2);
  background: #fff;
  cursor: pointer;
  font-weight: 600;
}

.error-banner {
  padding: 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
  margin-bottom: 16px;
}

.flags-section,
.agents-section {
  margin-bottom: 28px;
  padding: 20px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  background: #fff;
}

.flags-section h3,
.agents-section h3 {
  margin: 0 0 14px;
  font-size: 16px;
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
  border-radius: 8px;
  font-size: 12px;
}

.flags-grid li.on {
  background: #dcfce7;
  color: #15803d;
}

.flags-grid li.off {
  background: #f1f5f9;
  color: #64748b;
}

.flags-grid code {
  font-size: 11px;
}

.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: #475569;
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
}

th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px 8px;
  text-align: left;
}

.status-pill,
.mode-pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}

.status-pill.partial { background: #fef3c7; color: #b45309; }
.status-pill.fake { background: #fee2e2; color: #b91c1c; }
.status-pill.disconnected { background: #f1f5f9; color: #64748b; }
.status-pill.real { background: #dcfce7; color: #15803d; }

.mode-pill {
  background: #e0e7ff;
  color: #3730a3;
}

.api-cell code {
  font-size: 11px;
}

.notes-list {
  margin: 16px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: #64748b;
}
</style>
