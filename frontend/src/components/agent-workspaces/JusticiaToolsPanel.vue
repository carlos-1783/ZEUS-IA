<template>
  <section class="tools-panel">
    <header>
      <h4>⚖️ Toolkit Legal</h4>
      <p>Genera contratos, firmas y auditorías GDPR sin salir del panel.</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card">
        <h5>Firma digital</h5>
        <input v-model="signerForm.document_name" placeholder="Nombre documento.pdf" />
        <input v-model="signerForm.file_hash" placeholder="Hash SHA-256" />
        <input v-model="signerForm.signer" placeholder="Firmante" />
        <button :disabled="loading.signer" @click="runSigner">
          {{ loading.signer ? 'Firmando…' : 'Firmar' }}
        </button>
        <pre v-if="signerResult">{{ formatJson(signerResult) }}</pre>
      </div>

      <div class="tool-card">
        <h5>Generador de contrato</h5>
        <input v-model="contractForm.scope" placeholder="Alcance" />
        <textarea v-model="contractForm.parties" placeholder="Parte A, Parte B"></textarea>
        <label><input type="checkbox" v-model="contractForm.media_buying" /> Incluye cláusula media buying</label>
        <button :disabled="loading.contract" @click="runContract">
          {{ loading.contract ? 'Generando…' : 'Generar' }}
        </button>
        <pre v-if="contractResult">{{ formatJson(contractResult) }}</pre>
      </div>

      <div class="tool-card">
        <h5>Auditoría GDPR</h5>
        <textarea v-model="gdprForm.systems" placeholder="Sistemas (coma)"></textarea>
        <textarea v-model="gdprForm.data_flows" placeholder="Flujos de datos (coma)"></textarea>
        <button :disabled="loading.gdpr" @click="runGdpr">
          {{ loading.gdpr ? 'Auditando…' : 'Auditar' }}
        </button>
        <pre v-if="gdprResult">{{ formatJson(gdprResult) }}</pre>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'

const loading = reactive({ signer: false, contract: false, gdpr: false })
const error = ref('')

const signerForm = reactive({
  document_name: 'contrato.pdf',
  file_hash: 'abcd1234',
  signer: 'JUSTICIA',
})
const contractForm = reactive({
  scope: 'campaña publicitaria',
  parties: 'ZEUS IA, Cliente Demo',
  media_buying: true,
})
const gdprForm = reactive({
  systems: 'CRM,WhatsApp',
  data_flows: 'Leads->CRM,CRM->Email',
})

const signerResult = ref<any | null>(null)
const contractResult = ref<any | null>(null)
const gdprResult = ref<any | null>(null)

const formatJson = (value: unknown) => JSON.stringify(value, null, 2)
const csv = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const runSigner = async () => {
  error.value = ''
  loading.signer = true
  try {
    signerResult.value = await workspaceTools.runJusticiaSigner({ ...signerForm })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.signer = false
  }
}

const runContract = async () => {
  error.value = ''
  loading.contract = true
  try {
    contractResult.value = await workspaceTools.runJusticiaContract({
      scope: contractForm.scope,
      media_buying: contractForm.media_buying,
      parties: csv(contractForm.parties),
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.contract = false
  }
}

const runGdpr = async () => {
  error.value = ''
  loading.gdpr = true
  try {
    gdprResult.value = await workspaceTools.runJusticiaGdpr({
      systems: csv(gdprForm.systems),
      data_flows: csv(gdprForm.data_flows),
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.gdpr = false
  }
}
</script>

<style scoped>
.tools-panel {
  margin-top: 24px;
  padding: 20px;
  border: 1px solid rgba(71, 85, 105, 0.25);
  border-radius: 16px;
  background: #ffffff;
}
.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.tool-card {
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tool-card input,
.tool-card textarea {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
}
.tool-card button {
  border: none;
  background: #0f172a;
  color: #fff;
  border-radius: 8px;
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

