<template>
  <section class="tools-panel">
    <header>
      <h4>🧾 Automatizaciones fiscales</h4>
      <p>Escaneo físico real → CRM, factura y cashflow. Sin simulaciones.</p>
      <router-link to="/scan" class="scan-link">Abrir hub de escaneo completo →</router-link>
    </header>

    <nav class="scan-tabs">
      <button type="button" :class="{ active: tab === 'qr' }" @click="tab = 'qr'">Cámara QR</button>
      <button type="button" :class="{ active: tab === 'nfc' }" @click="tab = 'nfc'">NFC</button>
      <button type="button" :class="{ active: tab === 'dni' }" @click="tab = 'dni'">DNI / MRZ</button>
    </nav>

    <div class="scan-panel">
      <ScannerQR v-if="tab === 'qr'" @scanned="onScanResult" @error="onScanError" />
      <RafaelScannerNFC v-else-if="tab === 'nfc'" @scanned="onScanResult" @error="onScanError" />
      <ParserDNI v-else @parsed="onScanResult" @error="onScanError" />
    </div>

    <p v-if="lastMessage" class="tool-success">{{ lastMessage }}</p>
    <pre v-if="lastPayload" class="tool-detail">{{ formatPayload(lastPayload) }}</pre>

    <div class="forms-section">
      <h5>Modelo 303 (Excel real)</h5>
      <div class="forms-row">
        <input type="number" v-model.number="forms.year" placeholder="Año" />
        <input type="number" v-model.number="forms.quarter" min="1" max="4" placeholder="Trimestre (1-4)" />
        <button :disabled="loading.forms" @click="runForms">Generar Excel 303</button>
      </div>
      <p v-if="formsResult" class="tool-text">{{ formsResult }}</p>
      <a v-if="formsFileUrl" class="download-link" :href="formsFileUrl" target="_blank" rel="noopener">Descargar archivo</a>
    </div>

    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { API_BASE_URL } from '@/config/index'
import { workspaceTools } from '@/api/workspaceTools'
import ScannerQR from '@/components/scan/ScannerQR.vue'
import RafaelScannerNFC from '@/components/scan/RafaelScannerNFC.vue'
import ParserDNI from '@/components/scan/ParserDNI.vue'

const tab = ref<'qr' | 'nfc' | 'dni'>('qr')
const loading = reactive({ forms: false })
const error = ref('')
const lastMessage = ref('')
const lastPayload = ref<Record<string, unknown> | null>(null)

const now = new Date()
const forms = reactive({
  year: now.getFullYear(),
  quarter: Math.floor(now.getMonth() / 3) + 1,
})
const formsResult = ref<string | null>(null)
const formsFileUrl = ref<string | null>(null)

function formatPayload(payload: Record<string, unknown>) {
  return JSON.stringify(payload, null, 2)
}

function onScanResult(result: Record<string, unknown>) {
  error.value = ''
  lastPayload.value = result
  lastMessage.value = String(result.message || 'Operación completada')
  if (result.invoice_id) {
    lastMessage.value += ` · Factura #${result.invoice_id}`
  }
  if (result.customer_id) {
    lastMessage.value += ` · Cliente #${result.customer_id}`
  }
  if (result.needs_approval) {
    lastMessage.value += ` · Pendiente aprobación #${result.approval_id}`
  }
}

function onScanError(msg: string) {
  error.value = msg
  lastMessage.value = ''
}

const runForms = async () => {
  error.value = ''
  loading.forms = true
  formsFileUrl.value = null
  try {
    const out = await workspaceTools.runRafaelForms({ ...forms })
    formsResult.value = String((out as any)?.text || 'Modelo 303 generado.')
    const url = (out as any)?.file_url || (out as any)?.result?.file_url
    if (url) {
      formsFileUrl.value = url.startsWith('http') ? url : `${API_BASE_URL}${url}`
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.forms = false
  }
}
</script>

<style scoped>
/* El unico acento de la vista ya vive en la cabecera del modal --
   aqui todo queda en tokens neutros (antes: fondo/borde ambar en el
   panel, tabs y boton "Generar Excel 303" ambar solido, recuadro de
   escaneo en navy solido -- este ultimo es propio de este archivo, no
   viene de ScanHub.vue/los componentes de escaneo compartidos, que ya
   se corrigieron aparte). */
.tools-panel {
  margin-top: 28px;
  padding: 24px;
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-lg, 18px);
  background: var(--zeus-surface, #fff);
}

header p { margin: 4px 0 0; color: var(--zeus-text-secondary, #52607a); font-size: 14px; }
.scan-link {
  display: inline-block;
  margin-top: 8px;
  color: var(--zeus-accent, #4f46e5);
  font-weight: 600;
  font-size: 13px;
  text-decoration: none;
}

.scan-tabs {
  display: flex;
  gap: 8px;
  margin: 16px 0 12px;
  flex-wrap: wrap;
}
.scan-tabs button {
  border: 1px solid #D1D5DB;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  border-radius: var(--zeus-radius-full, 999px);
  padding: 6px 14px;
  cursor: pointer;
  font-weight: var(--zeus-weight-medium, 500);
  font-size: 13px;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.scan-tabs button:hover {
  border-color: #9aa2af;
}
.scan-tabs button.active {
  font-weight: var(--zeus-weight-bold, 700);
  border-color: var(--zeus-border-strong, #cdd3db);
}

.scan-panel {
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius, 14px);
  padding: 12px;
  background: var(--zeus-surface, #fff);
  margin-bottom: 14px;
}

.tool-success {
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--zeus-success-soft, #e9faf3);
  color: #065f46;
  font-size: 13px;
  font-weight: 600;
}
.tool-detail {
  margin: 0 0 14px;
  padding: 10px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--zeus-bg-subtle, #eef1f6);
  color: var(--zeus-text, #0f172a);
  font-size: 11px;
  overflow: auto;
  max-height: 180px;
}

.forms-section {
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px dashed var(--zeus-border, #e1e5eb);
}
.forms-section h5 { margin: 0 0 8px; color: var(--zeus-text, #0f172a); }
.forms-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.forms-row input {
  border: 1px solid var(--zeus-border-strong, #cdd3db);
  border-radius: var(--zeus-radius-sm, 8px);
  padding: 8px;
  font-size: 13px;
  width: 100px;
  color: var(--zeus-text, #0f172a);
  background: var(--zeus-surface, #fff);
}
.forms-row button {
  border: 1px solid #D1D5DB;
  border-radius: var(--zeus-radius-sm, 8px);
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  padding: 8px 12px;
  cursor: pointer;
  font-weight: var(--zeus-weight-medium, 500);
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.forms-row button:hover:not(:disabled) {
  border-color: #9aa2af;
}

.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--zeus-bg-subtle, #eef1f6);
  color: var(--zeus-text, #0f172a);
  font-size: 13px;
}
.tool-error { margin-top: 12px; color: var(--zeus-danger, #ef4444); }
.download-link {
  display: inline-block;
  margin-top: 8px;
  color: var(--zeus-accent, #4f46e5);
  font-weight: 600;
  font-size: 13px;
}
</style>
