<template>
  <div class="perseo-workspace">
    <header class="workspace-header">
      <div>
        <h3>📢 Espacio de Trabajo – PERSEO</h3>
        <p class="subtitle">
          Generador automático de campañas, guiones y prompts IA listos para lanzar.
        </p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="reload">
        <i class="fas fa-sync-alt"></i>
        {{ isLoading ? 'Actualizando…' : 'Actualizar' }}
      </button>
    </header>

    <div v-if="error" class="error-banner">
      <i class="fas fa-exclamation-triangle"></i>
      <span>Hubo un problema al cargar los entregables: {{ error }}</span>
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
              <span class="tag">Guion</span>
              <span class="tag">Prompts IA</span>
              <span class="tag">Plan Difusión</span>
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
          <section class="card" v-if="currentDetails.video_script">
            <h5>🎬 Guion de Vídeo</h5>
            <p class="card-description">{{ currentDetails.video_script.goal }}</p>
            <ul class="script-list">
              <li v-for="segment in currentDetails.video_script.structure" :key="segment.segment">
                <span class="segment-title">{{ segment.segment }}</span>
                <span class="segment-copy">{{ segment.copy }}</span>
              </li>
            </ul>
            <div v-if="currentDetails.video_script.visual_notes" class="notes">
              <h6>Notas visuales</h6>
              <ul>
                <li v-for="note in currentDetails.video_script.visual_notes" :key="note">
                  {{ note }}
                </li>
              </ul>
            </div>
          </section>

          <section class="card" v-if="currentDetails.ai_prompts">
            <h5>🤖 Prompts para IA</h5>
            <div class="prompts">
              <div v-for="(data, platform) in currentDetails.ai_prompts" :key="platform" class="prompt">
                <div class="prompt-header">
                  <span class="prompt-platform">{{ formatPlatform(platform) }}</span>
                  <span class="prompt-target">{{ formatPlatformTarget(data) }}</span>
                </div>
                <code class="prompt-body">{{ formatPromptBody(data) }}</code>
              </div>
            </div>
          </section>

          <section class="card" v-if="currentDetails.distribution_plan">
            <h5>📣 Plan de Difusión</h5>
            <p class="card-description">
              Lanzamiento previsto el {{ currentDetails.distribution_plan.launch_date }}.
              Acciones por canal y automatizaciones listas.
            </p>
            <div class="channels">
              <div
                class="channel"
                v-for="(channel, name) in currentDetails.distribution_plan.channels"
                :key="name"
              >
                <h6>{{ formatPlatform(name) }}</h6>
                <ul>
                  <li v-if="channel.type"><strong>Formato:</strong> {{ channel.type }}</li>
                  <li v-if="channel.copy"><strong>Mensajes:</strong>
                    <ul>
                      <li v-for="line in channel.copy" :key="line">{{ line }}</li>
                    </ul>
                  </li>
                  <li v-if="channel.assets"><strong>Assets:</strong> {{ channel.assets.join(', ') }}</li>
                  <li v-if="channel.cta"><strong>CTA:</strong> {{ channel.cta }}</li>
                </ul>
              </div>
            </div>
            <div class="automation" v-if="currentDetails.distribution_plan.automation">
              <h6>Automatizaciones</h6>
              <ul>
                <li v-for="(desc, key) in currentDetails.distribution_plan.automation" :key="key">
                  <strong>{{ formatPlatform(key) }}:</strong> {{ desc }}
                </li>
              </ul>
            </div>
          </section>
        </div>
      </main>

      <main class="deliverable-details" v-else>
        <div class="empty-state">
          <div class="icon">🗂️</div>
          <h4>Selecciona un entregable</h4>
          <p>
            Haz clic en cualquiera de los entregables de la izquierda para visualizar el guion,
            prompts y plan de difusión.
          </p>
        </div>
      </main>
    </section>

    <section v-else class="empty-container">
      <div v-if="isLoading" class="empty-state">
        <div class="spinner"></div>
        <p>Generando entregables de marketing…</p>
      </div>
      <div v-else class="empty-state">
        <div class="icon">🕒</div>
        <h4>Sin entregables aún</h4>
        <p>
          Pide a PERSEO una acción desde el chat (“crea un vídeo de lanzamiento…”) y aparecerá aquí
          el paquete completo de activos listos para descargar.
        </p>
      </div>
    </section>

    <footer class="workspace-footer">
      <p>
        Consejo: cuando estés conforme, pulsa “Descargar Markdown” para exportar el briefing directo
        al equipo creativo o a tu IA de vídeo.
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
} = useAutomationDeliverables('PERSEO');

