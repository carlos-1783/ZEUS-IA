<template>
  <div class="justicia-workspace">
    <div class="workspace-header">
      <h3>⚖️ Espacio de Trabajo - JUSTICIA</h3>
      <div class="tabs">
        <button :class="{ active: activeTab === 'contracts' }" @click="activeTab = 'contracts'">
          📄 Contratos
        </button>
        <button :class="{ active: activeTab === 'compliance' }" @click="activeTab = 'compliance'">
          ✅ Compliance
        </button>
        <button :class="{ active: activeTab === 'policies' }" @click="activeTab = 'policies'">
          📋 Políticas
        </button>
        <button :class="{ active: activeTab === 'gdpr' }" @click="activeTab = 'gdpr'">
          🔒 GDPR
        </button>
      </div>
    </div>

    <!-- Contratos -->
    <div v-if="activeTab === 'contracts'" class="contracts-section">
      <div class="section-header">
        <h4>Contratos Pendientes de Revisión</h4>
        <button @click="uploadContract" class="btn-upload">📤 Subir Contrato</button>
      </div>

      <div class="contracts-list">
        <div v-for="contract in pendingContracts" :key="contract.id" class="contract-card">
          <div class="contract-header">
            <div>
              <h4>{{ contract.title }}</h4>
              <span class="contract-type">{{ contract.type }}</span>
            </div>
            <span class="contract-status" :class="contract.status">{{ contract.status_text }}</span>
          </div>
          
          <div class="contract-info">
            <div class="info-row">
              <span class="label">Cliente:</span>
              <span class="value">{{ contract.client }}</span>
            </div>
            <div class="info-row">
              <span class="label">Fecha subida:</span>
              <span class="value">{{ formatDate(contract.uploaded_at) }}</span>
            </div>
            <div class="info-row">
              <span class="label">Cláusulas:</span>
              <span class="value">{{ contract.clauses_count }}</span>
            </div>
          </div>

          <div v-if="contract.issues && contract.issues.length > 0" class="contract-issues">
            <h5>⚠️ Problemas Detectados:</h5>
            <ul>
              <li v-for="(issue, idx) in contract.issues" :key="idx">{{ issue }}</li>
            </ul>
          </div>

          <div class="contract-actions">
            <button @click="reviewContract(contract.id)" class="btn-review">👁️ Revisar</button>
            <button v-if="contract.status === 'reviewed'" @click="approveContract(contract.id)" class="btn-approve">
              ✅ Aprobar
            </button>
            <button v-if="contract.status === 'reviewed'" @click="rejectContract(contract.id)" class="btn-reject">
              ❌ Rechazar
            </button>
            <button @click="downloadContract(contract.id)" class="btn-download">⬇️ Descargar</button>
          </div>
        </div>

        <div v-if="pendingContracts.length === 0" class="empty-state">
          ✅ No hay contratos pendientes de revisión
        </div>
      </div>
    </div>

    <!-- Compliance -->
    <div v-if="activeTab === 'compliance'" class="compliance-section">
      <div class="section-header">
        <h4>Auditorías de Cumplimiento</h4>
        <button @click="runComplianceCheck" class="btn-run">🔍 Nueva Auditoría</button>
      </div>

      <div class="compliance-overview">
        <div class="compliance-card">
          <h4>🇪🇺 GDPR</h4>
          <div class="compliance-score">
            <div class="score-circle" :style="{ background: getScoreColor(98) }">
              <span>98%</span>
            </div>
            <p>Conforme</p>
          </div>
          <ul class="compliance-checks">
            <li class="check-ok">✅ Consentimiento</li>
            <li class="check-ok">✅ Derechos ARCO</li>
            <li class="check-warning">⚠️ Política de cookies (actualizar)</li>
          </ul>
        </div>

        <div class="compliance-card">
          <h4>🔐 LOPD</h4>
          <div class="compliance-score">
            <div class="score-circle" :style="{ background: getScoreColor(100) }">
              <span>100%</span>
            </div>
            <p>Conforme</p>
          </div>
          <ul class="compliance-checks">
            <li class="check-ok">✅ Registro de actividades</li>
            <li class="check-ok">✅ DPO asignado</li>
            <li class="check-ok">✅ Evaluación de impacto</li>
          </ul>
        </div>

        <div class="compliance-card">
          <h4>📊 ISO 27001</h4>
          <div class="compliance-score">
            <div class="score-circle" :style="{ background: getScoreColor(85) }">
              <span>85%</span>
            </div>
            <p>En progreso</p>
          </div>
          <ul class="compliance-checks">
            <li class="check-ok">✅ Gestión de riesgos</li>
            <li class="check-warning">⚠️ Políticas de seguridad</li>
            <li class="check-pending">⏳ Auditoría externa pendiente</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Políticas -->
    <div v-if="activeTab === 'policies'" class="policies-section">
      <div class="section-header">
        <h4>Políticas y Documentos Legales</h4>
        <button @click="createPolicy" class="btn-create">+ Nueva Política</button>
      </div>

      <div class="policies-list">
        <div v-for="policy in policies" :key="policy.id" class="policy-card">
          <div class="policy-header">
            <h4>{{ policy.title }}</h4>
            <span class="policy-version">v{{ policy.version }}</span>
          </div>
          <p class="policy-description">{{ policy.description }}</p>
          <div class="policy-meta">
            <span>Última actualización: {{ formatDate(policy.updated_at) }}</span>
            <span :class="['policy-status', policy.status]">{{ policy.status_text }}</span>
          </div>
          <div class="policy-actions">
            <button @click="viewPolicy(policy.id)" class="btn-view">👁️ Ver</button>
            <button @click="editPolicy(policy.id)" class="btn-edit">✏️ Editar</button>
            <button @click="publishPolicy(policy.id)" class="btn-publish">🚀 Publicar</button>
          </div>
        </div>
      </div>
    </div>

    <!-- GDPR -->
    <div v-if="activeTab === 'gdpr'" class="gdpr-section">
      <div class="section-header">
        <h4>Gestión GDPR</h4>
      </div>

      <div class="gdpr-cards">
        <div class="gdpr-card">
          <h4>📝 Solicitudes ARCO</h4>
          <p class="gdpr-description">Acceso, Rectificación, Cancelación, Oposición</p>
          <div class="gdpr-stat">
            <span class="stat-number">{{ arcoRequests.length }}</span>
            <span class="stat-label">Pendientes</span>
          </div>
          <button @click="viewArcoRequests" class="btn-manage">Gestionar</button>
        </div>

        <div class="gdpr-card">
          <h4>🗑️ Derecho al Olvido</h4>
          <p class="gdpr-description">Solicitudes de eliminación de datos</p>
          <div class="gdpr-stat">
            <span class="stat-number">0</span>
            <span class="stat-label">Pendientes</span>
          </div>
          <button @click="viewDeletionRequests" class="btn-manage">Gestionar</button>
        </div>

        <div class="gdpr-card">
          <h4>📦 Portabilidad</h4>
          <p class="gdpr-description">Exportación de datos personales</p>
          <div class="gdpr-stat">
            <span class="stat-number">2</span>
            <span class="stat-label">Pendientes</span>
          </div>
          <button @click="viewPortabilityRequests" class="btn-manage">Gestionar</button>
        </div>

        <div class="gdpr-card">
          <h4>🔔 Notificaciones</h4>
          <p class="gdpr-description">Brechas de seguridad (72h AEPD)</p>
          <div class="gdpr-stat">
            <span class="stat-number">0</span>
            <span class="stat-label">Activas</span>
          </div>
          <button @click="viewNotifications" class="btn-manage">Gestionar</button>
        </div>
      </div>

      <div class="data-registry">
        <h4>📊 Registro de Actividades de Tratamiento</h4>
        <div class="registry-table">
          <div class="table-header">
            <span>Tratamiento</span>
            <span>Finalidad</span>
            <span>Base legal</span>
            <span>Categorías</span>
          </div>
          <div class="table-row">
            <span>Gestión de clientes</span>
            <span>Facturación</span>
            <span>Ejecución contrato</span>
            <span>Identificación, contacto</span>
          </div>
          <div class="table-row">
            <span>Marketing</span>
            <span>Campañas publicitarias</span>
            <span>Consentimiento</span>
            <span>Email, preferencias</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('contracts')

