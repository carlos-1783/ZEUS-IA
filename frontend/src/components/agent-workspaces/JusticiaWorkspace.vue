<template>
  <div class="justicia-workspace">
    <header class="workspace-header">
      <div>
        <h3>⚖️ Espacio de Trabajo – JUSTICIA</h3>
        <p class="subtitle">
          Entregables legales automatizados: políticas, términos y checklist de cumplimiento.
        </p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="reload">
        <i class="fas fa-sync-alt"></i>
        {{ isLoading ? 'Actualizando…' : 'Actualizar' }}
      </button>
    </header>

    <div v-if="error" class="error-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <span>Error al cargar entregables legales: {{ error }}</span>
    </div>

    <section class="workspace-body" v-if="!isLoading && deliverables.length">
      <aside class="deliverable-list">
        <h4>Documentos generados</h4>
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
              <span class="tag policy">Política</span>
              <span class="tag terms">Términos</span>
              <span class="tag compliance">Checklist</span>
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
          <section class="card" v-if="currentDetails.privacy_policy">
            <header class="card-header">
              <h5>🔒 Política de Privacidad</h5>
              <span class="badge">RGPD Ready</span>
            </header>
            <p class="card-summary">{{ currentDetails.privacy_policy.overview }}</p>
            <div class="sections">
              <div
                v-for="section in currentDetails.privacy_policy.sections"
                :key="section.heading"
                class="section-block"
              >
                <h6>{{ section.heading }}</h6>
                <p>{{ section.content }}</p>
              </div>
            </div>
          </section>

          <section class="card" v-if="currentDetails.terms_of_service">
            <header class="card-header">
              <h5>📜 Términos de Servicio</h5>
              <span class="badge violet">Protección contractual</span>
            </header>
            <p class="card-summary">{{ currentDetails.terms_of_service.overview }}</p>
            <div class="sections">
              <div
                v-for="clause in currentDetails.terms_of_service.clauses"
                :key="clause.title"
                class="section-block"
              >
                <h6>{{ clause.title }}</h6>
                <p>{{ clause.body }}</p>
              </div>
            </div>
          </section>

          <section class="card" v-if="currentDetails.compliance_checklist">
            <header class="card-header">
              <h5>✅ Checklist de Cumplimiento</h5>
            </header>
            <ul class="checklist">
              <li
                v-for="item in currentDetails.compliance_checklist.items"
                :key="item.description"
              >
                <span class="state" :class="item.status">{{ formatStatus(item.status) }}</span>
                <span class="description">{{ item.description }}</span>
              </li>
            </ul>
            <div v-if="currentDetails.compliance_checklist.alerts?.length" class="alerts">
              <h6>Alertas legales</h6>
              <ul>
                <li v-for="alert in currentDetails.compliance_checklist.alerts" :key="alert">
                  {{ alert }}
                </li>
              </ul>
            </div>
          </section>
        </div>
      </main>

      <main class="deliverable-details" v-else>
        <div class="empty-state">
          <div class="icon">📚</div>
          <h4>Selecciona un entregable legal</h4>
          <p>Elige un paquete generado para revisar políticas y condiciones.</p>
        </div>
      </main>
    </section>

    <section v-else class="empty-container">
      <div v-if="isLoading" class="empty-state">
        <div class="spinner"></div>
        <p>Generando documentación legal…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">⚖️</div>
        <h4>Sin entregables disponibles</h4>
        <p>
          Solicita a JUSTICIA un nuevo paquete legal y aparecerá aquí listo para descargar.
        </p>
      </div>
    </section>

    <footer class="workspace-footer">
      <p>
        Descarga el Markdown para enviarlo a tu equipo legal o integrarlo en la web sin esfuerzo.
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
} = useAutomationDeliverables('JUSTICIA');

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
    console.error('Error cargando paquete legal', err);
    currentDetails.value = null;
  }
};

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) {
    selectedId.value = id;
  }
};

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Paquete legal';
  const parts = item.id.split('/');
  const filename = parts[parts.length - 1];
  return filename.replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Paquete legal';
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

const formatStatus = (status: string) => {
  if (!status) return 'Pendiente';
  const map: Record<string, string> = {
    completed: 'Completado',
    pending: 'Pendiente',
    review: 'Revisión',
  };
  return map[status.toLowerCase()] || status;
};

watch(selectedId, loadDetails);

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.justicia-workspace {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 32px 48px 64px;
  background: radial-gradient(circle at top right, rgba(129, 140, 248, 0.12), transparent 55%);
  min-height: calc(100vh - 96px);
  max-width: 98%;
  width: calc(100% - 24px);
  margin: 0 auto 24px;
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
  border: 1px solid rgba(129, 140, 248, 0.4);
  background: rgba(129, 140, 248, 0.12);
  color: #4338ca;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(129, 140, 248, 0.2);
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
  grid-template-columns: minmax(420px, 500px) minmax(0, 1fr);
  gap: 32px;
  flex: 1;
  min-height: 0;
  max-height: none;
  align-items: stretch;
}

.deliverable-list {
  background: #ffffff;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 28px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
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
  border-color: rgba(129, 140, 248, 0.45);
  background: rgba(129, 140, 248, 0.12);
  box-shadow: 0 6px 14px rgba(129, 140, 248, 0.2);
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

.tag.policy {
  background: rgba(165, 243, 252, 0.8);
  color: #0f766e;
}

.tag.terms {
  background: rgba(199, 210, 254, 0.85);
  color: #3730a3;
}

.tag.compliance {
  background: rgba(252, 231, 243, 0.8);
  color: #a21caf;
}

.deliverable-details {
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  padding: 32px;
  box-shadow: 0 18px 35px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-height: 0;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
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
  border: 1px solid rgba(129, 140, 248, 0.4);
  background: rgba(129, 140, 248, 0.12);
  color: #4338ca;
}

.btn:hover {
  transform: translateY(-1px);
}

.details-grid {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
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
  background: rgba(129, 140, 248, 0.2);
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
}

.badge.violet {
  background: rgba(196, 181, 253, 0.25);
  color: #6d28d9;
}

.card-summary {
  color: #475569;
  font-size: 14px;
}

.sections {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-block {
  background: rgba(227, 233, 255, 0.4);
  border-radius: 14px;
  padding: 14px 18px;
}

.section-block h6 {
  font-size: 15px;
  color: #1d4ed8;
  margin-bottom: 6px;
}

.section-block p {
  color: #475569;
  font-size: 14px;
}

.checklist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checklist li {
  display: flex;
  gap: 12px;
  align-items: center;
  background: rgba(236, 254, 255, 0.6);
  border-radius: 12px;
  padding: 12px 16px;
}

.state {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.state.completed {
  background: rgba(167, 243, 208, 0.9);
  color: #047857;
}

.state.pending {
  background: rgba(254, 226, 226, 0.9);
  color: #b91c1c;
}

.state.review {
  background: rgba(254, 249, 195, 0.9);
  color: #b45309;
}

.description {
  color: #475569;
  font-size: 14px;
}

.alerts {
  margin-top: 12px;
}

.alerts h6 {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
  color: #7c3aed;
}

.alerts ul {
  margin: 0;
  padding-left: 18px;
  color: #6b7280;
  font-size: 13px;
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
  border: 4px solid rgba(129, 140, 248, 0.2);
  border-top-color: #6366f1;
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
  .justicia-workspace {
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

