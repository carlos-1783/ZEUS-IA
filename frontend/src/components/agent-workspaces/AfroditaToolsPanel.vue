<template>
  <section class="tools-panel">
    <header>
      <div class="header-row">
        <div>
          <h4>💼 Herramientas RRHH</h4>
          <p>Fichajes, empleados y turnos con estado REAL / SIMULADO visible.</p>
        </div>
        <ThalosExecutionBadge
          v-if="globalStatus"
          :global-mode="globalStatus.system_default_mode"
          :control="globalStatus.afrodita_control"
          :data-origin="globalStatus.data_origin"
          :real-execution="globalStatus.real_execution"
        />
      </div>
      <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card legacy">
        <div class="card-title-row">
          <h5>Fichaje facial</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Sin biometría real. Con flags activos usa register_checkin (device).</p>
        <select v-model="faceForm.employee_id">
          <option value="">— Selecciona empleado —</option>
          <option v-for="emp in employees" :key="emp.employee_code" :value="emp.employee_code">
            {{ emp.full_name }} ({{ emp.employee_code }})
          </option>
        </select>
        <input v-model="faceForm.employee_id" placeholder="O escribe código manual" />
        <button :disabled="loading.face" @click="runFace">
          {{ loading.face ? 'Procesando…' : 'Registrar' }}
        </button>
        <ThalosExecutionBadge v-if="lastFaceControl" :control="lastFaceControl" :show-global="false" />
        <p v-if="faceResult" class="tool-text">{{ faceResult }}</p>
      </div>
      <div class="tool-card highlight">
        <div class="card-title-row">
          <h5>Fichaje QR</h5>
          <ThalosExecutionBadge module-badge="PARCIAL" :inline="true" :show-global="false" />
        </div>
        <p class="hint">ZEUSCHECK|código|timestamp (máx 5 min). Ejecución real requiere flags.</p>
        <input v-model="qrCode" placeholder="ZEUSCHECK|EMP1|timestamp" />
        <button :disabled="loading.qr" @click="runQr">
          {{ loading.qr ? 'Validando…' : 'Validar' }}
        </button>
        <ThalosExecutionBadge v-if="lastQrControl" :control="lastQrControl" :show-global="false" />
        <p v-if="qrResult" class="tool-text">{{ qrResult }}</p>
      </div>
      <div class="tool-card">
        <div class="card-title-row">
          <h5>Gestor empleados</h5>
          <ThalosExecutionBadge module-badge="REAL" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Lectura desde company_employees (solo lectura).</p>
        <button :disabled="loading.employees" @click="() => loadEmployees()">
          {{ loading.employees ? 'Cargando…' : 'Cargar empleados' }}
        </button>
        <ul v-if="employees.length" class="emp-list">
          <li v-for="emp in employees" :key="emp.employee_code">
            <strong>{{ emp.full_name }}</strong>
            <span>{{ emp.employee_code }} · {{ emp.role_title || '—' }}</span>
          </li>
        </ul>
        <p v-else-if="employeesLoaded" class="hint">Sin empleados en BD para tu empresa.</p>
        <ThalosExecutionBadge v-if="lastEmpControl" :control="lastEmpControl" :show-global="false" />
      </div>
      <div class="tool-card">
        <div class="card-title-row">
          <h5>Turnos (lectura)</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <p class="hint">employee_schedules · activar AFRODITA_USE_REAL_SCHEDULES en Railway.</p>
        <button :disabled="loading.schedules" @click="loadSchedules">
          {{ loading.schedules ? 'Cargando…' : 'Ver turnos reales' }}
        </button>
        <ul v-if="schedules.length" class="emp-list">
          <li v-for="(s, i) in schedules.slice(0, 8)" :key="i">
            {{ s.employee_id }} · {{ s.day_name }} {{ s.start_time }}-{{ s.end_time }}
          </li>
        </ul>
        <p v-if="scheduleNote" class="tool-text">{{ scheduleNote }}</p>
        <ThalosExecutionBadge v-if="lastSchedControl" :control="lastSchedControl" :show-global="false" />
      </div>
      <div class="tool-card legacy">
        <div class="card-title-row">
          <h5>Contrato RRHH</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <input v-model="contractForm.employee_name" placeholder="Empleado" />
        <input v-model="contractForm.role" placeholder="Rol" />
        <input type="number" v-model.number="contractForm.salary" placeholder="Salario anual" />
        <select v-model="contractForm.contract_type">
          <option value="indefinido">Indefinido</option>
          <option value="temporal">Temporal</option>
        </select>
        <button :disabled="loading.contract" @click="runContract">
          {{ loading.contract ? 'Compilando…' : 'Crear borrador' }}
        </button>
        <p v-if="contractResult" class="tool-text">{{ contractResult }}</p>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'
import {
  extractAfroditaControl,
  fetchAfroditaEmployees,
  fetchAfroditaSchedules,
  fetchAfroditaStatus,
  type AfroditaControlMetadata,
  type AfroditaEmployee,
  type AfroditaScheduleRow,
  type AfroditaStatusResponse,
} from '@/api/afrodita_workspace_api'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

const loading = reactive({
  face: false,
  qr: false,
  employees: false,
  schedules: false,
  contract: false,
})
const error = ref('')
const statusNote = ref('')
const globalStatus = ref<AfroditaStatusResponse | null>(null)
const employees = ref<AfroditaEmployee[]>([])
const employeesLoaded = ref(false)
const schedules = ref<AfroditaScheduleRow[]>([])
const scheduleNote = ref<string | null>(null)

