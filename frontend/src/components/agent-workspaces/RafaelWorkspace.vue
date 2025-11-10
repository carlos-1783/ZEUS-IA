<template>
  <div class="rafael-workspace">
    <header class="workspace-header">
      <div>
        <h3>📊 Espacio de Trabajo – RAFAEL</h3>
        <p class="subtitle">Paquetes fiscales generados automáticamente (facturas, modelos y cashflow).</p>
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

    <section class="workspace-body" v-if="!isLoading && deliverables.length">
      <aside class="deliverable-list">
        <h4>Entregables</h4>
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
              <span class="tag">Factura</span>
              <span class="tag">Modelo 303/390</span>
              <span class="tag">Cashflow</span>
            </div>
          </li>
        </ul>
      </aside>

      <main class="deliverable-details" v-if="currentDetails">
        <header class="details-header">
          <div>
            <h4>{{ formatTitle(currentDeliverable ?? undefined) }}</h4>
            <span v-if="currentDeliverable" class="details-meta">Generado el {{ formatDate(currentDeliverable.createdAt) }}</span>
            <p v-if="currentDetails.summary" class="details-summary">{{ currentDetails.summary }}</p>
          </div>
          <div class="actions">
            <a
              v-if="currentDeliverable?.files.json"
              :href="buildDownloadLink(currentDeliverable.files.json)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn ghost"
            >JSON</a>
            <a
              v-if="currentDeliverable?.files.markdown"
              :href="buildDownloadLink(currentDeliverable.files.markdown)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn ghost"
            >Markdown</a>
          </div>
        </header>

        <div class="cards">
          <section class="card" v-if="currentDetails.invoice_template">
            <h5>🧾 Factura</h5>
            <p><strong>Concepto:</strong> {{ currentDetails.invoice_template.concept }}</p>
            <p><strong>Cliente:</strong> {{ currentDetails.invoice_template.customer }}</p>
            <p><strong>Fecha:</strong> {{ currentDetails.invoice_template.issue_date }}</p>
            <table class="data-table">
              <thead><tr><th>Descripción</th><th>Precio</th><th>IVA</th></tr></thead>
              <tbody>
                <tr v-for="item in currentDetails.invoice_template.items" :key="item.description">
                  <td>{{ item.description }}</td>
                  <td>{{ formatCurrency(item.price) }}</td>
                  <td>{{ item.tax }}%</td>
                </tr>
              </tbody>
            </table>
            <p class="note">{{ currentDetails.invoice_template.notes }}</p>
          </section>

          <section class="card" v-if="currentDetails.tax_models">
            <h5>💼 Modelos Fiscales</h5>
            <ul class="bullet">
              <li v-for="(model, code) in currentDetails.tax_models" :key="code">
                <strong>{{ String(code).toUpperCase() }}:</strong>
                <span v-if="model.quarter"> {{ model.quarter }}º trimestre.</span>
                <span v-if="model.year"> Año {{ model.year }}.</span>
                <span v-if="model.required_fields"> Campos: {{ model.required_fields.join(', ') }}.</span>
                <span v-if="model.notes"> {{ model.notes }}</span>
              </li>
            </ul>
          </section>

          <section class="card" v-if="currentDetails.cashflow_projection">
            <h5>📈 Cashflow</h5>
            <table class="data-table">
              <thead><tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Notas</th></tr></thead>
              <tbody>
                <tr v-for="row in currentDetails.cashflow_projection.months" :key="row.month">
                  <td>{{ row.month }}</td>
                  <td>{{ formatCurrency(row.expected_recurring) }}</td>
                  <td>{{ formatCurrency(row.expected_expenses) }}</td>
                  <td>{{ row.notes }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="currentDetails.cashflow_projection.alerts?.length" class="alert-block">
              <h6>Alertas</h6>
              <ul class="bullet">
                <li v-for="alert in currentDetails.cashflow_projection.alerts" :key="alert">{{ alert }}</li>
              </ul>
            </div>
          </section>
        </div>
      </main>

      <main class="deliverable-details" v-else>
        <div class="empty-state">
          <div class="icon">📂</div>
          <p>Elige un entregable para revisar el detalle generado por RAFAEL.</p>
        </div>
      </main>
    </section>

    <section v-else class="empty-container">
      <div v-if="isLoading" class="empty-state">
        <div class="spinner"></div>
        <p>Consultando documentación fiscal…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">🧾</div>
        <p>Solicita a RAFAEL una tarea para que aparezcan los entregables aquí.</p>
      </div>
    </section>
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
} = useAutomationDeliverables('RAFAEL');

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
  if (!selectedId.value || !deliverables.value.some((item) => item.id === selectedId.value)) {
    selectedId.value = deliverables.value[0].id;
  }
  await loadDetails();
};

const loadDetails = async () => {
  if (!currentDeliverable.value) {
    currentDetails.value = null;
    return;
  }
  try {
    currentDetails.value = await fetchDeliverableData(currentDeliverable.value);
  } catch (err) {
    console.error('Error cargando paquete fiscal', err);
    currentDetails.value = null;
  }
};

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) {
    selectedId.value = id;
  }
};

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Paquete fiscal';
  const parts = item.id.split('/');
  return parts[parts.length - 1].replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Paquete fiscal';
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

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(value ?? 0);

watch(selectedId, loadDetails);

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.rafael-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px 32px 48px;
  background: radial-gradient(circle at top left, rgba(245, 158, 11, 0.12), transparent 55%);
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

.subtitle {
  font-size: 15px;
  color: #475569;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  font-weight: 600;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.error-banner {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #b91c1c;
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
  background: rgba(248, 250, 252, 0.85);
  cursor: pointer;
  transition: 0.2s;
}

.deliverable-list li.active {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.1);
  box-shadow: 0 6px 14px rgba(245, 158, 11, 0.15);
}

.title {
  font-weight: 600;
  color: #1e293b;
}

.meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(254, 215, 170, 0.6);
  color: #9a3412;
  font-weight: 600;
}

.deliverable-details {
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  padding: 28px;
  box-shadow: 0 18px 35px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
  overflow-y: auto;
}

.details-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.details-meta {
  display: block;
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
}

.details-summary {
  margin-top: 8px;
  color: #475569;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  font-weight: 600;
  text-decoration: none;
}

.cards {
  display: grid;
  gap: 16px;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 16px;
  padding: 20px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 60%);
}

.card h5 {
  font-size: 17px;
  color: #0f172a;
  margin-bottom: 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
  font-size: 14px;
}

.data-table th,
.data-table td {
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 8px 10px;
  text-align: left;
}

.note {
  margin-top: 10px;
  font-size: 13px;
  color: #6b7280;
}

.bullet {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.alert-block {
  margin-top: 12px;
  background: rgba(254, 226, 226, 0.6);
  border-radius: 12px;
  padding: 12px 14px;
  color: #b91c1c;
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

.icon {
  font-size: 40px;
}

.spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 4px solid rgba(245, 158, 11, 0.2);
  border-top-color: #f59e0b;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .workspace-body {
    grid-template-columns: 1fr;
    max-height: none;
  }
}

@media (max-width: 600px) {
  .rafael-workspace {
    padding: 20px 16px 80px;
    min-height: auto;
  }

  .workspace-header {
    flex-direction: column;
    gap: 12px;
  }

  .actions {
    flex-wrap: wrap;
  }
}
</style>
