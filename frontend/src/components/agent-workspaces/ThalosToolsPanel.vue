<template>

  <section class="tools-panel">

    <header>

      <div class="header-row">

        <div>

          <h4>🛡️ Vigilancia activa</h4>

          <p>Ejecuta análisis reales contra el backend THALOS v1.</p>

        </div>

        <ThalosExecutionBadge
          v-if="globalStatus"
          :global-mode="globalStatus.system_default_mode"
          :control="globalStatus.thalos_control"
          :data-origin="globalStatus.data_origin"
          :real-execution="globalStatus.real_execution"
          :show-global="true"
        />

      </div>

    </header>

    <div class="tools-grid">

      <div class="tool-card highlight">

        <div class="card-title-row">

          <h5>Auditoría real (scan logs)</h5>

          <ThalosExecutionBadge :module-badge="moduleBadge('auditoria_real')" :inline="true" :show-global="false" />

        </div>

        <p class="hint">Analiza actividades y eventos de seguridad persistidos en BD.</p>

        <button :disabled="loading.monitor" @click="runRealMonitor">

          {{ loading.monitor ? 'Escaneando…' : 'Ejecutar auditoría' }}

        </button>

        <ThalosExecutionBadge

          v-if="lastMonitorControl"

          :control="lastMonitorControl"

          :show-global="false"

        />

        <p v-if="monitorSummary" class="tool-text">{{ monitorSummary }}</p>

      </div>

      <div class="tool-card">

        <div class="card-title-row">

          <h5>Backup del sistema</h5>

          <ThalosExecutionBadge :module-badge="moduleBadge('backup_system')" :inline="true" :show-global="false" />

        </div>

        <p class="hint">Genera copia local de zeus.db (si existe en el servidor).</p>

        <button :disabled="loading.backup" @click="runBackup">

          {{ loading.backup ? 'Procesando…' : 'Trigger backup' }}

        </button>

        <ThalosExecutionBadge

          v-if="lastBackupControl"

          :control="lastBackupControl"

          :show-global="false"

        />

        <p v-if="backupSummary" class="tool-text">{{ backupSummary }}</p>

      </div>

      <div class="tool-card" :class="{ real: moduleBadge('log_monitor') === 'REAL' }">
        <div class="card-title-row">
          <h5>Monitor de logs (BD)</h5>
          <ThalosExecutionBadge :module-badge="moduleBadge('log_monitor')" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Ingesta real → thalos_events → motor de amenazas → alertas.</p>

        <textarea v-model="logInput" placeholder="Líneas de log separadas por salto de línea"></textarea>

        <button :disabled="loading.logs" @click="runLogs">

          {{ loading.logs ? 'Analizando…' : 'Ingestar logs en BD' }}

        </button>

        <ThalosExecutionBadge

          v-if="lastLogControl"

          :control="lastLogControl"

          :show-global="false"

        />

        <p v-if="logResult" class="tool-text">{{ logResult }}</p>

      </div>

    </div>

    <p v-if="error" class="tool-error">{{ error }}</p>

    <p v-if="statusNote" class="status-note">{{ statusNote }}</p>

  </section>

</template>



<script setup lang="ts">

import { onMounted, reactive, ref } from 'vue'

import {
  extractControlMetadata,
  fetchThalosAudit,
  fetchThalosStatus,
  ingestThalosLogs,
  runThalosMonitor,
  type ThalosControlMetadata,
  type ThalosStatusResponse,
} from '@/api/thalos_workspace_api'

import { resolveThalosModuleBadge } from '@/utils/zeus_safe_lock'

import api from '@/services/api'

import ThalosExecutionBadge from './ThalosExecutionBadge.vue'



const emit = defineEmits<{ (e: 'refreshed'): void }>()



const loading = reactive({ logs: false, monitor: false, backup: false })

const error = ref('')

const statusNote = ref('')

const globalStatus = ref<ThalosStatusResponse | null>(null)

const lastMonitorControl = ref<ThalosControlMetadata | null>(null)

const lastBackupControl = ref<ThalosControlMetadata | null>(null)

const lastLogControl = ref<ThalosControlMetadata | null>(null)

const logInput = ref('INFO Login ok\nWARN failed login user=demo')

const logResult = ref<string | null>(null)

const monitorSummary = ref<string | null>(null)

const backupSummary = ref<string | null>(null)
const auditStats = ref<{ event_count?: number; open_alerts?: number; worker?: { running?: boolean } } | null>(null)

const moduleBadge = (module: string) => resolveThalosModuleBadge(module, globalStatus.value)



const pickControl = (out: unknown): ThalosControlMetadata | null => extractControlMetadata(out)



onMounted(async () => {
  try {
    globalStatus.value = await fetchThalosStatus()
    const audit = await fetchThalosAudit().catch(() => null)
    auditStats.value = audit as typeof auditStats.value
    const mode = globalStatus.value.system_default_mode
    const ev = auditStats.value?.event_count ?? 0
    const al = auditStats.value?.open_alerts ?? 0
    const wrk = auditStats.value?.worker?.running ? 'activo' : 'inactivo'
    statusNote.value = `Modo ${mode} · ${ev} eventos BD · ${al} alertas abiertas · worker ${wrk}`
  } catch {
    /* optional */
  }
})



