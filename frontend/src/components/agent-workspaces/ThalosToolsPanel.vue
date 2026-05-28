<template>
  <section class="tools-panel">
    <header>
      <h4>🛡️ Vigilancia activa</h4>
      <p>Ejecuta análisis de seguridad sin abrir la consola.</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card">
        <h5>Monitor de logs</h5>
        <textarea v-model="logInput" placeholder="Líneas de log separadas por salto de línea"></textarea>
        <button :disabled="loading.logs" @click="runLogs">
          {{ loading.logs ? 'Analizando…' : 'Analizar' }}
        </button>
        <p v-if="logResult" class="tool-text">{{ logResult }}</p>
      </div>
      <div class="tool-card">
        <h5>Detector de amenazas</h5>
        <textarea v-model="eventsInput" placeholder='Fuente: severidad (ej. "api:3")'></textarea>
        <button :disabled="loading.threats" @click="runThreats">
          {{ loading.threats ? 'Procesando…' : 'Calcular riesgo' }}
        </button>
        <p v-if="threatResult" class="tool-text">{{ threatResult }}</p>
      </div>
      <div class="tool-card">
        <h5>Revocar credenciales</h5>
        <input v-model="credentialInput" placeholder="cred-1, cred-2" />
        <button :disabled="loading.credentials" @click="runCredentials">
          {{ loading.credentials ? 'Revocando…' : 'Revocar' }}
        </button>
        <p v-if="credentialResult" class="tool-text">{{ credentialResult }}</p>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'

const loading = reactive({ logs: false, threats: false, credentials: false })
const error = ref('')

const logInput = ref('INFO Login ok\nWARN failed login user=demo\nSELECT * FROM users')
const eventsInput = ref('api:3\nwebsite:1')
const credentialInput = ref('token-prod-1,token-prod-2')

const logResult = ref<string | null>(null)
const threatResult = ref<string | null>(null)
const credentialResult = ref<string | null>(null)
const csv = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const runLogs = async () => {
  error.value = ''
  loading.logs = true
  try {
    const out = await workspaceTools.runThalosLogMonitor({
      logs: logInput.value.split('\n').filter(Boolean),
    })
    logResult.value = String((out as any)?.text || 'Monitorización de logs completada.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.logs = false
  }
}

const runThreats = async () => {
  error.value = ''
  loading.threats = true
  try {
    const events = eventsInput.value
      .split('\n')
      .map((row) => row.trim())
      .filter(Boolean)
      .map((row) => {
        const [source, severity] = row.split(':')
        return { source, severity: Number(severity) || 1 }
      })
    const out = await workspaceTools.runThalosThreatDetector({ events })
    threatResult.value = String((out as any)?.text || 'Detección de amenazas completada.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.threats = false
  }
}

const runCredentials = async () => {
  error.value = ''
  loading.credentials = true
  try {
    const out = await workspaceTools.runThalosCredentialRevoker({
      credential_ids: csv(credentialInput.value),
    })
    credentialResult.value = String((out as any)?.text || 'Credenciales revocadas.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.credentials = false
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
.tool-card textarea,
.tool-card input {
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
</style>

