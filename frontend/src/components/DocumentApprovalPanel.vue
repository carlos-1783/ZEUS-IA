<template>
  <div class="document-approval-panel">
    <div class="panel-header">
      <h3>📋 Documentos Pendientes de Aprobación</h3>
      <button @click="loadPendingDocuments" :disabled="loading" class="btn-refresh">
        {{ loading ? 'Cargando...' : '🔄 Actualizar' }}
      </button>
    </div>

    <div v-if="error" class="error-message">
      ⚠️ {{ error }}
    </div>

    <div v-if="loading && documents.length === 0" class="loading">
      Cargando documentos...
    </div>

    <div v-else-if="documents.length === 0" class="empty-state">
      <p>✅ No hay documentos pendientes de aprobación</p>
    </div>

    <div v-else class="documents-list">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="document-card"
        :class="{ 'expanded': expandedDoc === doc.id }"
      >
        <div class="document-header" @click="toggleExpand(doc.id)">
          <div class="document-info">
            <span class="agent-badge" :class="doc.agent_name.toLowerCase()">
              {{ doc.agent_name }}
            </span>
            <span class="document-type">{{ doc.document_type }}</span>
            <span class="document-date">
              {{ formatDate(doc.created_at) }}
            </span>
          </div>
          <div class="document-actions">
            <span class="status-badge" :class="doc.status">
              {{ getStatusLabel(doc.status) }}
            </span>
            <span class="expand-icon">{{ expandedDoc === doc.id ? '▼' : '▶' }}</span>
          </div>
        </div>

        <div v-if="expandedDoc === doc.id" class="document-details">
          <div class="document-content">
            <h4>Contenido del Documento:</h4>
            <pre class="document-preview">{{ formatDocumentContent(doc.document_payload) }}</pre>
          </div>

          <div v-if="doc.advisor_email" class="advisor-info">
            <strong>Asesor:</strong> {{ doc.advisor_email }}
          </div>

          <div v-else class="advisor-warning">
            ⚠️ Falta email de asesor. Configúralo en tu perfil.
          </div>

          <div class="approval-actions">
            <button
              @click="approveDocument(doc)"
              :disabled="approving || !doc.advisor_email"
              class="btn-approve"
            >
              {{ getApprovalButtonLabel(doc.agent_name) }}
            </button>
            <button
              @click="rejectDocument(doc)"
              :disabled="approving"
              class="btn-reject"
            >
              Rechazar
            </button>
          </div>

          <div v-if="doc.audit_log && doc.audit_log.length > 0" class="audit-log">
            <h4>Historial:</h4>
            <ul>
              <li v-for="(log, idx) in doc.audit_log" :key="idx">
                <strong>{{ log.event }}</strong> - {{ formatDate(log.timestamp) }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

interface Document {
  id: number
  user_id: number
  agent_name: string
  document_type: string
  document_payload: any
  status: string
  advisor_email?: string
  created_at: string
  approved_at?: string
  sent_at?: string
  audit_log: any[]
}

const documents = ref<Document[]>([])
const loading = ref(false)
const approving = ref(false)
const error = ref('')
const expandedDoc = ref<number | null>(null)

const loadPendingDocuments = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get('/documents/pending')
    if (response.data.success) {
      documents.value = response.data.pending_documents || []
    } else {
      error.value = response.data.message || 'Error cargando documentos'
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Error al cargar documentos pendientes'
    console.error('Error loading pending documents:', err)
  } finally {
    loading.value = false
  }
}

