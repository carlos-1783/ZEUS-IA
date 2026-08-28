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

    <TeamFlowPanel agent="JUSTICIA" />

    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchJusticiaComplianceEvents,
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

const legalDocCount = ref(0)

const csv = (value: string) =>
  value.split(',').map((item) => item.trim()).filter(Boolean)

onMounted(async () => {
  try {
    globalStatus.value = await fetchJusticiaStatus()
    const docs = await fetchJusticiaDocuments().catch(() => null)
    legalDocCount.value = docs?.count ?? docs?.documents?.length ?? 0
    const events = await fetchJusticiaComplianceEvents().catch(() => null)
    complianceAlerts.value = events?.events || []
    statusNote.value = globalStatus.value.JUSTICE_REAL_AUDIT_ENABLED
      ? `Modo REAL · ${legalDocCount.value} documentos legales · ${complianceAlerts.value.length} alertas compliance`
      : 'Activa JUSTICE_REAL_AUDIT_ENABLED en Railway.'
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
/* El unico acento de la vista ya vive en la cabecera del modal --
   aqui todo queda en tokens neutros (antes: botones negro/azul marino
   solido, tarjeta de auditoria con borde negro). */
.tools-panel {
  margin-top: 24px;
  padding: 20px;
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-lg, 16px);
  background: var(--zeus-surface, #fff);
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
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius, 12px);
  background: var(--zeus-bg-subtle, #eef1f6);
}
.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.tool-card {
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius, 12px);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--zeus-surface, #fff);
}
.hint { margin: 0; font-size: 12px; color: var(--zeus-text-secondary, #52607a); }
.status-note { margin-top: 8px; font-size: 12px; color: var(--zeus-text-secondary, #52607a); }
.tool-card input,
.tool-card textarea {
  border: 1px solid var(--zeus-border-strong, #cdd3db);
  border-radius: var(--zeus-radius-sm, 8px);
  padding: 8px;
  font-size: 13px;
  color: var(--zeus-text, #0f172a);
  background: var(--zeus-surface, #fff);
}
.tool-card button,
.audit-card button {
  border: 1px solid #D1D5DB;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  border-radius: var(--zeus-radius-sm, 8px);
  padding: 8px 10px;
  cursor: pointer;
  font-weight: var(--zeus-weight-medium, 500);
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.tool-card button:hover:not(:disabled),
.audit-card button:hover:not(:disabled) {
  border-color: #9aa2af;
}
.audit-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
}
.audit-list .pass { color: var(--zeus-success, #10b981); }
.audit-list .gap { color: var(--zeus-warning, #f59e0b); }
.audit-list .warn { color: var(--zeus-warning, #f59e0b); }
.audit-list .fail { color: var(--zeus-danger, #ef4444); }
.audit-list em { color: var(--zeus-text-muted, #8792a6); font-style: normal; }
.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--zeus-bg-subtle, #eef1f6);
  color: var(--zeus-text, #0f172a);
  font-size: 13px;
}
.tool-error { margin-top: 10px; color: var(--zeus-danger, #ef4444); }
</style>
