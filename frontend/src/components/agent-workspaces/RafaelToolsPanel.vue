<template>
  <section class="tools-panel">
    <header>
      <h4>🧾 Automatizaciones fiscales</h4>
      <p>Procesa entradas comunes de RAFAEL desde un único lugar.</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card">
        <h5>Lectura QR</h5>
        <textarea v-model="qrData" placeholder="ZEUS|Cliente|100|EUR"></textarea>
        <button :disabled="loading.qr" @click="runQr">Leer QR</button>
        <pre v-if="qrResult">{{ formatJson(qrResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Lectura NFC</h5>
        <input v-model="nfcHex" placeholder="Payload HEX" />
        <button :disabled="loading.nfc" @click="runNfc">Escanear</button>
        <pre v-if="nfcResult">{{ formatJson(nfcResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Parser DNIe (MRZ)</h5>
        <textarea v-model="mrz" placeholder="2 líneas MRZ"></textarea>
        <button :disabled="loading.mrz" @click="runMrz">Parsear</button>
        <pre v-if="mrzResult">{{ formatJson(mrzResult) }}</pre>
      </div>
      <div class="tool-card">
        <h5>Modelos 303/390</h5>
        <input type="number" v-model.number="forms.revenue" placeholder="Ingresos trimestre" />
        <input type="number" v-model.number="forms.expenses" placeholder="Gastos trimestre" />
        <input type="number" v-model.number="forms.iva_type" placeholder="IVA %" />
        <button :disabled="loading.forms" @click="runForms">Generar</button>
        <pre v-if="formsResult">{{ formatJson(formsResult) }}</pre>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'

const loading = reactive({ qr: false, nfc: false, mrz: false, forms: false })
const error = ref('')

const qrData = ref('ZEUS|Cliente Demo|1200|EUR')
const nfcHex = ref('5a4555535f4941')
const mrz = ref('IDESP0000000000<<<<<<<<<<<<<<<\n8001010M2501013ESP<<<<<<<<<<<')
const forms = reactive({ revenue: 2500, expenses: 400, iva_type: 21 })

const qrResult = ref<any | null>(null)
const nfcResult = ref<any | null>(null)
const mrzResult = ref<any | null>(null)
const formsResult = ref<any | null>(null)

const formatJson = (value: unknown) => JSON.stringify(value, null, 2)

const runQr = async () => {
  error.value = ''
  loading.qr = true
  try {
    qrResult.value = await workspaceTools.runRafaelQrReader({ data: qrData.value })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.qr = false
  }
}

const runNfc = async () => {
  error.value = ''
  loading.nfc = true
  try {
    nfcResult.value = await workspaceTools.runRafaelNfcScanner({ payload_hex: nfcHex.value })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.nfc = false
  }
}

const runMrz = async () => {
  error.value = ''
  loading.mrz = true
  try {
    mrzResult.value = await workspaceTools.runRafaelDniParser({ mrz: mrz.value })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.mrz = false
  }
}

const runForms = async () => {
  error.value = ''
  loading.forms = true
  try {
    formsResult.value = await workspaceTools.runRafaelForms({ ...forms })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.forms = false
  }
}
</script>

<style scoped>
.tools-panel {
  margin-top: 28px;
  padding: 24px;
  border: 1px solid rgba(248, 196, 113, 0.4);
  border-radius: 18px;
  background: #fffaf4;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.tool-card {
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #fff;
}

.tool-card textarea,
.tool-card input {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
}

.tool-card button {
  border: none;
  border-radius: 8px;
  background: #d97706;
  color: white;
  padding: 6px 10px;
  cursor: pointer;
}

.tool-card pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 8px;
  border-radius: 8px;
  font-size: 12px;
  max-height: 140px;
  overflow: auto;
}

.tool-error {
  margin-top: 12px;
  color: #991b1b;
}
</style>