const pendingContracts = ref([
  {
    id: 1,
    title: 'Contrato de Suscripción - Empresa XYZ SL',
    type: 'Subscription Agreement',
    client: 'Empresa XYZ SL',
    uploaded_at: new Date(Date.now() - 1000 * 3600 * 24 * 2),
    clauses_count: 23,
    status: 'reviewed',
    status_text: 'Revisado',
    issues: [
      'Cláusula 12: Falta definir período de preaviso para cancelación',
      'Cláusula 18: Términos de renovación automática deben ser más claros'
    ]
  },
  {
    id: 2,
    title: 'Acuerdo de Confidencialidad - Partner Tech SA',
    type: 'NDA',
    client: 'Partner Tech SA',
    uploaded_at: new Date(Date.now() - 1000 * 3600 * 12),
    clauses_count: 8,
    status: 'pending',
    status_text: 'Pendiente',
    issues: []
  }
])

const policies = ref([
  {
    id: 1,
    title: 'Política de Privacidad',
    description: 'Tratamiento de datos personales según GDPR',
    version: '2.1',
    updated_at: new Date(Date.now() - 1000 * 3600 * 24 * 15),
    status: 'published',
    status_text: 'Publicada'
  },
  {
    id: 2,
    title: 'Términos y Condiciones',
    description: 'Condiciones generales de uso del servicio',
    version: '3.0',
    updated_at: new Date(Date.now() - 1000 * 3600 * 24 * 5),
    status: 'draft',
    status_text: 'Borrador'
  },
  {
    id: 3,
    title: 'Política de Cookies',
    description: 'Uso de cookies y tecnologías similares',
    version: '1.5',
    updated_at: new Date(Date.now() - 1000 * 3600 * 24 * 30),
    status: 'published',
    status_text: 'Publicada'
  }
])

