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
              <span v-if="fiscalTag(item)" class="tag">{{ fiscalTag(item) }}</span>
              <span v-if="item.fileUrl" class="tag tag-file">Archivo real</span>
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
              v-if="fiscalDownloadUrl"
              :href="fiscalDownloadUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="btn primary"
            >{{ fiscalDownloadLabel }}</a>
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

        <section v-if="currentDetails?.workspace_deliverable" class="card workspace-fiscal-card">
          <h5>📄 Documento fiscal</h5>
          <p v-if="workspaceFiscalSummary" class="fiscal-summary">{{ workspaceFiscalSummary }}</p>
          <p v-if="!fiscalDownloadUrl" class="note">
            Borrador sin archivo descargable. Regenera desde «Generar Excel 303» o genera el PDF de una factura.
          </p>
          <a
            v-if="fiscalDownloadUrl"
            :href="fiscalDownloadUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="btn primary"
          >{{ fiscalDownloadLabel }}</a>
        </section>

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

    <!-- Documentos Pendientes de Aprobación -->
    <section class="approval-section">
      <DocumentApprovalPanel />
    </section>
  </div>

  <RafaelToolsPanel />
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { API_BASE_URL } from '@/config/index';
import { useAutomationDeliverables, type DeliverableItem } from '@/composables/useAutomationDeliverables';
import RafaelToolsPanel from './RafaelToolsPanel.vue';
import DocumentApprovalPanel from '@/components/DocumentApprovalPanel.vue';

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

const selectDeliverable = async (id: string) => {
  selectedId.value = id;
  await loadDetails();
};

const formatTitle = (item?: DeliverableItem | null) => {
  if (!item) return 'Paquete fiscal';
  if (item.displayTitle) return item.displayTitle;
  const parts = item.id.split('/');
  return parts[parts.length - 1].replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Paquete fiscal';
};

const fiscalTag = (item: DeliverableItem) => {
  const t = (item.fiscalDocType || '').toLowerCase();
  if (t.includes('303')) return 'Modelo 303';
  if (t.includes('factura') || t === 'invoice') return 'Factura PDF';
  if (t.includes('390')) return 'Modelo 390';
  return item.fileUrl ? 'Fiscal' : '';
};

const workspaceFiscalContent = computed(() => {
  const payload = currentDetails.value?.payload as Record<string, unknown> | undefined;
  const content = (payload?.content || {}) as Record<string, unknown>;
  return content;
});

const fiscalDownloadUrl = computed(() => {
  const fromItem = currentDeliverable.value?.fileUrl;
  const fromContent = workspaceFiscalContent.value?.file_url;
  const raw = (fromItem || fromContent) as string | undefined;
  if (!raw) return '';
  if (raw.startsWith('http')) return raw;
  return `${API_BASE_URL}${raw.startsWith('/') ? raw : `/${raw}`}`;
});

const fiscalDownloadLabel = computed(() => {
  const mime = currentDeliverable.value?.mimeType || workspaceFiscalContent.value?.mime_type;
  if (typeof mime === 'string' && mime.includes('pdf')) return 'Descargar PDF';
  if (typeof mime === 'string' && mime.includes('spreadsheet')) return 'Descargar Excel 303';
  const url = fiscalDownloadUrl.value.toLowerCase();
  if (url.endsWith('.pdf')) return 'Descargar PDF';
  if (url.endsWith('.xlsx')) return 'Descargar Excel 303';
  return 'Descargar archivo';
});

const workspaceFiscalSummary = computed(() => {
  const c = workspaceFiscalContent.value;
  if (!c || typeof c !== 'object') return '';
  const parts: string[] = [];
  if (c.period) parts.push(`Periodo: ${c.period}`);
  if (c.iva_devengado != null) parts.push(`IVA devengado: ${c.iva_devengado} €`);
  if (c.iva_soportado != null) parts.push(`IVA soportado: ${c.iva_soportado} €`);
  if (c.resultado != null) parts.push(`Resultado: ${c.resultado} €`);
  if (c.total != null) parts.push(`Total: ${c.total} €`);
  return parts.join(' · ');
});

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

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.rafael-workspace {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 32px 48px 64px;
  background: radial-gradient(circle at top left, rgba(245, 158, 11, 0.12), transparent 55%);
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
.btn.primary {
  background: #d97706;
  border-color: #b45309;
  color: #fff;
}
.workspace-fiscal-card {
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 16px;
  padding: 20px;
  background: #fffbeb;
}
.fiscal-summary {
  color: #475569;
  font-size: 14px;
  margin: 8px 0 12px;
}
.tag-file {
  background: rgba(34, 197, 94, 0.2);
  color: #166534;
}

.cards {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
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
    padding: 24px 18px 80px;
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