const selectedId = ref<string | null>(null);
const currentDetails = ref<any>(null);
const isLoadingDetails = ref(false);

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
  isLoadingDetails.value = true;
  try {
    currentDetails.value = await fetchDeliverableData(currentDeliverable.value);
  } catch (err) {
    console.error('Error cargando detalle de entregable', err);
    currentDetails.value = null;
  } finally {
    isLoadingDetails.value = false;
  }
};

const selectDeliverable = (id: string) => {
  if (selectedId.value !== id) {
    selectedId.value = id;
  }
};

const formatTitle = (item?: { id: string }) => {
  if (!item) return 'Entregable';
  const parts = item.id.split('/');
  const filename = parts[parts.length - 1];
  return filename.replace(/_/g, ' ').replace(/\d{8}T\d{6}Z$/, '').trim() || 'Campaña';
};

const formatDate = (timestamp: number) => {
  return new Date(timestamp * 1000).toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

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

const formatPlatform = (name: string | number) => String(name).replace(/_/g, ' ').toUpperCase();

const formatPlatformTarget = (value: any) => {
  if (value && typeof value === 'object') {
    if ('platform' in value) return value.platform;
    if ('voice' in value) return value.voice;
    if ('text' in value) return 'texto';
  }
  return 'prompt';
};

const formatPromptBody = (value: any) => {
  if (value && typeof value === 'object') {
    return value.prompt || value.text || JSON.stringify(value);
  }
  return String(value);
};

watch(selectedId, loadDetails);

onMounted(async () => {
  await reload();
});
</script>

<style scoped>
.perseo-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px 32px 48px;
  background: radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 55%);
  min-height: calc(100vh - 120px);
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

.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #b91c1c;
  font-size: 14px;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.08);
  color: #1d4ed8;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.15);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.workspace-body {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
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
  background: rgba(248, 250, 252, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.deliverable-list li.active {
  border-color: rgba(59, 130, 246, 0.45);
  background: rgba(59, 130, 246, 0.08);
  box-shadow: 0 6px 14px rgba(59, 130, 246, 0.1);
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
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
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
  border: 1px solid rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.05);
  color: #1d4ed8;
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
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card h5 {
  font-size: 18px;
  color: #0f172a;
  font-weight: 700;
}

.card-description {
  color: #475569;
  font-size: 14px;
}

.script-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.script-list li {
  background: rgba(59, 130, 246, 0.08);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.segment-title {
  font-weight: 700;
  color: #1d4ed8;
  font-size: 13px;
  text-transform: uppercase;
}

.segment-copy {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
}

.notes ul {
  margin: 0;
  padding-left: 20px;
  color: #475569;
}

.prompts {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.prompt {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  padding: 12px 14px;
  background: rgba(15, 118, 110, 0.05);
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #0f766e;
  font-weight: 600;
  margin-bottom: 8px;
}

.prompt-body {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: #0f172a;
  white-space: pre-wrap;
  display: block;
}

.channels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.channel {
  background: rgba(14, 116, 144, 0.05);
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(14, 116, 144, 0.2);
}

.channel h6 {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.channel ul,
.automation ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
}

.automation {
  margin-top: 12px;
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
  border: 4px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
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
  }

  .deliverable-details {
    padding: 20px;
  }
}

@media (max-width: 600px) {
  .perseo-workspace {
    padding: 20px 16px 80px;
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
