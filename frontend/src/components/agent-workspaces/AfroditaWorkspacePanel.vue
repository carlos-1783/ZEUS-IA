<template>
  <div class="afrodita-workspace-panel">
    <header class="panel-header">
      <div>
        <h4>📝 Workspace IA</h4>
        <p class="subtitle">
          Archivos y playbooks desde BD
          <span v-if="connected" class="conn-badge real">CONECTADO</span>
          <span v-else class="conn-badge sim">SIN CONEXIÓN</span>
        </p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="reload">
        <i class="fas fa-sync-alt"></i>
        {{ isLoading ? 'Actualizando…' : 'Actualizar' }}
      </button>
    </header>

    <div v-if="error" class="error-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <span>{{ error }}</span>
    </div>

    <section v-if="files.length" class="files-section">
      <h5>Archivos ({{ files.length }})</h5>
      <ul class="file-list">
        <li v-for="file in files" :key="file.id">
          <strong>{{ file.name }}</strong>
          <span class="meta">{{ formatDate(file.updated_at || file.created_at) }}</span>
          <p v-if="file.content" class="preview">{{ previewContent(file.content) }}</p>
        </li>
      </ul>
    </section>

    <div v-if="!isLoading && playbooks.length" class="workspace-body">
      <aside class="deliverable-list">
        <h4>Playbooks (BD)</h4>
        <ul>
          <li
            v-for="item in playbooks"
            :key="item.id"
            :class="{ active: item.id === selectedId }"
            @click="selectedId = item.id"
          >
            <div class="title">{{ item.title }}</div>
            <div class="meta">
              <span class="source-badge">{{ item.agent_source || 'afrodita' }}</span>
              <span>{{ formatDate(item.created_at) }}</span>
            </div>
          </li>
        </ul>
      </aside>

      <main class="deliverable-details" v-if="currentDetails">
        <header class="details-header">
          <div>
            <h4>{{ selectedPlaybook?.title }}</h4>
            <p v-if="currentDetails.summary" class="details-summary">{{ currentDetails.summary }}</p>
          </div>
        </header>

        <div class="details-grid">
          <section class="card" v-if="currentDetails.support_schedule">
            <header class="card-header">
              <h5>📅 Agenda de Soporte</h5>
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
              <ul>
                <li v-for="meeting in currentDetails.coordination_notes.meetings" :key="meeting.frequency">
                  <strong>{{ meeting.frequency }}</strong> · {{ meeting.participants.join(', ') }}
                </li>
              </ul>
            </div>
          </section>
        </div>
      </main>
    </div>

    <section v-else-if="!isLoading" class="empty-container">
      <div class="empty-state">
        <div class="icon">🤝</div>
        <h4>Sin playbooks en BD</h4>
        <p v-if="connected">Ejecuta una tarea AFRODITA para generar y persistir un playbook.</p>
        <p v-else>Workspace no conectado — verifique AFRODITA_WORKSPACE_ENABLED y la base de datos.</p>
      </div>
    </section>

    <div v-if="isLoading" class="empty-state">
      <div class="spinner"></div>
      <p>Cargando workspace…</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchAfroditaWorkspaceFiles,
  type AfroditaWorkspaceFile,
  type AfroditaWorkspacePlaybook,
} from '@/api/afrodita_workspace_api'
import { fetchWorkspacePlaybooks, type WorkspacePlaybookItem } from '@/api/workspace_playbooks_api'

const props = defineProps<{
  connected?: boolean
}>()

const files = ref<AfroditaWorkspaceFile[]>([])
const playbooks = ref<WorkspacePlaybookItem[]>([])
const selectedId = ref<number | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)
const connected = computed(() => props.connected ?? false)

const selectedPlaybook = computed(() =>
  playbooks.value.find((p) => p.id === selectedId.value) || null
)

const currentDetails = computed(() => selectedPlaybook.value?.content || null)

const reload = async () => {
  isLoading.value = true
  error.value = null
  try {
    const [filesRes, playbooksRes] = await Promise.all([
      fetchAfroditaWorkspaceFiles(),
      fetchWorkspacePlaybooks(),
    ])
    files.value = filesRes.files || []
    playbooks.value = playbooksRes.playbooks || []
    if (playbooks.value.length && !selectedId.value) {
      selectedId.value = playbooks.value[0].id
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    files.value = []
    playbooks.value = []
  } finally {
    isLoading.value = false
  }
}

const formatDate = (iso: string | null | undefined) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatWeek = (label: string | number) =>
  String(label).replace('_', ' ').replace(/\bweek\b/i, 'Semana')

const previewContent = (content: string) =>
  content.length > 120 ? `${content.slice(0, 120)}…` : content

onMounted(reload)
</script>

<style scoped>
.afrodita-workspace-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-header h4 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
}

.conn-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 6px;
}

.conn-badge.real { background: #dcfce7; color: #15803d; }
.conn-badge.sim { background: #fef3c7; color: #b45309; }

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

.files-section {
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 16px;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.file-list li {
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.preview {
  font-size: 12px;
  color: #64748b;
  margin: 4px 0 0;
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
}

.deliverable-list li {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
}

.deliverable-list li.active {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(16, 185, 129, 0.08);
}

.deliverable-list .meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.source-badge {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.12);
  color: #4338ca;
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
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .workspace-body { grid-template-columns: 1fr; }
}
</style>