const runRealMonitor = async () => {

  error.value = ''

  loading.monitor = true

  monitorSummary.value = null

  lastMonitorControl.value = null

  try {

    const out = (await runThalosMonitor()) as Record<string, any>

    lastMonitorControl.value = pickControl(out)

    const scan = out?.scan || {}

    const alerts = (scan.pattern_alerts || []).length

    const fails = (scan.failed_login_candidates || []).length

    monitorSummary.value = `Riesgo: ${scan.risk_level || 'ok'} · ${scan.activities_scanned || 0} actividades · ${alerts} alertas · ${fails} candidatos brute-force`

    emit('refreshed')

  } catch (err) {

    error.value = err instanceof Error ? err.message : String(err)

  } finally {

    loading.monitor = false

  }

}



const runBackup = async () => {

  error.value = ''

  loading.backup = true

  backupSummary.value = null

  lastBackupControl.value = null

  try {

    const out = (await api.post('/api/v1/thalos/v1/execute', { action: 'trigger_backup' })) as Record<string, any>

    lastBackupControl.value = pickControl(out)

    const bk = out?.result || {}

    backupSummary.value = bk.backup_created

      ? `Backup OK: ${bk.backup_path}`

      : String(out?.reason || bk.notes || 'Backup no ejecutado (flag o sin zeus.db local)')

    emit('refreshed')

  } catch (err: unknown) {

    const msg = err instanceof Error ? err.message : String(err)

    if (msg.includes('403') || msg.toLowerCase().includes('execution')) {

      backupSummary.value = 'Backup requiere THALOS_EXECUTION_ENABLED + THALOS_BACKUP_ENABLED.'

    } else {

      error.value = msg

    }

  } finally {

    loading.backup = false

  }

}



const runLogs = async () => {
  error.value = ''
  loading.logs = true
  lastLogControl.value = null
  try {
    const lines = logInput.value.split('\n').filter(Boolean)
    const out = (await ingestThalosLogs(lines)) as Record<string, unknown>
    lastLogControl.value = pickControl(out)
    const inserted = (out as { events_inserted?: number }).events_inserted ?? 0
    const alerts = (out as { alerts_created?: number }).alerts_created ?? 0
    logResult.value = `${inserted} evento(s) en BD · ${alerts} alerta(s) generada(s)`
    emit('refreshed')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.logs = false
  }
}

</script>



<style scoped>

/* El unico acento de la vista ya vive en la cabecera del modal --
   aqui todo queda en tokens neutros (antes: fondo/borde teal en el
   panel, borde celeste "highlight", botones teal/azul solidos). */
.tools-panel {

  margin-top: 24px;

  padding: 22px;

  border: 1px solid var(--zeus-border, #e1e5eb);

  border-radius: var(--zeus-radius-lg, 16px);

  background: var(--zeus-surface, #fff);

}

.header-row {

  display: flex;

  justify-content: space-between;

  align-items: flex-start;

  gap: 12px;

  flex-wrap: wrap;

}

.card-title-row {

  display: flex;

  justify-content: space-between;

  align-items: center;

  gap: 8px;

  flex-wrap: wrap;

}

.tools-grid {

  display: grid;

  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));

  gap: 16px;

}

.tool-card {

  background: var(--zeus-surface, #fff);

  border: 1px solid var(--zeus-border, #e1e5eb);

  border-radius: var(--zeus-radius, 12px);

  padding: 14px;

  display: flex;

  flex-direction: column;

  gap: 8px;

}

.hint {

  margin: 0;

  font-size: 12px;

  color: var(--zeus-text-secondary, #52607a);

}

.legacy-hint {

  margin: 0;

  font-size: 11px;

  color: var(--zeus-warning, #f59e0b);

}

.tool-card textarea {

  border: 1px solid var(--zeus-border-strong, #cdd3db);

  border-radius: var(--zeus-radius-sm, 8px);

  padding: 8px;

  font-size: 13px;

  min-height: 70px;

  color: var(--zeus-text, #0f172a);

  background: var(--zeus-surface, #fff);

}

.tool-card button {

  border: 1px solid #D1D5DB;

  border-radius: var(--zeus-radius-sm, 8px);

  background: #ffffff;

  color: var(--zeus-text, #0f172a);

  padding: 8px 10px;

  cursor: pointer;

  font-weight: var(--zeus-weight-medium, 500);

  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);

}

.tool-card button:hover:not(:disabled) {

  border-color: #9aa2af;

}

.tool-text {

  margin: 8px 0 0;

  padding: 10px;

  border-radius: var(--zeus-radius-sm, 8px);

  background: var(--zeus-bg-subtle, #eef1f6);

  color: var(--zeus-text, #0f172a);

  font-size: 13px;

  line-height: 1.4;

}

.tool-error {

  margin-top: 10px;

  color: var(--zeus-danger, #ef4444);

}

.status-note {

  margin-top: 8px;

  font-size: 12px;

  color: var(--zeus-text-secondary, #52607a);

}

</style>

