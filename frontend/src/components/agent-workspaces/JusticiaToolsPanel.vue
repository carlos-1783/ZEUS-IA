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
      <div class="tool-card" :class="{ real: moduleBadge('pdf_signer') === 'REAL' }">
        <div class="card-title-row">
          <h5>Firma digital</h5>
          <ThalosExecutionBadge :module-badge="moduleBadge('pdf_signer')" :inline="true" :show-global="false" />
        </div>
        <input v-model="signerForm.document_name" placeholder="Nombre documento.pdf" />
        <input v-model="signerForm.file_hash" placeholder="Hash SHA-256 (opcional)" />
        <button :disabled="loading.signer" @click="runSigner">
          {{ loading.signer ? 'Firmando…' : 'Firmar y persistir' }}
        </button>
        <p v-if="signerResult" class="tool-text">{{ signerResult }}</p>
      </div>

      <div class="tool-card" :class="{ real: moduleBadge('contract_generator') === 'REAL' }">
        <div class="card-title-row">
          <h5>Generador de contrato</h5>
          <ThalosExecutionBadge :module-badge="moduleBadge('contract_generator')" :inline="true" :show-global="false" />
        </div>
        <input v-model="contractForm.scope" placeholder="Alcance" />
        <textarea v-model="contractForm.parties" placeholder="Parte A, Parte B"></textarea>
        <button :disabled="loading.contract" @click="runContract">
          {{ loading.contract ? 'Generando…' : 'Generar borrador' }}
        </button>
        <p v-if="contractResult" class="tool-text">{{ contractResult }}</p>
      </div>

      <div class="tool-card" :class="{ real: moduleBadge('gdpr_audit') === 'REAL' }">
        <div class="card-title-row">
          <h5>Auditoría GDPR</h5>
          <ThalosExecutionBadge :module-badge="moduleBadge('gdpr_audit')" :inline="true" :show-global="false" />
        </div>
        <textarea v-model="gdprForm.systems" placeholder="Sistemas (coma)"></textarea>
        <button :disabled="loading.gdpr" @click="runGdpr">
          {{ loading.gdpr ? 'Auditando…' : 'Auditar RGPD (BD)' }}
        </button>
        <p v-if="gdprResult" class="tool-text">{{ gdprResult }}</p>
        <ul v-if="complianceAlerts.length" class="audit-list">
          <li v-for="(a, i) in complianceAlerts.slice(0, 5)" :key="i">
            <strong>{{ a.source }}</strong> · {{ a.event_type }} — {{ a.severity }}
          </li>
        </ul>
      </div>
    </div>

    <section v-if="legalDocuments.length" class="legal-docs-section">
      <h5>Documentos legales en BD ({{ legalDocuments.length }})</h5>
      <ul class="legal-doc-list">
        <li
          v-for="doc in legalDocuments"
          :key="String(doc.id)"
          :class="{ active: selectedLegalId === doc.id }"
          @click="selectLegalDoc(doc)"
        >
          <strong>{{ doc.type }}</strong> · {{ doc.status }}
          <span class="doc-id">{{ doc.id }}</span>
        </li>
      </ul>
      <ZeusDocumentRenderer v-if="legalDocPayload" :doc="legalDocPayload" />
    </section>

    <TeamFlowPanel agent="JUSTICIA" />

    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchJusticiaComplianceEvents,
  fetchJusticiaDocumentDetail,
  fetchJusticiaDocuments,
  fetchJusticiaStatus,
  fetchJusticiaSystemAudit,
  justiciaGenerateContract,
  justiciaGdprCheck,
  justiciaSign,
  type AuditConclusion,
  type JusticiaStatusResponse,
} from '@/api/justicia_workspace_api'
import { resolveJusticiaModuleBadge } from '@/utils/zeus_safe_lock'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'
import ZeusDocumentRenderer from '@/components/documents/ZeusDocumentRenderer.vue'
import TeamFlowPanel from './TeamFlowPanel.vue'

