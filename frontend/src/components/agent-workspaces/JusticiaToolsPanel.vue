<template>
  <section class="tools-panel">
    <header>
      <div class="header-row">
        <div>
          <h4>⚖️ Toolkit Legal</h4>
          <p>Auditoría de sistema (read-only) y herramientas documentales etiquetadas.</p>
        </div>
        <ThalosExecutionBadge
          v-if="globalStatus"
          :global-mode="globalStatus.system_default_mode"
          :control="globalStatus.justicia_control"
          :real-execution="globalStatus.real_execution"
        />
      </div>
      <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
    </header>

    <div class="audit-card highlight">
      <div class="card-title-row">
        <h5>Auditoría de sistema</h5>
        <ThalosExecutionBadge
          :module-badge="auditBadge"
          :inline="true"
          :show-global="false"
        />
      </div>
      <p class="hint">justice_deep_audit_v1 — consulta tablas reales (RRHH, OPS, workspace).</p>
      <button :disabled="loading.audit" @click="runSystemAudit">
        {{ loading.audit ? 'Auditando…' : 'Ejecutar auditoría' }}
      </button>
      <p v-if="auditSummary" class="tool-text">{{ auditSummary }}</p>
      <ul v-if="auditConclusions.length" class="audit-list">
        <li v-for="(c, i) in auditConclusions.slice(0, 10)" :key="i">
          <strong>{{ c.domain }}</strong> · {{ c.check }} —
          <span :class="c.status.toLowerCase()">{{ c.status }}</span>
          <em>({{ c.evidence_source }})</em>
        </li>
      </ul>
    </div>

    <div class="tools-grid">
      <div class="tool-card legacy">
        <div class="card-title-row">
          <h5>Firma digital</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <input v-model="signerForm.document_name" placeholder="Nombre documento.pdf" />
        <input v-model="signerForm.file_hash" placeholder="Hash SHA-256" />
        <button :disabled="loading.signer" @click="runSigner">
          {{ loading.signer ? 'Firmando…' : 'Firmar (stub)' }}
        </button>
        <p v-if="signerResult" class="tool-text">{{ signerResult }}</p>
      </div>

      <div class="tool-card legacy">
        <div class="card-title-row">
          <h5>Generador de contrato</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <input v-model="contractForm.scope" placeholder="Alcance" />
        <textarea v-model="contractForm.parties" placeholder="Parte A, Parte B"></textarea>
        <button :disabled="loading.contract" @click="runContract">
          {{ loading.contract ? 'Generando…' : 'Generar borrador' }}
        </button>
        <p v-if="contractResult" class="tool-text">{{ contractResult }}</p>
      </div>

      <div class="tool-card legacy">
        <div class="card-title-row">
          <h5>Auditoría GDPR (descriptiva)</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <textarea v-model="gdprForm.systems" placeholder="Sistemas (coma)"></textarea>
        <button :disabled="loading.gdpr" @click="runGdpr">
          {{ loading.gdpr ? 'Auditando…' : 'Auditar (LLM/stub)' }}
        </button>
        <p v-if="gdprResult" class="tool-text">{{ gdprResult }}</p>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'
import {
  fetchJusticiaStatus,
  fetchJusticiaSystemAudit,
  type AuditConclusion,
  type JusticiaStatusResponse,
} from '@/api/justicia_workspace_api'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

const loading = reactive({ signer: false, contract: false, gdpr: false, audit: false })
const error = ref('')
const statusNote = ref('')
const globalStatus = ref<JusticiaStatusResponse | null>(null)
const auditSummary = ref<string | null>(null)
const auditConclusions = ref<AuditConclusion[]>([])

const auditBadge = computed(() =>
  globalStatus.value?.JUSTICE_REAL_AUDIT_ENABLED ? 'REAL' : 'SIMULADO'
)

const signerForm = reactive({
  document_name: '',
  file_hash: '',
  signer: 'JUSTICIA',
})
const contractForm = reactive({ scope: '', parties: '', media_buying: false })
const gdprForm = reactive({ systems: '', data_flows: '' })

const signerResult = ref<string | null>(null)
const contractResult = ref<string | null>(null)
const gdprResult = ref<string | null>(null)

const csv = (value: string) =>
  value.split(',').map((item) => item.trim()).filter(Boolean)

onMounted(async () => {
  try {
    globalStatus.value = await fetchJusticiaStatus()
    statusNote.value = globalStatus.value.JUSTICE_REAL_AUDIT_ENABLED
      ? 'Auditoría real activa: conclusions con evidence_source DB/API.'
      : 'Modo descriptivo: activa JUSTICE_REAL_AUDIT_ENABLED en Railway para queries BD.'
  } catch {
    /* optional */
  }
})

const runSystemAudit = async () => {
  error.value = ''
  loading.audit = true
  auditSummary.value = null
  auditConclusions.value = []
  try {
    const out = await fetchJusticiaSystemAudit()
    auditSummary.value = out.summary
    auditConclusions.value = out.conclusions || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.audit = false
  }
}

const runSigner = async () => {
  error.value = ''
  loading.signer = true
  try {
    const out = await workspaceTools.runJusticiaSigner({ ...signerForm })
    signerResult.value = String((out as { text?: string }).text || 'Stub — sin firma legal real.')
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
    const out = await workspaceTools.runJusticiaContract({
      scope: contractForm.scope,
      media_buying: contractForm.media_buying,
      parties: csv(contractForm.parties),
    })
    contractResult.value = String((out as { text?: string }).text || 'Borrador simulado.')
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
    const out = await workspaceTools.runJusticiaGdpr({
      systems: csv(gdprForm.systems),
      data_flows: csv(gdprForm.data_flows),
    })
    gdprResult.value = String((out as { text?: string }).text || 'Auditoría descriptiva (sin BD).')
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
}
.audit-card {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid rgba(15, 23, 42, 0.2);
  border-radius: 12px;
}
.audit-card.highlight {
  border-color: #0f172a;
  background: #f8fafc;
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
.tool-card.legacy { opacity: 0.92; }
.hint { margin: 0; font-size: 12px; color: #64748b; }
.status-note { margin-top: 8px; font-size: 12px; color: #475569; }
.tool-card input,
.tool-card textarea {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
}
.tool-card button,
.audit-card button {
  border: none;
  background: #0f172a;
  color: #fff;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
}
.audit-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
}
.audit-list .pass { color: #15803d; }
.audit-list .gap { color: #b45309; }
.audit-list .warn { color: #b45309; }
.audit-list .fail { color: #b91c1c; }
.audit-list em { color: #64748b; font-style: normal; }
.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 13px;
}
.tool-error { margin-top: 10px; color: #b91c1c; }
</style>
