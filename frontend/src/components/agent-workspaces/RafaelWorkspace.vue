<template>
  <div class="rafael-workspace">
    <div class="workspace-header">
      <h3>📊 Espacio de Trabajo - RAFAEL</h3>
      <div class="tabs">
        <button 
          :class="{ active: activeTab === 'documents' }"
          @click="activeTab = 'documents'"
        >
          📄 Documentos
        </button>
        <button 
          :class="{ active: activeTab === 'invoices' }"
          @click="activeTab = 'invoices'"
        >
          🧾 Facturas
        </button>
        <button 
          :class="{ active: activeTab === 'taxes' }"
          @click="activeTab = 'taxes'"
        >
          💰 Impuestos
        </button>
        <button 
          :class="{ active: activeTab === 'credentials' }"
          @click="activeTab === 'credentials'"
        >
          🔐 Credenciales
        </button>
      </div>
    </div>

    <!-- Documentos -->
    <div v-if="activeTab === 'documents'" class="documents-section">
      <div class="upload-area">
        <div class="upload-box" @click="triggerFileUpload">
          <input 
            ref="fileInput"
            type="file"
            @change="handleFileUpload"
            style="display: none"
            accept=".pdf,.jpg,.jpeg,.png"
          />
          <div class="upload-icon">📤</div>
          <p>Subir Documento</p>
          <span>DNI, Certificado Digital, Contratos...</span>
        </div>
      </div>

      <div class="documents-list">
        <div 
          v-for="doc in documents" 
          :key="doc.id"
          class="document-item"
        >
          <div class="doc-icon">📄</div>
          <div class="doc-info">
            <h4>{{ doc.name }}</h4>
            <span class="doc-meta">{{ doc.type }} • {{ formatFileSize(doc.size) }} • {{ formatDate(doc.uploaded_at) }}</span>
          </div>
          <div class="doc-actions">
            <button @click="viewDocument(doc.id)" class="btn-view">👁️ Ver</button>
            <button @click="downloadDocument(doc.id)" class="btn-download">⬇️</button>
            <button @click="deleteDocument(doc.id)" class="btn-delete">🗑️</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Facturas -->
    <div v-if="activeTab === 'invoices'" class="invoices-section">
      <div class="section-header">
        <h4>Facturas Pendientes de Envío</h4>
        <button @click="createInvoice" class="btn-create">+ Nueva Factura</button>
      </div>

      <div class="invoices-list">
        <div 
          v-for="invoice in invoices" 
          :key="invoice.id"
          class="invoice-card"
        >
          <div class="invoice-header">
            <div>
              <h4>{{ invoice.number }}</h4>
              <span class="invoice-client">{{ invoice.client_name }}</span>
            </div>
            <div class="invoice-amount">€{{ invoice.total.toFixed(2) }}</div>
          </div>
          <div class="invoice-details">
            <div class="detail">
              <span class="detail-label">Fecha:</span>
              <span>{{ formatDate(invoice.date) }}</span>
            </div>
            <div class="detail">
              <span class="detail-label">Base imponible:</span>
              <span>€{{ invoice.base.toFixed(2) }}</span>
            </div>
            <div class="detail">
              <span class="detail-label">IVA:</span>
              <span>€{{ invoice.tax.toFixed(2) }}</span>
            </div>
          </div>
          <div class="invoice-actions">
            <button 
              v-if="invoice.status === 'draft'" 
              @click="approveInvoice(invoice.id)"
              class="btn-approve"
            >
              ✅ Aprobar y Enviar
            </button>
            <button @click="previewInvoice(invoice.id)" class="btn-preview">👁️ Vista Previa</button>
            <button @click="editInvoice(invoice.id)" class="btn-edit">✏️ Editar</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Impuestos -->
    <div v-if="activeTab === 'taxes'" class="taxes-section">
      <div class="tax-models">
        <div 
          v-for="model in taxModels" 
          :key="model.id"
          class="tax-model-card"
        >
          <div class="model-header">
            <h4>{{ model.name }}</h4>
            <span :class="['model-status', model.status]">{{ model.status_text }}</span>
          </div>
          <div class="model-info">
            <p>{{ model.description }}</p>
            <div class="model-period">
              <strong>Período:</strong> {{ model.period }}
            </div>
            <div class="model-deadline">
              <strong>Fecha límite:</strong> {{ formatDate(model.deadline) }}
            </div>
          </div>
          <div class="model-summary" v-if="model.data">
            <div class="summary-item">
              <span>Base imponible:</span>
              <span>€{{ model.data.base?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="summary-item">
              <span>Cuota:</span>
              <span>€{{ model.data.tax?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="summary-item total">
              <span>Resultado:</span>
              <span>€{{ model.data.result?.toFixed(2) || '0.00' }}</span>
            </div>
          </div>
          <div class="model-actions">
            <button 
              v-if="model.status === 'ready'"
              @click="approveTaxModel(model.id)"
              class="btn-approve"
            >
              ✅ Aprobar y Presentar
            </button>
            <button 
              v-else-if="model.status === 'draft'"
              @click="reviewTaxModel(model.id)"
              class="btn-review"
            >
              👁️ Revisar
            </button>
            <button 
              v-else
              disabled
              class="btn-submitted"
            >
              ✓ Presentado
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Credenciales -->
    <div v-if="activeTab === 'credentials'" class="credentials-section">
      <div class="credentials-form">
        <h4>🔐 Credenciales de Hacienda (AEAT)</h4>
        <p class="help-text">Necesarias para presentar modelos fiscales automáticamente</p>

        <div class="form-group">
          <label>NIF / CIF</label>
          <input v-model="credentials.nif" type="text" placeholder="12345678A" />
        </div>

        <div class="form-group">
          <label>Certificado Digital</label>
          <div class="file-input-group">
            <input 
              ref="certInput"
              type="file"
              @change="handleCertUpload"
              accept=".p12,.pfx"
              style="display: none"
            />
            <button @click="$refs.certInput.click()" class="btn-upload">
              📄 Subir Certificado (.p12 / .pfx)
            </button>
            <span v-if="credentials.cert_name">{{ credentials.cert_name }}</span>
          </div>
        </div>

        <div class="form-group">
          <label>Contraseña del Certificado</label>
          <input v-model="credentials.cert_password" type="password" placeholder="••••••••" />
        </div>

        <div class="form-actions">
          <button @click="saveCredentials" class="btn-save">💾 Guardar Credenciales</button>
          <button @click="testCredentials" class="btn-test">🔍 Probar Conexión</button>
        </div>

        <div class="security-notice">
          <p>🔒 Tus credenciales están encriptadas y solo las usa RAFAEL para gestiones oficiales.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('documents')
const fileInput = ref(null)
const certInput = ref(null)

const credentials = ref({
  nif: '',
  cert_name: '',
  cert_password: ''
})

const documents = ref([
  {
    id: 1,
    name: 'DNI - Carlos Jesús',
    type: 'Identificación',
    size: 2458000,
    uploaded_at: '2024-11-01T10:00:00'
  },
  {
    id: 2,
    name: 'Certificado Digital FNMT',
    type: 'Certificado',
    size: 5120,
    uploaded_at: '2024-11-02T14:30:00'
  }
])

const invoices = ref([
  {
    id: 1,
    number: '2024-045',
    client_name: 'Empresa SL',
    date: '2024-11-04',
    base: 1000.00,
    tax: 210.00,
    total: 1210.00,
    status: 'draft'
  },
  {
    id: 2,
    number: '2024-046',
    client_name: 'Cliente Test SA',
    date: '2024-11-04',
    base: 500.00,
    tax: 105.00,
    total: 605.00,
    status: 'draft'
  }
])

const taxModels = ref([
  {
    id: 1,
    name: 'Modelo 303 - IVA Trimestral',
    description: 'Declaración trimestral del IVA',
    period: 'Q3 2024',
    deadline: '2024-11-20',
    status: 'ready',
    status_text: 'Listo para presentar',
    data: {
      base: 15000.00,
      tax: 3150.00,
      result: 2800.00
    }
  },
  {
    id: 2,
    name: 'Modelo 111 - Retenciones IRPF',
    description: 'Retenciones e ingresos a cuenta del IRPF',
    period: 'Octubre 2024',
    deadline: '2024-11-20',
    status: 'draft',
    status_text: 'Borrador',
    data: {
      base: 8000.00,
      tax: 1200.00,
      result: 1200.00
    }
  }
])

function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function triggerFileUpload() {
  fileInput.value.click()
}

function handleFileUpload(event) {
  const file = event.target.files[0]
  if (file) {
    console.log('Subir documento:', file.name)
    // TODO: Llamar API para subir
  }
}

function handleCertUpload(event) {
  const file = event.target.files[0]
  if (file) {
    credentials.value.cert_name = file.name
    console.log('Certificado seleccionado:', file.name)
  }
}

function viewDocument(id) {
  console.log('Ver documento:', id)
  // TODO: Mostrar preview
}

function downloadDocument(id) {
  console.log('Descargar documento:', id)
  // TODO: Descargar archivo
}

function deleteDocument(id) {
  if (confirm('¿Eliminar este documento?')) {
    console.log('Eliminar documento:', id)
    // TODO: Llamar API
  }
}

function createInvoice() {
  console.log('Crear nueva factura')
  // TODO: Abrir formulario
}

function approveInvoice(id) {
  if (confirm('¿Aprobar y enviar esta factura al cliente?')) {
    console.log('Aprobar factura:', id)
    // TODO: Llamar API
  }
}

function previewInvoice(id) {
  console.log('Vista previa factura:', id)
  // TODO: Mostrar PDF
}

function editInvoice(id) {
  console.log('Editar factura:', id)
  // TODO: Abrir editor
}

function approveTaxModel(id) {
  if (confirm('¿Aprobar y presentar este modelo a Hacienda?')) {
    console.log('Aprobar modelo fiscal:', id)
    // TODO: Llamar API
  }
}

function reviewTaxModel(id) {
  console.log('Revisar modelo:', id)
  // TODO: Mostrar detalles
}

function saveCredentials() {
  console.log('Guardar credenciales:', credentials.value)
  // TODO: Llamar API (encriptado)
  alert('✅ Credenciales guardadas de forma segura')
}

function testCredentials() {
  console.log('Probar conexión con AEAT')
  // TODO: Llamar API para test
  alert('🔍 Probando conexión con Hacienda...')
}
</script>

<style scoped>
.rafael-workspace {
  padding: 20px;
}

.workspace-header h3 {
  font-size: 24px;
  margin-bottom: 15px;
  color: #1f2937;
}

.tabs {
  display: flex;
  gap: 10px;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 30px;
}

.tabs button {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  transition: all 0.3s;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tabs button.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.upload-area {
  margin-bottom: 30px;
}

.upload-box {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-box:hover {
  border-color: #3b82f6;
  background: #f9fafb;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.upload-box p {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 5px;
}

.upload-box span {
  font-size: 14px;
  color: #6b7280;
}

.documents-list,
.invoices-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.document-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: white;
}

.doc-icon {
  font-size: 32px;
}

.doc-info {
  flex: 1;
}

.doc-info h4 {
  font-size: 16px;
  margin-bottom: 5px;
  color: #1f2937;
}

.doc-meta {
  font-size: 12px;
  color: #6b7280;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.doc-actions button {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.doc-actions button:hover {
  background: #f3f4f6;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h4 {
  font-size: 18px;
  color: #1f2937;
}

.btn-create {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-create:hover {
  background: #2563eb;
}

.invoice-card,
.tax-model-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
}

.invoice-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.invoice-header h4 {
  font-size: 18px;
  margin-bottom: 5px;
  color: #1f2937;
}

.invoice-client {
  font-size: 14px;
  color: #6b7280;
}

.invoice-amount {
  font-size: 24px;
  font-weight: 700;
  color: #059669;
}

.invoice-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin-bottom: 15px;
  padding: 15px;
  background: #f9fafb;
  border-radius: 8px;
}

.detail {
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.invoice-actions {
  display: flex;
  gap: 10px;
}

.invoice-actions button,
.model-actions button {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-approve {
  background: #10b981;
  color: white;
}

.btn-approve:hover {
  background: #059669;
}

.btn-preview,
.btn-review {
  background: #3b82f6;
  color: white;
}

.btn-preview:hover,
.btn-review:hover {
  background: #2563eb;
}

.btn-edit {
  background: #f59e0b;
  color: white;
}

.btn-edit:hover {
  background: #d97706;
}

.btn-submitted {
  background: #d1fae5;
  color: #065f46;
  cursor: not-allowed;
}

.tax-models {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.model-header h4 {
  font-size: 16px;
  color: #1f2937;
}

.model-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.model-status.ready {
  background: #d1fae5;
  color: #065f46;
}

.model-status.draft {
  background: #fef3c7;
  color: #92400e;
}

.model-info {
  margin-bottom: 15px;
  font-size: 14px;
  color: #4b5563;
}

.model-period,
.model-deadline {
  margin-top: 8px;
  font-size: 13px;
}

.model-summary {
  background: #f9fafb;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.summary-item.total {
  font-weight: 700;
  font-size: 16px;
  color: #059669;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}

.credentials-form {
  max-width: 600px;
  margin: 0 auto;
}

.credentials-form h4 {
  font-size: 20px;
  margin-bottom: 10px;
  color: #1f2937;
}

.help-text {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 30px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.file-input-group {
  display: flex;
  align-items: center;
  gap: 15px;
}

.btn-upload {
  padding: 10px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.form-actions {
  display: flex;
  gap: 15px;
  margin-top: 30px;
}

.btn-save,
.btn-test {
  flex: 1;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-save {
  background: #10b981;
  color: white;
}

.btn-save:hover {
  background: #059669;
}

.btn-test {
  background: #3b82f6;
  color: white;
}

.btn-test:hover {
  background: #2563eb;
}

.security-notice {
  margin-top: 30px;
  padding: 15px;
  background: #eff6ff;
  border-left: 4px solid #3b82f6;
  border-radius: 6px;
}

.security-notice p {
  font-size: 13px;
  color: #1e40af;
}
</style>