const loading = reactive({ signer: false, contract: false, gdpr: false, audit: false })
const error = ref('')
const statusNote = ref('')
const globalStatus = ref<JusticiaStatusResponse | null>(null)
const auditSummary = ref<string | null>(null)
const auditConclusions = ref<AuditConclusion[]>([])

const auditBadge = computed(() => resolveJusticiaModuleBadge('system_audit', globalStatus.value))

const moduleBadge = (key: string) => resolveJusticiaModuleBadge(key, globalStatus.value)

const complianceAlerts = ref<Array<Record<string, unknown>>>([])

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

const legalDocuments = ref<Array<Record<string, unknown>>>([])
const selectedLegalId = ref<string | null>(null)
const legalDocPayload = ref<Record<string, unknown> | null>(null)

const loadLegalDocuments = async () => {
  const docs = await fetchJusticiaDocuments().catch(() => null)
  legalDocuments.value = docs?.documents || []
  if (legalDocuments.value.length && !selectedLegalId.value) {
    await selectLegalDoc(legalDocuments.value[0])
  }
}

const selectLegalDoc = async (doc: Record<string, unknown>) => {
  const id = String(doc.id || '')
  selectedLegalId.value = id
  legalDocPayload.value = null
  if (!id) return
  try {
    const detail = (await fetchJusticiaDocumentDetail(id)) as Record<string, unknown>
    legalDocPayload.value = {
      agent_source: 'JUSTICIA',
      type: detail.type || doc.type,
      title: `Documento ${detail.type || doc.type}`,
      content: detail.content ?? detail.content_preview,
      data: detail,
    }
  } catch {
    legalDocPayload.value = {
      agent_source: 'JUSTICIA',
      type: doc.type,
      content: doc,
    }
  }
}

const csv = (value: string) =>
  value.split(',').map((item) => item.trim()).filter(Boolean)

onMounted(async () => {
  try {
    globalStatus.value = await fetchJusticiaStatus()
    await loadLegalDocuments()
    const events = await fetchJusticiaComplianceEvents().catch(() => null)
    complianceAlerts.value = events?.events || []
    statusNote.value = globalStatus.value.JUSTICE_REAL_AUDIT_ENABLED
      ? `Modo REAL · ${legalDocuments.value.length} documentos legales · ${complianceAlerts.value.length} alertas compliance`
      : 'Activa JUSTICE_REAL_AUDIT_ENABLED en Railway.'
  } catch {
    /* optional */
  }
  window.addEventListener('zeus:teamflow-refresh', loadLegalDocuments)
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
    const out = await justiciaSign({ ...signerForm })
    signerResult.value = `Firma: ${(out as { signature?: string }).signature?.slice(0, 16)}… · doc ${(out as { document_id?: string }).document_id}`
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
    const out = await justiciaGenerateContract({
      scope: contractForm.scope,
      media_buying: contractForm.media_buying,
      parties: csv(contractForm.parties),
    })
    contractResult.value = `Contrato v${(out as { version?: number }).version} · ${(out as { document_id?: string }).document_id} · ${(out as { status?: string }).status}`
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
    const out = await justiciaGdprCheck(csv(gdprForm.systems))
    const issues = (out as { issues?: Array<{ message?: string }> }).issues || []
    gdprResult.value = issues.map((i) => i.message).join(' · ') || 'Sin incidencias críticas.'
    const ev = await fetchJusticiaComplianceEvents()
    complianceAlerts.value = ev.events || []
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
.tool-card.real { border-color: #0f172a; }
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
.legal-docs-section {
  margin-top: 20px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.15);
  background: #f8fafc;
}
.legal-doc-list { list-style: none; margin: 0 0 12px; padding: 0; }
.legal-doc-list li {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  margin-bottom: 6px;
  cursor: pointer;
  font-size: 13px;
}
.legal-doc-list li.active { border-color: #0f172a; background: #fff; }
.doc-id { display: block; font-size: 11px; color: #64748b; margin-top: 2px; }
</style>
