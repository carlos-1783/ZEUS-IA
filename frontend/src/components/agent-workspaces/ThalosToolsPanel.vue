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

          <ThalosExecutionBadge module-badge="REAL" :inline="true" :show-global="false" />

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

          <ThalosExecutionBadge module-badge="PARCIAL" :inline="true" :show-global="false" />

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

      <div class="tool-card legacy">
        <!-- LEGACY MODE (NO REAL EXECUTION) — usar thalos_workspace_api /api/v1/thalos/v1/monitor -->
        <div class="card-title-row">
          <h5>Monitor de logs (heurístico)</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <p class="legacy-hint">Legacy workspaceTools — sin persistencia en BD.</p>

        <textarea v-model="logInput" placeholder="Líneas de log separadas por salto de línea"></textarea>

        <button :disabled="loading.logs" @click="runLogs">

          {{ loading.logs ? 'Analizando…' : 'Analizar texto' }}

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

import { workspaceTools } from '@/api/workspaceTools'

import {
  extractControlMetadata,
  fetchThalosStatus,
  runThalosMonitor,
  type ThalosControlMetadata,
  type ThalosStatusResponse,
} from '@/api/thalos_workspace_api'

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



const pickControl = (out: unknown): ThalosControlMetadata | null => extractControlMetadata(out)



onMounted(async () => {

  try {

    globalStatus.value = await fetchThalosStatus()

    const mode = globalStatus.value.system_default_mode

    if (mode === 'SIMULATION') {

      statusNote.value =

        'Modo simulación por defecto: auditoría y workspace son REAL_SAFE; backup y acciones destructivas requieren REAL_ACTIVE.'

    } else if (mode === 'REAL_SAFE') {

      statusNote.value = 'Modo REAL_SAFE: monitoreo y persistencia activos; ejecución destructiva bloqueada.'

    } else {

      statusNote.value = 'Modo REAL_ACTIVE: ejecución completa habilitada (revisar flags en Railway).'

    }

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

    const out = (await workspaceTools.runThalosLogMonitor({

      logs: logInput.value.split('\n').filter(Boolean),

    })) as Record<string, unknown>

    lastLogControl.value = pickControl(out)

    logResult.value = String(out?.text || 'Monitorización de logs completada.')

    emit('refreshed')

  } catch (err) {

    error.value = err instanceof Error ? err.message : String(err)

  } finally {

    loading.logs = false

  }

}

</script>



<style scoped>

.tools-panel {

  margin-top: 24px;

  padding: 22px;

  border: 1px solid rgba(15, 118, 110, 0.3);

  border-radius: 16px;

  background: #f0fdfa;

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

  background: white;

  border: 1px solid rgba(15, 118, 110, 0.35);

  border-radius: 12px;

  padding: 14px;

  display: flex;

  flex-direction: column;

  gap: 8px;

}

.tool-card.highlight {

  border-color: #0ea5e9;

  box-shadow: 0 0 0 1px rgba(14, 165, 233, 0.2);

}

.hint {

  margin: 0;

  font-size: 12px;

  color: #64748b;

}

.legacy-hint {

  margin: 0;

  font-size: 11px;

  color: #b45309;

}

.tool-card textarea {

  border: 1px solid rgba(148, 163, 184, 0.5);

  border-radius: 8px;

  padding: 8px;

  font-size: 13px;

  min-height: 70px;

}

.tool-card button {

  border: none;

  border-radius: 8px;

  background: #0f766e;

  color: #fff;

  padding: 8px 10px;

  cursor: pointer;

}

.tool-card.highlight button {

  background: #0369a1;

}

.tool-text {

  margin: 8px 0 0;

  padding: 10px;

  border-radius: 8px;

  background: #ecfeff;

  color: #0f172a;

  font-size: 13px;

  line-height: 1.4;

}

.tool-error {

  margin-top: 10px;

  color: #b91c1c;

}

.status-note {

  margin-top: 8px;

  font-size: 12px;

  color: #475569;

}

</style>

