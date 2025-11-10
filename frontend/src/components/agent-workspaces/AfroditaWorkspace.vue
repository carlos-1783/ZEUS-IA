<template>
  <div class="afrodita-workspace">
    <header class="workspace-header">
      <div>
        <h3>🤝 Espacio de Trabajo – AFRODITA</h3>
        <p class="subtitle">
          Playbooks de soporte, onboarding y coordinación automatizados.
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
              v-if="currentDeliverable && currentDeliverable.files.json"
              :href="buildDownloadLink(currentDeliverable.files.json)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn ghost"
            >
              Descargar JSON
            </a>
            <a
              v-if="currentDeliverable && currentDeliverable.files.markdown"
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
            <div class="resources" v-if="currentDetails.onboarding_manual.resources?.length">
              <h6>Recursos</h6>
              <ul>
                <li v-for="resource in currentDetails.onboarding_manual.resources" :key="resource">
                  {{ resource }}
                </li>
              </ul>
            </div>
          </section>

          <section class="card" v-if="currentDetails.coordination_notes">
            <header class="card-header">
              <h5>🤝 Coordinación Multicanal</h5>
            </header>
            <div class="meetings">
              <h6>Ritmo de reuniones</h6>
              <ul>
                <li v-for="meeting in currentDetails.coordination_notes.meetings" :key="meeting.frequency">
                  <strong>{{ meeting.frequency }}</strong> · {{ meeting.participants.join(', ') }} →
                  {{ meeting.objective }}
                </li>
              </ul>
            </div>
            <div class="alerts" v-if="currentDetails.coordination_notes.alerts?.length">
              <h6>Alertas críticas</h6>
              <ul>
                <li v-for="alert in currentDetails.coordination_notes.alerts" :key="alert">
                  {{ alert }}
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
        <p>Generando playbook de soporte…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">🤝</div>
        <h4>Sin entregables disponibles</h4>
        <p>
          Solicita a AFRODITA un nuevo plan de soporte y aparecerá aquí automáticamente.
        </p>
      </div>
    </section>

    <footer class="workspace-footer">
      <p>
        Descarga el Markdown para compartir el playbook completo con tu equipo de customer success.
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue';
import { useAutomationDeliverables } from '@/composables/useAutomationDeliverables';

const {
  items: deliverables,
  isLoading,
  error,
  load,
  buildDownloadLinkFor,
  fetchDeliverableData,
} = useAutomationDeliverables('AFRODITA');

const selectedId = ref<string | null>(null);
const currentDetails = ref<any>(null);

const currentDeliverable = computed(() =>
  deliverables.value.find((item) => item.id === selectedId.value) || null
);

const buildDownloadLink = buildDownloadLinkFor;

const reload = async () => {
  await load();
  if (!deliverables.value.length) {
    selectedId.value = null;
    currentDetails.value = null;
    return;
  }
  const previous = selectedId.value;
  const exists = previous && deliverables.value.some((item) => item.id === previous);
  if (!exists) {
    selectedId.value = deliverables.value[0].id;
  } else {
    await loadDetails();
  }
};

const loadDetails = async () => {
  if (!currentDeliverable.value) {
    currentDetails.value = null;
    return;
  }
  try {
    currentDetails.value = await fetchDeliverableData(currentDeliverable.value);
  } catch (err) {
    console.error('Error cargando playbook de soporte', err);
    currentDetails.value = null;
  }
};

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) {
    selectedId.value = id;
  }
};

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Playbook';
  const parts = item.id.split('/');
  const filename = parts[parts.length - 1];
  return filename.replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Playbook';
};

const formatDate = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

const formatSize = (bytes: number) => {
  if (!bytes) return '0 KB';
  const units = ['B', 'KB', 'MB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(1)} ${units[index]}`;
};

const formatWeek = (label: string | number) =>
  String(label).replace('_', ' ').replace(/\bweek\b/i, 'Semana');

watch(selectedId, loadDetails);

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.afrodita-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 32px 48px 64px;
  background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 55%);
  min-height: calc(100vh - 96px);
  max-width: 1440px;
  width: min(1440px, calc(100% - 48px));
  margin: 0 auto 32px;
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.workspace-header h3 {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.workspace-header .subtitle {
  font-size: 15px;
  color: #475569;
  margin-top: 4px;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.18);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
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
  grid-template-columns: 360px 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 180px);
}

.deliverable-list {
  background: #ffffff;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 20px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.deliverable-list h4 {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.deliverable-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.deliverable-list li {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(248, 250, 252, 0.9);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.deliverable-list li.active {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(16, 185, 129, 0.12);
  box-shadow: 0 6px 14px rgba(16, 185, 129, 0.18);
}

.deliverable-list .title {
  font-weight: 600;
  color: #1e293b;
}

.deliverable-list .meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.deliverable-list .tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.tag.schedule {
  background: rgba(204, 251, 241, 0.9);
  color: #0f766e;
}

.tag.onboarding {
  background: rgba(187, 247, 208, 0.85);
  color: #047857;
}

.tag.coordination {
  background: rgba(233, 213, 255, 0.85);
  color: #6d28d9;
}

.deliverable-details {
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  padding: 28px;
  box-shadow: 0 18px 35px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.details-header h4 {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.details-meta {
  display: inline-block;
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
}

.details-summary {
  margin-top: 8px;
  color: #475569;
  font-size: 14px;
}

.details-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.15s;
}

.btn.ghost {
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.btn:hover {
  transform: translateY(-1px);
}

.details-grid {
  display: grid;
  gap: 20px;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 18px;
  padding: 22px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 55%);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card h5 {
  font-size: 18px;
  color: #0f172a;
  font-weight: 700;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.15);
  color: #047857;
  font-size: 12px;
  font-weight: 600;
}

.badge.teal {
  background: rgba(125, 211, 252, 0.25);
  color: #0c4a6e;
}

.schedule {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.week-block {
  background: rgba(224, 242, 241, 0.6);
  border-radius: 14px;
  padding: 14px 18px;
}

.week-block h6 {
  font-size: 15px;
  color: #0f766e;
  margin-bottom: 6px;
}

.week-block ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.modules {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.module {
  background: rgba(209, 250, 229, 0.65);
  border-radius: 14px;
  padding: 14px 16px;
}

.module h6 {
  font-size: 15px;
  color: #047857;
  margin-bottom: 6px;
}

.module ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.resources {
  margin-top: 12px;
}

.resources h6 {
  font-size: 14px;
  color: #0c4a6e;
  margin-bottom: 6px;
}

.resources ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.meetings ul,
.alerts ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.alerts h6,
.meetings h6 {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
}

.empty-container {
  background: rgba(248, 250, 252, 0.7);
  border: 2px dashed rgba(148, 163, 184, 0.5);
  border-radius: 20px;
  padding: 60px 30px;
  text-align: center;
  color: #475569;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.empty-state .icon {
  font-size: 42px;
}

.spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 4px solid rgba(16, 185, 129, 0.2);
  border-top-color: #10b981;
  animation: spin 1s linear infinite;
}

.workspace-footer {
  font-size: 13px;
  color: #64748b;
  text-align: center;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .workspace-body {
    grid-template-columns: 1fr;
    max-height: none;
  }
}

@media (max-width: 600px) {
  .afrodita-workspace {
    padding: 20px 16px 80px;
    min-height: auto;
  }

  .workspace-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .refresh-btn {
    width: 100%;
    justify-content: center;
  }

  .deliverable-list {
    padding: 16px;
  }

  .details-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .details-actions {
    width: 100%;
    gap: 8px;
  }
}
</style>