const approveDocument = async (doc: Document) => {
  if (!doc.advisor_email) {
    error.value = 'Falta email de asesor. Configúralo en tu perfil.'
    return
  }

  approving.value = true
  error.value = ''
  try {
    const response = await api.post('/documents/approve', {
      document_id: doc.id.toString(),
      agent_name: doc.agent_name,
      document_content: doc.document_payload?.content || doc.document_payload,
      advisor_email: doc.advisor_email
    })

    if (response.data.success) {
      // Recargar documentos
      await loadPendingDocuments()
      expandedDoc.value = null
      alert('✅ Documento aprobado y enviado al asesor exitosamente')
    } else {
      error.value = response.data.message || 'Error al aprobar documento'
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Error al aprobar documento'
    console.error('Error approving document:', err)
  } finally {
    approving.value = false
  }
}

const rejectDocument = async (doc: Document) => {
  if (!confirm('¿Estás seguro de rechazar este documento?')) {
    return
  }

  // Por ahora solo removemos de la lista visualmente
  // En el futuro se podría implementar un endpoint para rechazar
  documents.value = documents.value.filter(d => d.id !== doc.id)
  alert('Documento rechazado')
}

const toggleExpand = (docId: number) => {
  expandedDoc.value = expandedDoc.value === docId ? null : docId
}

const formatDate = (dateString: string) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString('es-ES', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDocumentContent = (payload: any) => {
  if (!payload) return 'Sin contenido'
  if (typeof payload === 'string') {
    try {
      return JSON.stringify(JSON.parse(payload), null, 2)
    } catch {
      return payload
    }
  }
  if (payload.content) {
    return typeof payload.content === 'string' 
      ? payload.content 
      : JSON.stringify(payload.content, null, 2)
  }
  return JSON.stringify(payload, null, 2)
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: 'Borrador',
    pending_approval: 'Pendiente',
    approved: 'Aprobado',
    rejected: 'Rechazado',
    sent_to_advisor: 'Enviado',
    failed: 'Error'
  }
  return labels[status] || status
}

const getApprovalButtonLabel = (agentName: string) => {
  if (agentName === 'RAFAEL') {
    return '✅ Aprobar y Enviar al Asesor Fiscal'
  } else if (agentName === 'JUSTICIA') {
    return '✅ Aprobar y Enviar al Abogado'
  }
  return '✅ Aprobar y Enviar al Asesor'
}

onMounted(() => {
  loadPendingDocuments()
})
</script>

<style scoped>
.document-approval-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #e5e7eb;
}

.panel-header h3 {
  margin: 0;
  color: #1f2937;
}

.btn-refresh {
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-refresh:hover:not(:disabled) {
  background: #2563eb;
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  background: #fef2f2;
  color: #dc2626;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  border-left: 4px solid #dc2626;
}

.loading, .empty-state {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.documents-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.document-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.document-card:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.document-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  cursor: pointer;
  background: #f9fafb;
}

.document-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.agent-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.agent-badge.rafael {
  background: #dbeafe;
  color: #1e40af;
}

.agent-badge.justicia {
  background: #fce7f3;
  color: #9f1239;
}

.document-type {
  font-weight: 500;
  color: #374151;
}

.document-date {
  font-size: 12px;
  color: #6b7280;
}

.document-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.status-badge.draft,
.status-badge.pending_approval {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.approved,
.status-badge.sent_to_advisor {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.rejected,
.status-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.expand-icon {
  color: #6b7280;
  font-size: 12px;
}

.document-details {
  padding: 20px;
  background: white;
  border-top: 1px solid #e5e7eb;
}

.document-content {
  margin-bottom: 20px;
}

.document-content h4 {
  margin: 0 0 12px 0;
  color: #374151;
  font-size: 14px;
}

.document-preview {
  background: #f9fafb;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.advisor-info {
  padding: 12px;
  background: #eff6ff;
  border-radius: 6px;
  margin-bottom: 16px;
  color: #1e40af;
}

.advisor-warning {
  padding: 12px;
  background: #fef3c7;
  border-radius: 6px;
  margin-bottom: 16px;
  color: #92400e;
}

.approval-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.btn-approve {
  flex: 1;
  padding: 12px 24px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-approve:hover:not(:disabled) {
  background: #059669;
}

.btn-approve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-reject {
  padding: 12px 24px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-reject:hover:not(:disabled) {
  background: #dc2626;
}

.btn-reject:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.audit-log {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.audit-log h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #6b7280;
}

.audit-log ul {
  margin: 0;
  padding-left: 20px;
  list-style: disc;
}

.audit-log li {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
</style>