const lastFaceControl = ref<AfroditaControlMetadata | null>(null)
const lastQrControl = ref<AfroditaControlMetadata | null>(null)
const lastEmpControl = ref<AfroditaControlMetadata | null>(null)
const lastSchedControl = ref<AfroditaControlMetadata | null>(null)

const faceForm = reactive({ employee_id: '', timestamp: new Date().toISOString() })
const qrCode = ref('')
const contractForm = reactive({
  employee_name: 'Ana Torres',
  role: 'Soporte',
  salary: 24000,
  contract_type: 'indefinido',
})

const faceResult = ref<string | null>(null)
const qrResult = ref<string | null>(null)
const contractResult = ref<string | null>(null)

const pickControl = (out: unknown): AfroditaControlMetadata | null => extractAfroditaControl(out)

const refreshQrDefault = () => {
  const code = employees.value[0]?.employee_code || 'EMP-001'
  qrCode.value = `ZEUSCHECK|${code}|${new Date().toISOString()}`
}

onMounted(async () => {
  try {
    globalStatus.value = await fetchAfroditaStatus()
    const mode = globalStatus.value.system_default_mode
    if (mode === 'READ_ONLY') {
      statusNote.value =
        'Modo lectura: empleados reales; fichajes validan pero no persisten hasta AFRODITA_EXECUTION_ENABLED=true y READ_ONLY=false.'
    } else if (mode === 'REAL_ACTIVE') {
      statusNote.value = 'Ejecución activa: fichajes pasan por register_checkin → time_cost_checkins.'
    } else {
      statusNote.value = 'Modo simulación: solo operaciones marcadas como REAL leen BD.'
    }
    await loadEmployees(true)
    refreshQrDefault()
  } catch {
    refreshQrDefault()
  }
})

const loadEmployees = async (silent = false) => {
  if (!silent) error.value = ''
  loading.employees = true
  lastEmpControl.value = null
  try {
    const out = await fetchAfroditaEmployees()
    lastEmpControl.value = pickControl(out)
    employees.value = out.employees || []
    employeesLoaded.value = true
    if (employees.value.length && !faceForm.employee_id) {
      faceForm.employee_id = employees.value[0].employee_code
    }
    refreshQrDefault()
  } catch (err) {
    if (!silent) error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.employees = false
  }
}

const loadSchedules = async () => {
  error.value = ''
  loading.schedules = true
  scheduleNote.value = null
  lastSchedControl.value = null
  try {
    const out = await fetchAfroditaSchedules()
    lastSchedControl.value = pickControl(out)
    schedules.value = out.schedules || []
    scheduleNote.value =
      schedules.value.length > 0
        ? `${schedules.value.length} turnos cargados desde employee_schedules`
        : String((out as { note?: string }).note || 'Sin turnos en BD o flag desactivado.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.schedules = false
  }
}

const runFace = async () => {
  error.value = ''
  loading.face = true
  faceResult.value = null
  lastFaceControl.value = null
  try {
    const out = (await workspaceTools.runAfroditaFaceCheckIn({
      employee_id: faceForm.employee_id,
      embedding: [0.2, 0.5, 0.7],
      timestamp: faceForm.timestamp,
    })) as Record<string, unknown>
    lastFaceControl.value = pickControl(out)
    const res = (out.result || {}) as Record<string, unknown>
    faceResult.value = String(
      out.text ||
        res.reason ||
        (res.executed ? `Fichaje OK (${res.employee_id})` : 'Fichaje simulado (sin biometría)')
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.face = false
  }
}

const runQr = async () => {
  error.value = ''
  loading.qr = true
  qrResult.value = null
  lastQrControl.value = null
  try {
    const out = (await workspaceTools.runAfroditaQrCheckIn({ qr_code: qrCode.value })) as Record<string, unknown>
    lastQrControl.value = pickControl(out)
    qrResult.value = String(out.text || 'Fichaje QR procesado.')
    refreshQrDefault()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.qr = false
  }
}

const runContract = async () => {
  error.value = ''
  loading.contract = true
  try {
    const out = await workspaceTools.runAfroditaContract({ ...contractForm })
    contractResult.value = String((out as { text?: string }).text || 'Contrato RRHH generado (simulado).')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.contract = false
  }
}
</script>

<style scoped>
.tools-panel {
  margin-top: 24px;
  padding: 22px;
  border-radius: 16px;
  border: 1px solid rgba(219, 39, 119, 0.3);
  background: #fff0f6;
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
  gap: 14px;
}
.tool-card {
  background: white;
  border: 1px solid rgba(219, 39, 119, 0.4);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tool-card.highlight {
  border-color: #db2777;
  box-shadow: 0 0 0 1px rgba(219, 39, 119, 0.15);
}
.tool-card.legacy {
  opacity: 0.95;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}
.status-note {
  margin-top: 8px;
  font-size: 12px;
  color: #475569;
}
.tool-card textarea,
.tool-card input,
.tool-card select {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
}
.tool-card button {
  border: none;
  border-radius: 8px;
  background: #db2777;
  color: #fff;
  padding: 8px 10px;
  cursor: pointer;
}
.emp-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #334155;
}
.emp-list li {
  margin-bottom: 4px;
}
.emp-list span {
  display: block;
  color: #64748b;
}
.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 8px;
  background: #fdf2f8;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.4;
}
.tool-error {
  margin-top: 10px;
  color: #b91c1c;
}
</style>
