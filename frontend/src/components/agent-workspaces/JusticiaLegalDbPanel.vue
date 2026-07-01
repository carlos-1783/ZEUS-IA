<template>
  <section class="legal-db-panel">
    <header class="ldb-header">
      <div>
        <h4>📄 Documentos legales en BD</h4>
        <p class="hint">
          Contratos RRHH (AFRODITA), borradores JUSTICIA y handoffs TeamFlow — datos reales de
          <code>legal_documents</code>.
        </p>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="reload">
        {{ loading ? '…' : 'Actualizar' }}
      </button>
    </header>

    <p v-if="error" class="ldb-error">{{ error }}</p>

    <div v-if="!loading && (documents.length || teamflowItems.length)" class="ldb-body">
      <aside class="ldb-list">
        <h5 v-if="documents.length">Legal ({{ documents.length }})</h5>
        <ul v-if="documents.length">
          <li
            v-for="doc in documents"
            :key="String(doc.id)"
            :class="{ active: selectedKind === 'legal' && selectedLegalId === doc.id }"
            @click="selectLegal(doc)"
          >
            <div class="title">{{ docLabel(doc) }}</div>
            <div class="meta">
              <span class="badge">{{ doc.status }}</span>
              <span>{{ formatDate(doc.created_at as string) }}</span>
            </div>
            <span class="doc-id">{{ doc.id }}</span>
          </li>
        </ul>

        <h5 v-if="teamflowItems.length" class="tf-title">TeamFlow ({{ teamflowItems.length }})</h5>
        <ul v-if="teamflowItems.length">
          <li
            v-for="item in teamflowItems"
            :key="item.id"
            :class="{ active: selectedKind === 'teamflow' && selectedTeamflowId === item.id }"
            @click="selectTeamflow(item)"
          >
            <div class="title">{{ item.title }}</div>
            <div class="meta">
              <span>{{ item.source_agent }} → {{ item.target_agent || '—' }}</span>
              <span class="badge">{{ item.status }}</span>
            </div>
          </li>
        </ul>
      </aside>

      <main class="ldb-detail">
        <ZeusDocumentRenderer v-if="previewDoc" :doc="previewDoc" />
        <p v-else class="ldb-empty-detail">Selecciona un documento o flujo TeamFlow.</p>
      </main>
    </div>

    <p v-else-if="!loading" class="ldb-empty">
      Sin documentos en BD. Crea un contrato en <strong>AFRODITA → RRHH → Crear borrador</strong>.
    </p>
    <p v-if="loading" class="ldb-loading">Cargando documentos legales…</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import {
  fetchJusticiaDocumentDetail,
  fetchJusticiaDocuments,
} from '@/api/justicia_workspace_api'
import { fetchTeamFlowItems, type TeamFlowItem } from '@/api/teamflow_api'
import ZeusDocumentRenderer from '@/components/documents/ZeusDocumentRenderer.vue'

const documents = ref<Array<Record<string, unknown>>>([])
const teamflowItems = ref<TeamFlowItem[]>([])
const selectedKind = ref<'legal' | 'teamflow' | null>(null)
const selectedLegalId = ref<string | null>(null)
const selectedTeamflowId = ref<string | null>(null)
const previewDoc = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const error = ref('')

const formatDate = (iso?: string) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const docLabel = (doc: Record<string, unknown>) => {
  const type = String(doc.type || 'document')
  const owner = String(doc.owner_agent || '')
  if (type === 'contract') return `Contrato laboral${owner ? ` (${owner})` : ''}`
  return type
}

const selectLegal = async (doc: Record<string, unknown>) => {
  const id = String(doc.id || '')
  selectedKind.value = 'legal'
  selectedLegalId.value = id
  selectedTeamflowId.value = null
  previewDoc.value = null
  if (!id) return
  try {
    const detail = (await fetchJusticiaDocumentDetail(id)) as Record<string, unknown>
    previewDoc.value = {
      agent_source: 'JUSTICIA',
      type: detail.type || doc.type,
      title: docLabel(doc),
      content: detail.content ?? detail.content_preview,
      data: detail,
    }
  } catch {
    previewDoc.value = { agent_source: 'JUSTICIA', type: doc.type, content: doc }
  }
}

const selectTeamflow = (item: TeamFlowItem) => {
  selectedKind.value = 'teamflow'
  selectedTeamflowId.value = item.id
  selectedLegalId.value = null
  const c = item.content || {}
  previewDoc.value = {
    agent_source: 'AFRODITA',
    legal_document: c.legal_document,
    employee: { full_name: c.employee_name },
    role: c.role,
    salary: c.salary,
    contract_id: c.document_id,
  }
}

const reload = async () => {
  loading.value = true
  error.value = ''
  try {
    const [docsRes, tfRes] = await Promise.all([
      fetchJusticiaDocuments(),
      fetchTeamFlowItems({ agent: 'JUSTICIA', limit: 30 }),
    ])
    documents.value = docsRes.documents || []
    teamflowItems.value = tfRes.items || []

    if (documents.value.length) {
      const pick =
        documents.value.find((d) => d.type === 'contract') || documents.value[0]
      await selectLegal(pick)
    } else if (teamflowItems.value.length) {
      selectTeamflow(teamflowItems.value[0])
    } else {
      previewDoc.value = null
      selectedKind.value = null
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void reload()
  window.addEventListener('zeus:teamflow-refresh', reload)
  window.addEventListener('zeus:workspace-refresh', reload)
})
onUnmounted(() => {
  window.removeEventListener('zeus:teamflow-refresh', reload)
  window.removeEventListener('zeus:workspace-refresh', reload)
})

defineExpose({ reload })
</script>

<style scoped>
.legal-db-panel {
  margin-bottom: 28px;
  padding: 20px;
  border-radius: 16px;
  border: 2px solid rgba(15, 23, 42, 0.12);
  background: linear-gradient(180deg, #f8fafc 0%, #fff 100%);
}
.ldb-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.ldb-header h4 { margin: 0; font-size: 17px; color: #0f172a; }
.hint { margin: 6px 0 0; font-size: 13px; color: #64748b; }
.hint code { font-size: 12px; background: #e2e8f0; padding: 1px 4px; border-radius: 4px; }
.refresh-btn {
  border: 1px solid #0f172a;
  background: #0f172a;
  color: #fff;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}
.ldb-body {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 20px;
}
.ldb-list h5 { margin: 0 0 8px; font-size: 13px; color: #475569; }
.tf-title { margin-top: 16px; }
.ldb-list ul { list-style: none; margin: 0 0 12px; padding: 0; }
.ldb-list li {
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  margin-bottom: 8px;
  cursor: pointer;
  background: #fff;
}
.ldb-list li.active {
  border-color: #0f172a;
  box-shadow: 0 0 0 1px #0f172a;
}
.ldb-list .title { font-weight: 600; font-size: 13px; }
.ldb-list .meta {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
}
.badge {
  font-weight: 700;
  text-transform: uppercase;
  color: #b45309;
}
.doc-id {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
  word-break: break-all;
}
.ldb-detail {
  min-height: 200px;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.25);
}
.ldb-empty, .ldb-empty-detail, .ldb-loading, .ldb-error {
  font-size: 14px;
  color: #64748b;
  margin: 8px 0;
}
.ldb-error { color: #b91c1c; }
@media (max-width: 800px) {
  .ldb-body { grid-template-columns: 1fr; }
}
</style>