const arcoRequests = ref([
  { id: 1, type: 'access', client: 'Juan Pérez' },
  { id: 2, type: 'rectification', client: 'María García' }
])

function formatDate(date) {
  return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function getScoreColor(score) {
  if (score >= 95) return 'linear-gradient(135deg, #10b981, #059669)'
  if (score >= 80) return 'linear-gradient(135deg, #eab308, #ca8a04)'
  return 'linear-gradient(135deg, #ef4444, #dc2626)'
}

function uploadContract() {
  console.log('Subir nuevo contrato')
}

function reviewContract(id) {
  console.log('Revisar contrato:', id)
}

function approveContract(id) {
  if (confirm('¿Aprobar este contrato?')) {
    console.log('Aprobar contrato:', id)
  }
}

function rejectContract(id) {
  const reason = prompt('¿Motivo del rechazo?')
  if (reason) {
    console.log('Rechazar contrato:', id, reason)
  }
}

function downloadContract(id) {
  console.log('Descargar contrato:', id)
}

function runComplianceCheck() {
  console.log('Ejecutar auditoría de compliance')
}

function createPolicy() {
  console.log('Crear nueva política')
}

function viewPolicy(id) {
  console.log('Ver política:', id)
}

function editPolicy(id) {
  console.log('Editar política:', id)
}

function publishPolicy(id) {
  if (confirm('¿Publicar esta política en la web?')) {
    console.log('Publicar política:', id)
  }
}

function viewArcoRequests() {
  console.log('Ver solicitudes ARCO')
}

function viewDeletionRequests() {
  console.log('Ver solicitudes de eliminación')
}

function viewPortabilityRequests() {
  console.log('Ver solicitudes de portabilidad')
}

function viewNotifications() {
  console.log('Ver notificaciones de brechas')
}
</script>

<style scoped>
.justicia-workspace {
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
  color: #8b5cf6;
  border-bottom-color: #8b5cf6;
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

.btn-upload,
.btn-run,
.btn-create {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: #8b5cf6;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-upload:hover,
.btn-run:hover,
.btn-create:hover {
  background: #7c3aed;
}

.contracts-list,
.policies-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.contract-card,
.policy-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
}

.contract-header,
.policy-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.contract-header h4,
.policy-header h4 {
  font-size: 18px;
  margin: 0 0 5px;
  color: #1f2937;
}

.contract-type {
  font-size: 13px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 4px 12px;
  border-radius: 4px;
  display: inline-block;
  margin-top: 5px;
}

.contract-status,
.policy-status {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.contract-status.reviewed {
  background: #dbeafe;
  color: #1e40af;
}

.contract-status.pending {
  background: #fef3c7;
  color: #92400e;
}

.contract-status.approved {
  background: #d1fae5;
  color: #065f46;
}

.contract-info {
  margin-bottom: 15px;
}

.info-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-row .label {
  color: #6b7280;
  min-width: 120px;
}

.info-row .value {
  color: #1f2937;
  font-weight: 500;
}

.contract-issues {
  background: #fef2f2;
  border-left: 4px solid #ef4444;
  padding: 15px;
  margin-bottom: 15px;
  border-radius: 6px;
}

.contract-issues h5 {
  font-size: 14px;
  margin: 0 0 10px;
  color: #991b1b;
}

.contract-issues ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #dc2626;
}

.contract-issues li {
  margin-bottom: 5px;
}

.contract-actions,
.policy-actions {
  display: flex;
  gap: 10px;
}

.contract-actions button,
.policy-actions button {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-review,
.btn-view {
  background: #3b82f6;
  color: white;
}

.btn-review:hover,
.btn-view:hover {
  background: #2563eb;
}

.btn-approve {
  background: #10b981;
  color: white;
}

.btn-approve:hover {
  background: #059669;
}

.btn-reject {
  background: #ef4444;
  color: white;
}

.btn-reject:hover {
  background: #dc2626;
}

.btn-download,
.btn-edit {
  background: #6b7280;
  color: white;
}

.btn-download:hover,
.btn-edit:hover {
  background: #4b5563;
}

.btn-publish {
  background: #8b5cf6;
  color: white;
}

.btn-publish:hover {
  background: #7c3aed;
}

.compliance-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.compliance-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
  text-align: center;
}

.compliance-card h4 {
  font-size: 18px;
  margin: 0 0 20px;
  color: #1f2937;
}

.compliance-score {
  margin-bottom: 20px;
}

.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.score-circle span {
  font-size: 28px;
  font-weight: 700;
  color: white;
}

.compliance-score p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.compliance-checks {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.compliance-checks li {
  padding: 8px 0;
  font-size: 14px;
  border-bottom: 1px solid #f3f4f6;
}

.compliance-checks li:last-child {
  border-bottom: none;
}

.check-ok {
  color: #059669;
}

.check-warning {
  color: #d97706;
}

.check-pending {
  color: #6b7280;
}

.policy-version {
  background: #f3f4f6;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
}

.policy-description {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 15px;
}

.policy-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  font-size: 13px;
  color: #6b7280;
}

.policy-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.policy-status.published {
  background: #d1fae5;
  color: #065f46;
}

.policy-status.draft {
  background: #fef3c7;
  color: #92400e;
}

.gdpr-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.gdpr-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
  text-align: center;
}

.gdpr-card h4 {
  font-size: 16px;
  margin: 0 0 10px;
  color: #1f2937;
}

.gdpr-description {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 20px;
}

.gdpr-stat {
  margin-bottom: 20px;
}

.stat-number {
  display: block;
  font-size: 48px;
  font-weight: 700;
  color: #8b5cf6;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.btn-manage {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-manage:hover {
  background: #f9fafb;
}

.data-registry {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.data-registry h4 {
  font-size: 16px;
  margin: 0 0 20px;
  color: #1f2937;
}

.registry-table {
  width: 100%;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 2fr 2fr 1.5fr 2fr;
  gap: 15px;
  padding: 12px 0;
  border-bottom: 1px solid #e5e7eb;
}

.table-header {
  font-weight: 700;
  font-size: 13px;
  color: #6b7280;
  text-transform: uppercase;
}

.table-row {
  font-size: 14px;
  color: #1f2937;
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: #6b7280;
  font-size: 16px;
}
</style>

