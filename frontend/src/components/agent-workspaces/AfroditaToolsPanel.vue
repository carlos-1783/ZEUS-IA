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
        <p v-if="faceResult" class="tool-text">{{ faceResult }}</p>
      </div>
      <div class="tool-card">
        <h5>Fichaje QR</h5>
        <input v-model="qrCode" placeholder="ZEUSCHECK|EMP1|timestamp" />
        <button :disabled="loading.qr" @click="runQr">
          {{ loading.qr ? 'Validando…' : 'Validar' }}
        </button>
        <p v-if="qrResult" class="tool-text">{{ qrResult }}</p>
      </div>
      <div class="tool-card">
        <h5>Gestor empleados</h5>
        <textarea v-model="employeesInput" placeholder="Nombre:Rol por línea"></textarea>
        <button :disabled="loading.schedule" @click="runSchedule">
          {{ loading.schedule ? 'Generando…' : 'Generar turnos' }}
        </button>
        <p v-if="scheduleResult" class="tool-text">{{ scheduleResult }}</p>
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
        <p v-if="contractResult" class="tool-text">{{ contractResult }}</p>
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

const faceResult = ref<string | null>(null)
const qrResult = ref<string | null>(null)
const scheduleResult = ref<string | null>(null)
const contractResult = ref<string | null>(null)

const runFace = async () => {
  error.value = ''
  loading.face = true
  try {
    const embedding = faceForm.embedding
      .split(',')
      .map((value) => Number(value.trim()))
      .filter((value) => !Number.isNaN(value))
    const out = await workspaceTools.runAfroditaFaceCheckIn({
      employee_id: faceForm.employee_id,
      embedding,
      timestamp: faceForm.timestamp,
    })
    faceResult.value = String((out as any)?.text || 'Fichaje facial registrado.')
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
    const out = await workspaceTools.runAfroditaQrCheckIn({ qr_code: qrCode.value })
    qrResult.value = String((out as any)?.text || 'Fichaje QR validado.')
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
    const out = await workspaceTools.runAfroditaEmployeeManager({ employees })
    scheduleResult.value = String((out as any)?.text || 'Turnos generados correctamente.')
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
    const out = await workspaceTools.runAfroditaContract({ ...contractForm })
    contractResult.value = String((out as any)?.text || 'Contrato RRHH generado.')
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
