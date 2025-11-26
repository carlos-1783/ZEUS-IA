<template>
  <section class="tools-panel">
    <header>
      <h4>💼 Herramientas RRHH</h4>
      <p>Onboarding completo desde fichajes hasta contratos.</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card">
        <h5>Fichaje facial</h5>
        <input v-model="faceForm.employee_id" placeholder="ID empleado" />
        <textarea v-model="faceForm.embedding" placeholder="embedding (coma)"></textarea>
        <button :disabled="loading.face" @click="runFace">
          {{ loading.face ? 'Procesando…' : 'Registrar' }}
        </button>
        <pre v-if="faceResult">{{ formatJson(faceResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Fichaje QR</h5>
        <input v-model="qrCode" placeholder="ZEUSCHECK|EMP1|timestamp" />
        <button :disabled="loading.qr" @click="runQr">
          {{ loading.qr ? 'Validando…' : 'Validar' }}
        </button>
        <pre v-if="qrResult">{{ formatJson(qrResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Gestor empleados</h5>
        <textarea v-model="employeesInput" placeholder="Nombre:Rol por línea"></textarea>
        <button :disabled="loading.schedule" @click="runSchedule">
          {{ loading.schedule ? 'Generando…' : 'Generar turnos' }}
        </button>
        <pre v-if="scheduleResult">{{ formatJson(scheduleResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Contrato RRHH</h5>
        <input v-model="contractForm.employee_name" placeholder="Empleado" />
        <input v-model="contractForm.role" placeholder="Rol" />
        <input type="number" v-model.number="contractForm.salary" placeholder="Salario anual" />
        <select v-model="contractForm.contract_type">
          <option value="indefinido">Indefinido</option>
          <option value="temporal">Temporal</option>
        </select>
        <button :disabled="loading.contract" @click="runContract">
          {{ loading.contract ? 'Compilando…' : 'Crear contrato' }}
        </button>
        <pre v-if="contractResult">{{ formatJson(contractResult) }}</pre>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'

const loading = reactive({ face: false, qr: false, schedule: false, contract: false })
const error = ref('')

const faceForm = reactive({ employee_id: 'EMP-001', embedding: '0.2,0.5,0.7', timestamp: new Date().toISOString() })
const qrCode = ref('ZEUSCHECK|EMP-001|2025-01-01T10:00:00Z')
const employeesInput = ref('Ana Torres:Soporte\nLuis Pérez:Logística')
const contractForm = reactive({ employee_name: 'Ana Torres', role: 'Soporte', salary: 24000, contract_type: 'indefinido' })

const faceResult = ref<any | null>(null)
const qrResult = ref<any | null>(null)
const scheduleResult = ref<any | null>(null)
const contractResult = ref<any | null>(null)

const formatJson = (value: unknown) => JSON.stringify(value, null, 2)

const runFace = async () => {
  error.value = ''
  loading.face = true
  try {
    const embedding = faceForm.embedding
      .split(',')
      .map((value) => Number(value.trim()))
      .filter((value) => !Number.isNaN(value))
    faceResult.value = await workspaceTools.runAfroditaFaceCheckIn({
      employee_id: faceForm.employee_id,
      embedding,
      timestamp: faceForm.timestamp,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.face = false
  }
}

const runQr = async () => {
  error.value = ''
  loading.qr = true
  try {
    qrResult.value = await workspaceTools.runAfroditaQrCheckIn({ qr_code: qrCode.value })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.qr = false
  }
}

const runSchedule = async () => {
  error.value = ''
  loading.schedule = true
  try {
    const employees = employeesInput.value
      .split('\n')
      .map((row) => row.trim())
      .filter(Boolean)
      .map((row) => {
        const [name, role] = row.split(':')
        return { name: name?.trim(), role: role?.trim() }
      })
    scheduleResult.value = await workspaceTools.runAfroditaEmployeeManager({ employees })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.schedule = false
  }
}

const runContract = async () => {
  error.value = ''
  loading.contract = true
  try {
    contractResult.value = await workspaceTools.runAfroditaContract({ ...contractForm })
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
.tool-card pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 8px;
  border-radius: 8px;
  max-height: 150px;
  overflow: auto;
  font-size: 12px;
}
.tool-error {
  margin-top: 10px;
  color: #b91c1c;
}
</style>

