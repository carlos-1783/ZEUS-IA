<template>
  <div class="perseo-workspace">
    <div class="workspace-header">
      <h3>📢 Espacio de Trabajo - PERSEO</h3>
      <div class="tabs">
        <button 
          :class="{ active: activeTab === 'content' }"
          @click="activeTab = 'content'"
        >
          📁 Contenido Creado
        </button>
        <button 
          :class="{ active: activeTab === 'campaigns' }"
          @click="activeTab = 'campaigns'"
        >
          🎯 Campañas
        </button>
        <button 
          :class="{ active: activeTab === 'pending' }"
          @click="activeTab = 'pending'"
        >
          ⏳ Pendientes Aprobación
        </button>
      </div>
    </div>

    <!-- Contenido Creado -->
    <div v-if="activeTab === 'content'" class="content-gallery">
      <div class="gallery-filters">
        <select v-model="contentFilter">
          <option value="all">Todos</option>
          <option value="image">Imágenes</option>
          <option value="video">Videos</option>
          <option value="post">Posts</option>
          <option value="ad">Anuncios</option>
        </select>
      </div>

      <div class="gallery-grid">
        <div 
          v-for="item in filteredContent" 
          :key="item.id"
          class="gallery-item"
          @click="previewItem(item)"
        >
          <div class="item-preview">
            <img v-if="item.type === 'image'" :src="item.thumbnail" :alt="item.title" />
            <video v-else-if="item.type === 'video'" :src="item.url" controls></video>
            <div v-else class="post-preview">
              <p>{{ item.content.substring(0, 100) }}...</p>
            </div>
          </div>
          <div class="item-info">
            <h4>{{ item.title }}</h4>
            <span class="item-date">{{ formatDate(item.created_at) }}</span>
            <span :class="['item-status', item.status]">{{ item.status }}</span>
          </div>
          <div class="item-actions">
            <button v-if="item.status === 'draft'" @click.stop="approveContent(item.id)" class="btn-approve">
              ✅ Aprobar
            </button>
            <button @click.stop="editContent(item.id)" class="btn-edit">
              ✏️ Editar
            </button>
            <button @click.stop="deleteContent(item.id)" class="btn-delete">
              🗑️ Eliminar
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Campañas -->
    <div v-if="activeTab === 'campaigns'" class="campaigns-section">
      <div class="campaigns-list">
        <div 
          v-for="campaign in campaigns" 
          :key="campaign.id"
          class="campaign-card"
        >
          <div class="campaign-header">
            <h4>{{ campaign.name }}</h4>
            <span :class="['campaign-status', campaign.status]">{{ campaign.status }}</span>
          </div>
          <div class="campaign-stats">
            <div class="stat">
              <span class="stat-label">Presupuesto:</span>
              <span class="stat-value">€{{ campaign.budget }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Gastado:</span>
              <span class="stat-value">€{{ campaign.spent }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">ROI:</span>
              <span class="stat-value">{{ campaign.roi }}x</span>
            </div>
            <div class="stat">
              <span class="stat-label">Conversiones:</span>
              <span class="stat-value">{{ campaign.conversions }}</span>
            </div>
          </div>
          <div class="campaign-actions">
            <button @click="viewCampaign(campaign.id)" class="btn-view">Ver Detalles</button>
            <button @click="pauseCampaign(campaign.id)" class="btn-pause">Pausar</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Pendientes de Aprobación -->
    <div v-if="activeTab === 'pending'" class="pending-section">
      <div v-if="pendingApprovals.length === 0" class="empty-state">
        <p>✅ No hay contenido pendiente de aprobación</p>
      </div>
      <div v-else class="pending-list">
        <div 
          v-for="item in pendingApprovals" 
          :key="item.id"
          class="pending-item"
        >
          <div class="pending-preview">
            <h4>{{ item.title }}</h4>
            <p>{{ item.description }}</p>
            <div class="preview-content">
              <img v-if="item.type === 'image'" :src="item.url" />
              <video v-else-if="item.type === 'video'" :src="item.url" controls></video>
              <div v-else class="text-preview">{{ item.content }}</div>
            </div>
          </div>
          <div class="pending-actions">
            <button @click="approveItem(item.id)" class="btn-approve">✅ Aprobar y Publicar</button>
            <button @click="requestChanges(item.id)" class="btn-edit">✏️ Solicitar Cambios</button>
            <button @click="rejectItem(item.id)" class="btn-reject">❌ Rechazar</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de Preview -->
    <div v-if="previewModal" class="modal-overlay" @click="closePreview">
      <div class="modal-content" @click.stop>
        <button class="modal-close" @click="closePreview">×</button>
        <div class="modal-body">
          <h3>{{ selectedItem.title }}</h3>
          <div class="preview-large">
            <img v-if="selectedItem.type === 'image'" :src="selectedItem.url" />
            <video v-else-if="selectedItem.type === 'video'" :src="selectedItem.url" controls></video>
            <div v-else class="post-full">{{ selectedItem.content }}</div>
          </div>
          <div class="modal-actions">
            <button @click="downloadItem" class="btn-download">⬇️ Descargar</button>
            <button @click="shareItem" class="btn-share">🔗 Compartir</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const activeTab = ref('content')
const contentFilter = ref('all')
const previewModal = ref(false)
const selectedItem = ref(null)

// Datos de ejemplo (TODO: Conectar con API)
const content = ref([
  {
    id: 1,
    type: 'image',
    title: 'Post LinkedIn - IA en Marketing',
    thumbnail: '/images/sample-post.jpg',
    url: '/images/sample-post.jpg',
    content: '',
    status: 'published',
    created_at: '2024-11-04T10:30:00'
  },
  {
    id: 2,
    type: 'video',
    title: 'Video Promocional - Black Friday',
    thumbnail: '/images/sample-video-thumb.jpg',
    url: '/videos/sample-promo.mp4',
    content: '',
    status: 'draft',
    created_at: '2024-11-04T12:00:00'
  },
  {
    id: 3,
    type: 'post',
    title: 'Post Instagram - Lanzamiento',
    thumbnail: '',
    url: '',
    content: '🚀 Hoy lanzamos algo increíble. ZEUS-IA está aquí para revolucionar cómo gestionas tu empresa...',
    status: 'draft',
    created_at: '2024-11-04T14:15:00'
  }
])

const campaigns = ref([
  {
    id: 1,
    name: 'Marketing Digital España',
    status: 'active',
    budget: 500,
    spent: 342,
    roi: 4.2,
    conversions: 45
  },
  {
    id: 2,
    name: 'Instagram Awareness',
    status: 'active',
    budget: 300,
    spent: 180,
    roi: 3.1,
    conversions: 28
  }
])

const pendingApprovals = ref([
  {
    id: 1,
    type: 'ad',
    title: 'Anuncio Google Ads - Cerveza 2x1',
    description: 'Campaña promocional para Black Friday',
    url: '',
    content: '🍺 BLACK FRIDAY ESPECIAL\n\n2x1 en todas nuestras cervezas artesanales\n\nSolo este fin de semana. ¡No te lo pierdas!\n\n👉 www.tucerveceria.com'
  }
])

const filteredContent = computed(() => {
  if (contentFilter.value === 'all') return content.value
  return content.value.filter(item => item.type === contentFilter.value)
})

function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function previewItem(item) {
  selectedItem.value = item
  previewModal.value = true
}

function closePreview() {
  previewModal.value = false
  selectedItem.value = null
}

function approveContent(id) {
  console.log('Aprobar contenido:', id)
  // TODO: Llamar API
}

function editContent(id) {
  console.log('Editar contenido:', id)
  // TODO: Abrir editor
}

function deleteContent(id) {
  if (confirm('¿Eliminar este contenido?')) {
    console.log('Eliminar:', id)
    // TODO: Llamar API
  }
}

function approveItem(id) {
  console.log('Aprobar y publicar:', id)
  // TODO: Llamar API
}

function requestChanges(id) {
  const feedback = prompt('¿Qué cambios necesitas?')
  if (feedback) {
    console.log('Solicitar cambios:', id, feedback)
    // TODO: Llamar API
  }
}

function rejectItem(id) {
  if (confirm('¿Rechazar este contenido?')) {
    console.log('Rechazar:', id)
    // TODO: Llamar API
  }
}

function viewCampaign(id) {
  console.log('Ver campaña:', id)
  // TODO: Mostrar detalles
}

function pauseCampaign(id) {
  console.log('Pausar campaña:', id)
  // TODO: Llamar API
}

function downloadItem() {
  console.log('Descargar:', selectedItem.value)
  // TODO: Implementar descarga
}

function shareItem() {
  console.log('Compartir:', selectedItem.value)
  // TODO: Implementar compartir
}
</script>

<style scoped>
.perseo-workspace {
  padding: 20px;
}

.workspace-header {
  margin-bottom: 30px;
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

.gallery-filters {
  margin-bottom: 20px;
}

.gallery-filters select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.gallery-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.gallery-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 20px rgba(0,0,0,0.1);
}

.item-preview {
  width: 100%;
  height: 200px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.item-preview img,
.item-preview video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.post-preview {
  padding: 20px;
  text-align: left;
  font-size: 14px;
  color: #4b5563;
}

.item-info {
  padding: 15px;
}

.item-info h4 {
  font-size: 16px;
  margin-bottom: 8px;
  color: #1f2937;
}

.item-date {
  font-size: 12px;
  color: #9ca3af;
  margin-right: 10px;
}

.item-status {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.item-status.published {
  background: #d1fae5;
  color: #065f46;
}

.item-status.draft {
  background: #fef3c7;
  color: #92400e;
}

.item-actions {
  padding: 0 15px 15px;
  display: flex;
  gap: 8px;
}

.item-actions button {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
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

.btn-edit {
  background: #3b82f6;
  color: white;
}

.btn-edit:hover {
  background: #2563eb;
}

.btn-delete,
.btn-reject {
  background: #ef4444;
  color: white;
}

.btn-delete:hover,
.btn-reject:hover {
  background: #dc2626;
}

.campaigns-list,
.pending-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.campaign-card,
.pending-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
}

.campaign-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.campaign-status.active {
  background: #d1fae5;
  color: #065f46;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.campaign-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 15px;
}

.stat {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.campaign-actions {
  display: flex;
  gap: 10px;
}

.btn-view,
.btn-pause {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-view:hover,
.btn-pause:hover {
  background: #f3f4f6;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #6b7280;
  font-size: 16px;
}

.pending-preview h4 {
  font-size: 18px;
  margin-bottom: 8px;
}

.pending-preview p {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 15px;
}

.preview-content,
.text-preview {
  background: #f9fafb;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.text-preview {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.6;
}

.pending-actions {
  display: flex;
  gap: 10px;
}

.pending-actions button {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 16px;
  max-width: 800px;
  max-height: 90vh;
  overflow: auto;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 15px;
  right: 15px;
  background: white;
  border: none;
  font-size: 32px;
  cursor: pointer;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-body {
  padding: 40px;
}

.modal-body h3 {
  font-size: 24px;
  margin-bottom: 20px;
}

.preview-large img,
.preview-large video {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 20px;
}

.post-full {
  background: #f9fafb;
  padding: 30px;
  border-radius: 8px;
  white-space: pre-wrap;
  line-height: 1.8;
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  gap: 15px;
}

.btn-download,
.btn-share {
  flex: 1;
  padding: 12px 20px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-download:hover,
.btn-share:hover {
  background: #f3f4f6;
}
</style>

