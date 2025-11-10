<template>
  <div class="thalos-workspace">
    <header class="workspace-header">
      <div>
        <h3>🛡️ Espacio de Trabajo – THALOS</h3>
        <p class="subtitle">
          Auditorías automáticas de seguridad, alertas y respaldos del sistema.
        </p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="reload">
        <i class="fas fa-sync-alt"></i>
        {{ isLoading ? 'Actualizando…' : 'Actualizar' }}
      </button>
    </header>

    <div v-if="error" class="error-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <span>Error al cargar reportes de seguridad: {{ error }}</span>
    </div>

    <section class="workspace-body" v-if="!isLoading && deliverables.length">
      <aside class="deliverable-list">
        <h4>Reportes</h4>
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
              <span class="tag audit">Auditoría</span>
              <span class="tag alerts">Alertas</span>
              <span class="tag backup">Backups</span>
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
            <p v-if="currentDetails.result" class="details-summary">{{ currentDetails.result }}</p>
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
          </div>
        </header>

        <div class="details-grid">
          <section class="card" v-if="currentDetails.checks">
            <header class="card-header">
              <h5>✅ Auditoría de Variables Críticas</h5>
              <span class="badge">{{ currentDetails.executed_at }}</span>
            </header>
            <table class="checks-table">
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(value, key) in currentDetails.checks" :key="key">
                  <td>{{ key }}</td>
                  <td>
                    <span :class="['pill', value ? 'ok' : 'missing']">
                      {{ value ? 'Configurada' : 'Faltante' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="currentDetails.missing?.length" class="missing">
              <h6>Variables faltantes</h6>
              <ul>
                <li v-for="item in currentDetails.missing" :key="item">{{ item }}</li>
              </ul>
            </div>
            <p class="recommendation">{{ currentDetails.recommendations }}</p>
          </section>

          <section class="card" v-if="currentDetails.configuration">
            <header class="card-header">
              <h5>📣 Configuración de Alertas</h5>
              <span class="badge blue">Monitor activo</span>
            </header>
            <div class="config-grid">
              <div v-for="(value, key) in currentDetails.configuration" :key="key">
                <strong>{{ formatKey(key) }}</strong>
                <span>{{ formatValue(value) }}</span>
              </div>
            </div>
            <div v-if="currentDetails.actions_performed" class="actions">
              <h6>Acciones automatizadas</h6>
              <ul>
                <li v-for="action in currentDetails.actions_performed" :key="action">
                  {{ action }}
                </li>
              </ul>
            </div>
          </section>

          <section class="card" v-if="currentDetails.backup_created !== undefined">
            <header class="card-header">
              <h5>🗄️ Gestión de Backups</h5>
              <span class="badge" :class="currentDetails.backup_created ? 'ok' : 'warn'">
                {{ currentDetails.backup_created ? 'Backup generado' : 'Backup pendiente' }}
              </span>
            </header>
            <ul class="backup-details">
              <li><strong>Origen disponible:</strong> {{ currentDetails.source_exists ? 'Sí' : 'No' }}</li>
              <li><strong>Ruta backup:</strong> {{ currentDetails.backup_path || 'No creado' }}</li>
              <li><strong>Notas:</strong> {{ currentDetails.notes }}</li>
            </ul>
          </section>
        </div>
      </main>

      <main class="deliverable-details" v-else>
        <div class="empty-state">
          <div class="icon">🛡️</div>
          <h4>Selecciona un reporte</h4>
          <p>Revisa auditorías, configuraciones de alertas o estados de backup.</p>
        </div>
      </main>
    </section>

    <section v-else class="empty-container">
      <div v-if="isLoading" class="empty-state">
        <div class="spinner"></div>
        <p>Analizando seguridad del sistema…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">🛡️</div>
        <h4>Sin reportes por ahora</h4>
        <p>Solicita a THALOS una auditoría o backup y aparecerá aquí el resultado.</p>
      </div>
    </section>

    <footer class="workspace-footer">
      <p>
        Revisa los reportes a diario y descarga el JSON para archivarlo en tu sistema SIEM.
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
} = useAutomationDeliverables('THALOS');

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
    console.error('Error cargando reporte de seguridad', err);
    currentDetails.value = null;
  }
};

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) {
    selectedId.value = id;
  }
};

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Reporte de seguridad';
  const parts = item.id.split('/');
  const filename = parts[parts.length - 1];
  return filename.replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Reporte de seguridad';
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

const formatKey = (key: string | number) => String(key).replace(/_/g, ' ').toUpperCase();
const formatValue = (value: unknown) => (typeof value === 'boolean' ? (value ? 'Sí' : 'No') : String(value));

watch(selectedId, loadDetails);

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.thalos-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px 32px 48px;
  background: radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 55%);
  min-height: calc(100vh - 120px);
  max-width: 1200px;
  margin: 0 auto;
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
  border: 1px solid rgba(14, 165, 233, 0.4);
  background: rgba(14, 165, 233, 0.12);
  color: #0369a1;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(14, 165, 233, 0.18);
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
  grid-template-columns: 320px 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 220px);
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
  border-color: rgba(14, 165, 233, 0.45);
  background: rgba(14, 165, 233, 0.12);
  box-shadow: 0 6px 14px rgba(14, 165, 233, 0.18);
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

.tag.audit {
  background: rgba(191, 219, 254, 0.9);
  color: #1d4ed8;
}

.tag.alerts {
  background: rgba(165, 243, 252, 0.9);
  color: #0f766e;
}

.tag.backup {
  background: rgba(254, 215, 170, 0.9);
  color: #9a3412;
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
  min-height: 0;
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
  color: #0369a1;
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
  border: 1px solid rgba(14, 165, 233, 0.45);
  background: rgba(14, 165, 233, 0.12);
  color: #0369a1;
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
  background: rgba(191, 219, 254, 0.6);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}

.badge.blue {
  background: rgba(165, 243, 252, 0.6);
  color: #0f766e;
}

.badge.ok {
  background: rgba(167, 243, 208, 0.9);
  color: #047857;
}

.badge.warn {
  background: rgba(254, 226, 226, 0.9);
  color: #b91c1c;
}

.checks-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.checks-table th,
.checks-table td {
  border: 1px solid rgba(148, 163, 184, 0.3);
  padding: 10px;
  text-align: left;
}

.checks-table th {
  background: rgba(248, 250, 252, 0.9);
  font-weight: 600;
}

.pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.pill.ok {
  background: rgba(167, 243, 208, 0.9);
  color: #047857;
}

.pill.missing {
  background: rgba(254, 226, 226, 0.9);
  color: #b91c1c;
}

.missing h6 {
  font-size: 14px;
  color: #b91c1c;
  margin-bottom: 6px;
}

.missing ul {
  margin: 0;
  padding-left: 18px;
  color: #b45309;
  font-size: 14px;
}

.recommendation {
  color: #0369a1;
  font-size: 13px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  font-size: 14px;
  color: #475569;
}

.actions ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.actions h6 {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
  color: #0369a1;
}

.backup-details {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
  list-style: disc;
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
  border: 4px solid rgba(14, 165, 233, 0.2);
  border-top-color: #0ea5e9;
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
  .thalos-workspace {
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

