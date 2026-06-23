<template>
  <div class="workspace-playbooks">
    <header class="playbooks-header">
      <div>
        <h4>📝 Workspace IA</h4>
        <p class="subtitle">
          Solo playbooks y entregables — sin ejecución de negocio.
        </p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="reload">
        <i class="fas fa-sync-alt"></i>
        {{ isLoading ? 'Actualizando…' : 'Actualizar' }}
      </button>
    </header>

    <div v-if="error" class="error-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <span>No se pudieron cargar los playbooks: {{ error }}</span>
    </div>

    <section class="workspace-body" v-if="!isLoading && deliverables.length">
      <aside class="deliverable-list">
        <h4>Playbooks generados</h4>
        <ul>
          <li
            v-for="item in deliverables"
            :key="item.id"
            :class="{ active: item.id === selectedId }"
            @click="selectDeliverable(item.id)"
          >
            <div class="title">{{ formatTitle(item) }}</div>
            <div class="meta">
              <span>{{ formatDate(item.createdAt) }}</span>
              <span>{{ formatSize(item.sizeBytes) }}</span>
            </div>
            <div class="tags">
              <span class="tag schedule">Agenda</span>
              <span class="tag onboarding">Onboarding</span>
              <span class="tag coordination">Coordinación</span>
            </div>
          </li>
        </ul>
      </aside>

      <main class="deliverable-details" v-if="currentDetails">
        <header class="details-header">
          <div>
            <h4>{{ formatTitle(currentDeliverable ?? undefined) }}</h4>
            <span v-if="currentDeliverable" class="details-meta">
              Generado el {{ formatDate(currentDeliverable.createdAt) }}
            </span>
            <p v-if="currentDetails.summary" class="details-summary">
              {{ currentDetails.summary }}
            </p>
          </div>
          <div class="details-actions">
            <a
              v-if="currentDeliverable?.files.json"
              :href="buildDownloadLink(currentDeliverable.files.json)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn ghost"
            >
              Descargar JSON
            </a>
            <a
              v-if="currentDeliverable?.files.markdown"
              :href="buildDownloadLink(currentDeliverable.files.markdown)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn ghost"
            >
              Descargar Markdown
            </a>
          </div>
        </header>

        <div class="details-grid">
          <section class="card" v-if="currentDetails.support_schedule">
            <header class="card-header">
              <h5>📅 Agenda de Soporte</h5>
              <span class="badge">Semanas iniciales</span>
            </header>
            <div class="schedule">
              <div
                v-for="(week, label) in currentDetails.support_schedule"
                :key="label"
                class="week-block"
              >
                <h6>{{ formatWeek(label) }} · {{ week.theme }}</h6>
                <ul>
                  <li v-for="touch in week.touchpoints" :key="touch.day + touch.channel">
                    <strong>{{ touch.day }}</strong> · {{ touch.channel }} → {{ touch.goal }}
                  </li>
                </ul>
              </div>
            </div>
          </section>

          <section class="card" v-if="currentDetails.onboarding_manual">
            <header class="card-header">
              <h5>🧭 Manual de Onboarding</h5>
              <span class="badge teal">Módulos paso a paso</span>
            </header>
            <div class="modules">
              <div
                v-for="module in currentDetails.onboarding_manual.modules"
                :key="module.title"
                class="module"
              >
                <h6>{{ module.title }}</h6>
                <ul>
                  <li v-for="topic in module.content" :key="topic">{{ topic }}</li>
                </ul>
              </div>
            </div>
          </section>

          <section class="card" v-if="currentDetails.coordination_notes">
            <header class="card-header">
              <h5>🤝 Coordinación Multicanal</h5>
            </header>
            <div class="meetings" v-if="currentDetails.coordination_notes.meetings">
              <h6>Ritmo de reuniones</h6>
              <ul>
                <li v-for="meeting in currentDetails.coordination_notes.meetings" :key="meeting.frequency">
                  <strong>{{ meeting.frequency }}</strong> · {{ meeting.participants.join(', ') }} →
                  {{ meeting.objective }}
                </li>
              </ul>
            </div>
          </section>
        </div>
      </main>

      <main class="deliverable-details" v-else>
        <div class="empty-state">
          <div class="icon">📝</div>
          <h4>Selecciona un playbook</h4>
          <p>Elige un entregable para revisar agenda, recursos y coordinación.</p>
        </div>
      </main>
    </section>

    <section v-else class="empty-container">
      <div v-if="isLoading" class="empty-state">
        <div class="spinner"></div>
        <p>Cargando playbooks…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">🤝</div>
        <h4>Sin entregables disponibles</h4>
        <p>Solicita a AFRODITA un nuevo plan de soporte y aparecerá aquí.</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAutomationDeliverables } from '@/composables/useAutomationDeliverables'

const {
  items: deliverables,
  isLoading,
  error,
  load,
  buildDownloadLinkFor,
  fetchDeliverableData,
} = useAutomationDeliverables('AFRODITA')

const selectedId = ref<string | null>(null)
const currentDetails = ref<Record<string, unknown> | null>(null)

const currentDeliverable = computed(() =>
  deliverables.value.find((item) => item.id === selectedId.value) || null
)

const buildDownloadLink = buildDownloadLinkFor

const reload = async () => {
  await load()
  if (!deliverables.value.length) {
    selectedId.value = null
    currentDetails.value = null
    return
  }
  const previous = selectedId.value
  const exists = previous && deliverables.value.some((item) => item.id === previous)
  if (!exists) {
    selectedId.value = deliverables.value[0].id
  } else {
    await loadDetails()
  }
}

const loadDetails = async () => {
  if (!currentDeliverable.value) {
    currentDetails.value = null
    return
  }
  try {
    currentDetails.value = await fetchDeliverableData(currentDeliverable.value)
  } catch {
    currentDetails.value = null
  }
}

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) selectedId.value = id
}

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Playbook'
  const parts = item.id.split('/')
  const filename = parts[parts.length - 1]
  return filename.replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Playbook'
}

const formatDate = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const formatSize = (bytes: number) => {
  if (!bytes) return '0 KB'
  const units = ['B', 'KB', 'MB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(1)} ${units[index]}`
}

const formatWeek = (label: string | number) =>
  String(label).replace('_', ' ').replace(/\bweek\b/i, 'Semana')

watch(selectedId, loadDetails)
onMounted(reload)
</script>

<style scoped>
.workspace-playbooks {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.playbooks-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.playbooks-header h4 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.subtitle {
  margin: 4px 0 8px;
  font-size: 13px;
  color: #64748b;
}

.layer-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #64748b;
  text-transform: uppercase;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-weight: 600;
  cursor: pointer;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.12);
  color: #b91c1c;
  font-size: 14px;
}

.workspace-body {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 24px;
}

.deliverable-list {
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 20px;
}

.deliverable-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.deliverable-list li {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
}

.deliverable-list li.active {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(16, 185, 129, 0.08);
}

.deliverable-details {
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  padding: 24px;
}

.details-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 14px;
  padding: 16px;
}

.btn.ghost {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
  text-decoration: none;
  font-size: 13px;
}

.empty-container {
  border: 2px dashed rgba(148, 163, 184, 0.5);
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  color: #64748b;
}

.spinner {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid rgba(16, 185, 129, 0.2);
  border-top-color: #10b981;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .workspace-body { grid-template-columns: 1fr; }
}
</style>
