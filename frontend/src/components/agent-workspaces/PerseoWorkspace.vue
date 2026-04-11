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
          <section v-if="currentDetails?.workspace_deliverable" class="card workspace-persisted-card">
            <header class="card-header">
              <h5>📌 Anuncio / copy generado por PERSEO</h5>
              <span class="badge">Chat / API</span>
            </header>
            <p class="card-description">
              El <strong>texto</strong> es el entregable principal. La foto que subiste es solo
              <strong>referencia</strong>: PERSEO no sustituye esa imagen por un cartel nuevo (solo puede añadir un
              vídeo de presentación si está activo en el servidor).
            </p>
            <div class="workspace-ad">
              <h6>{{ workspaceAdTitle }}</h6>
              <p class="workspace-copy">{{ workspaceAdCopy }}</p>
              <div class="workspace-meta">
                <span class="meta-chip">CTA: {{ workspaceAdCta }}</span>
                <span class="meta-chip">Canales: {{ workspaceAdPlatforms }}</span>
              </div>
            </div>
            <details class="workspace-raw">
              <summary>Ver JSON completo</summary>
              <pre class="workspace-json">{{ formatWorkspacePayload(currentDetails.payload) }}</pre>
            </details>
          </section>

          <section
            v-if="currentDetails?.workspace_deliverable"
            class="card workspace-expectations-card"
          >
            <header class="card-header">
              <h5>📷 Imagen y vídeo (chat)</h5>
              <span class="badge">Qué hace este flujo</span>
            </header>
            <p class="card-description">
              La <strong>foto</strong> es <strong>referencia</strong> (no se sustituye por un cartel nuevo generado por
              IA). El entregable útil es el <strong>copy</strong> en el bloque “Anuncio / copy generado”. Con imagen en
              el mismo mensaje de chat, el backend intenta un <strong>vídeo de presentación</strong> (slides + texto) en
              MP4 o GIF en segundo plano; recarga el workspace en 30–90 s. Si no aparece, revisa variables
              <code>PERSEO_CHAT_AUTO_VIDEO</code> y logs del servidor (FFmpeg / memoria).
            </p>
            <p v-if="workspaceVideoUrl" class="card-description subtle-expectation">
              Has adjuntado un vídeo: no se genera un segundo MP4 automático.
            </p>
          </section>

          <section class="card tip-card" v-if="currentDeliverable">
            <header class="card-header">
              <h5>🎯 Activar entrega</h5>
              <span class="badge">Todo listo</span>
            </header>
            <p v-if="currentDetails?.workspace_deliverable" class="tip-body">
              Entregable desde <strong>chat / API</strong>: revisa copy y adjuntos. Para llevarlo a vídeo, exporta el
              briefing o copia el guion de abajo hacia tu editor o IA de vídeo.
              <template v-if="currentDeliverable.files.markdown">
                Si tienes export local, también puedes usar <strong>Descargar Markdown</strong>.
              </template>
            </p>
            <p v-else class="tip-body">
              Cuando estés conforme, pulsa <strong>“Descargar Markdown”</strong>. Obtendrás el briefing completo para
              pasarlo al equipo creativo o a tu IA de vídeo sin tocar nada más.
            </p>
          </section>

          <section v-if="workspaceMediaCardVisible" class="card media-card">
            <h5>🖼️ Medios y referencias</h5>
            <p class="card-description">
              El anuncio en texto está arriba. Aquí van la imagen que enviaste y, si aplica, un vídeo de presentación
              generado a partir del copy.
            </p>
            <div v-if="currentDetails?.workspace_deliverable" class="media-block media-generated-copy">
              <h6 class="media-block-title">Texto del anuncio (mismo copy que arriba)</h6>
              <p class="generated-copy-body">{{ workspaceAdCopy }}</p>
              <p class="generated-copy-meta">
                CTA: {{ workspaceAdCta }} · Canales: {{ workspaceAdPlatforms }}
              </p>
            </div>
            <div v-if="workspaceImageUrl" class="media-block">
              <h6 class="media-block-title">Tu imagen (referencia)</h6>
              <img
                :src="workspaceImageDisplayUrl"
                loading="lazy"
                class="media-image"
                alt="Imagen de referencia enviada al chat"
              />
              <p class="media-ref-caption">
                Es la misma foto que adjuntaste: sirve de contexto visual. No se convierte sola en un nuevo diseño
                gráfico.
              </p>
            </div>
            <div v-if="workspaceVideoUrl" class="media-block">
              <h6 class="media-block-title">Vídeo adjunto por ti</h6>
              <video
                v-show="!workspaceVideoLoadError"
                :key="workspaceVideoDisplayUrl"
                :src="workspaceVideoDisplayUrl"
                controls
                playsinline
                preload="metadata"
                class="media-video"
                @error="onWorkspaceVideoError"
              ></video>
              <div v-if="workspaceVideoLoadError" class="media-video-fallback">
                <p>No se pudo reproducir en el navegador (URL o red).</p>
                <a
                  :href="workspaceVideoDisplayUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn ghost"
                >
                  Abrir vídeo en nueva pestaña
                </a>
              </div>
            </div>
            <div v-if="workspacePdfUrl" class="media-block media-pdf">
              <h6 class="media-block-title">PDF</h6>
              <a :href="workspacePdfDisplayUrl" target="_blank" rel="noopener noreferrer" class="btn ghost">
                Abrir PDF
              </a>
            </div>
            <div v-if="generatedVideoPending" class="media-block media-pending">
              <h6 class="media-block-title">Vídeo de presentación</h6>
              <p class="pending-text">
                Generando MP4 o GIF a partir del copy… Actualiza la página en unos segundos.
              </p>
            </div>
            <div v-else-if="workspaceGeneratedVideoUrl" class="media-block">
              <h6 class="media-block-title">Vídeo generado (presentación)</h6>
              <video
                v-show="!generatedVideoLoadError"
                :key="workspaceGeneratedVideoDisplayUrl"
                :src="workspaceGeneratedVideoDisplayUrl"
                controls
                playsinline
                preload="metadata"
                class="media-video"
                @error="onGeneratedVideoError"
              ></video>
              <div v-if="generatedVideoLoadError" class="media-video-fallback">
                <a
                  :href="workspaceGeneratedVideoDisplayUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn ghost"
                >
                  Abrir vídeo en nueva pestaña
                </a>
              </div>
            </div>
            <div v-if="generatedVideoFailed" class="media-block media-failed">
              <h6 class="media-block-title">Vídeo automático</h6>
              <p class="failed-text">
                No se pudo generar (¿MoviePy/FFmpeg en el servidor?). {{ generatedVideoErrorHint }}
              </p>
            </div>
          </section>

          <section v-if="!currentDetails?.workspace_deliverable" class="card video-card">
            <h5>🎥 Montaje del vídeo</h5>
            <p class="card-description">
              Render automático generado por PERSEO listo para revisión y descarga.
            </p>
            <div class="video-status" :class="videoStatusClass">
              <span class="status-dot"></span>
              <span>{{ videoStatusLabel }}</span>
            </div>
            <video
              v-if="videoUrl && !isGifVideo"
              :src="videoUrl"
              controls
              playsinline
              preload="metadata"
              class="video-player"
            ></video>
            <img
              v-else-if="videoUrl && isGifVideo"
              :src="videoUrl"
              loading="lazy"
              class="video-gif"
              alt="Vídeo generado por PERSEO (GIF fallback)"
            />
            <div v-else class="video-empty">
              <i class="fas fa-video-slash"></i>
              <p>
                Aún no se ha adjuntado un archivo de vídeo a este entregable. Ejecuta PERSEO nuevamente o instala MoviePy + FFmpeg para habilitar la exportación automática.
              </p>
            </div>
            <div v-if="videoFile" class="video-meta">
              <span>{{ formatSize(videoFile.size_bytes) }}</span>
              <a
                :href="buildDownloadLink(videoFile)"
                target="_blank"
                rel="noopener noreferrer"
                class="btn ghost"
              >
                {{ videoDownloadLabel }}
              </a>
            </div>
          </section>

          <section class="card" v-if="videoScriptSegments.length">
            <h5>🎬 Guion de Vídeo</h5>
            <p v-if="currentDetails.video_script?.goal" class="card-description">
              {{ currentDetails.video_script.goal }}
            </p>
            <p v-else class="card-description">
              Escenas o tramos detectados en el texto de la campaña. Úsalos como guion en tu herramienta de vídeo; la
              imagen de arriba puede servir de referencia visual.
            </p>
            <ul class="script-list">
              <li v-for="(segment, idx) in videoScriptSegments" :key="`${segment.segment}-${idx}`">
                <span class="segment-title">{{ segment.segment }}</span>
                <span class="segment-copy">{{ segment.copy }}</span>
              </li>
            </ul>
            <div v-if="currentDetails.video_script?.visual_notes?.length" class="notes">
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

    <PerseoToolsPanel />

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
import type { AutomationOutput } from '@/api/automationService';
import { useAutomationDeliverables } from '@/composables/useAutomationDeliverables';
import { resolveWorkspaceMediaUrl } from '@/utils/resolveWorkspaceMediaUrl';
import PerseoToolsPanel from './PerseoToolsPanel.vue';

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
const workspacePayload = computed(() => (currentDetails.value?.payload || {}) as any);
const workspaceContent = computed(() => {
  const payload = workspacePayload.value || {};
  return payload.content && typeof payload.content === 'object' ? payload.content : {};
});
const workspaceImageUrl = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.image_url || '').trim() || '';
});
const workspaceVideoUrl = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.video_url || '').trim() || '';
});
const workspacePdfUrl = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.pdf_url || '').trim() || '';
});

const workspaceGeneratedVideoUrl = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.generated_video_url || '').trim() || '';
});
const generatedVideoStatus = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.generated_video_status || '').trim().toLowerCase();
});
const generatedVideoPending = computed(
  () => generatedVideoStatus.value === 'pending'
);
const generatedVideoFailed = computed(() => generatedVideoStatus.value === 'failed');
const generatedVideoErrorHint = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.generated_video_error || '').trim() || 'Revisa logs del backend.';
});

const workspaceMediaCardVisible = computed(() => {
  if (!currentDetails.value?.workspace_deliverable) {
    return false;
  }
  const hasCopy =
    Boolean(workspaceAdCopy.value) && workspaceAdCopy.value !== 'Sin copy disponible.';
  return Boolean(
    workspaceImageUrl.value ||
      workspaceVideoUrl.value ||
      workspacePdfUrl.value ||
      workspaceGeneratedVideoUrl.value ||
      generatedVideoPending.value ||
      generatedVideoFailed.value ||
      hasCopy
  );
});

const workspaceImageDisplayUrl = computed(() => resolveWorkspaceMediaUrl(workspaceImageUrl.value));
const workspaceVideoDisplayUrl = computed(() => resolveWorkspaceMediaUrl(workspaceVideoUrl.value));
const workspacePdfDisplayUrl = computed(() => resolveWorkspaceMediaUrl(workspacePdfUrl.value));
const workspaceGeneratedVideoDisplayUrl = computed(() =>
  resolveWorkspaceMediaUrl(workspaceGeneratedVideoUrl.value)
);

const workspaceVideoLoadError = ref(false);
const generatedVideoLoadError = ref(false);
watch(workspaceVideoDisplayUrl, () => {
  workspaceVideoLoadError.value = false;
});
watch(workspaceGeneratedVideoDisplayUrl, () => {
  generatedVideoLoadError.value = false;
});
const onWorkspaceVideoError = () => {
  workspaceVideoLoadError.value = true;
};
const onGeneratedVideoError = () => {
  generatedVideoLoadError.value = true;
};
const workspaceAdTitle = computed(() => {
  const p = workspacePayload.value || {};
  const raw = String(p.title || '').trim();
  const badPrefix = /^por supuesto|^claro|^aquí está/i.test(raw);
  if (!raw || badPrefix) {
    const copy = workspaceAdCopy.value;
    return copy.length > 80 ? `${copy.slice(0, 80).trim()}...` : (copy || 'Campaña');
  }
  return raw;
});
const workspaceAdCopy = computed(() => {
  const c = workspaceContent.value || {};
  const copy = c.copy || c.body || '';
  return String(copy).trim() || 'Sin copy disponible.';
});
const workspaceAdCta = computed(() => {
  const c = workspaceContent.value || {};
  return String(c.cta || 'Reserva ahora').trim();
});
const workspaceAdPlatforms = computed(() => {
  const c = workspaceContent.value || {};
  const arr = Array.isArray(c.platforms) ? c.platforms : [];
  return arr.length ? arr.join(', ') : 'instagram, facebook';
});

/** Tramos Inicio/Medio/Final extraídos en backend (workspace_deliverables) */
const workspaceChatVideoScript = computed(() => {
  const vs = (workspaceContent.value as Record<string, unknown>)?.video_script;
  if (!Array.isArray(vs)) return [];
  return vs.filter(
    (x: unknown) =>
      x &&
      typeof x === 'object' &&
      (String((x as { segment?: string }).segment || '').trim() ||
        String((x as { copy?: string }).copy || '').trim())
  ) as { segment?: string; copy?: string }[];
});

const videoScriptSegments = computed(() => {
  const json = currentDetails.value?.video_script;
  if (json?.structure && Array.isArray(json.structure) && json.structure.length) {
    return json.structure as { segment: string; copy: string }[];
  }
  return workspaceChatVideoScript.value.map((x) => ({
    segment: String(x.segment || 'Escena').trim() || 'Escena',
    copy: String(x.copy || '').trim(),
  }));
});

const videoAsset = computed(() => currentDetails.value?.video_asset ?? null);
const extractRelativePathFromAsset = (asset: any): string | null => {
  if (!asset) return null;
  if (asset.relative_path) {
    return String(asset.relative_path).replace(/\\/g, '/').replace(/^\/+/, '');
  }
  if (asset.download_path) {
    const normalized = String(asset.download_path).replace(/\\/g, '/');
    const marker = '/automation/outputs/';
    const lower = normalized.toLowerCase();
    const idx = lower.indexOf(marker);
    if (idx !== -1) {
      return normalized.slice(idx + marker.length);
    }
  }
  if (asset.path) {
    const normalized = String(asset.path).replace(/\\/g, '/');
    const marker = '/outputs/';
    const lower = normalized.toLowerCase();
    const idx = lower.indexOf(marker);
    if (idx !== -1) {
      return normalized.slice(idx + marker.length);
    }
  }
  return null;
};

const videoFile = computed<AutomationOutput | null>(() => {
  const files = currentDeliverable.value?.files.other ?? [];
  const existing = files.find((file) => /\.(mp4|webm|mov|m4v|gif)$/i.test(file.path));
  if (existing) {
    return existing;
  }
  const relativePath = extractRelativePathFromAsset(videoAsset.value);
  if (!relativePath) {
    return null;
  }
  const filename = videoAsset.value?.filename || relativePath.split('/').pop() || 'video.mp4';
  return {
    agent: currentDeliverable.value?.agent ?? 'PERSEO',
    filename,
    path: relativePath,
    size_bytes: videoAsset.value?.file_size ?? 0,
    created_at: currentDeliverable.value?.createdAt ?? Math.floor(Date.now() / 1000),
  };
});

const videoUrl = computed(() => (videoFile.value ? buildDownloadLink(videoFile.value) : ''));
const isGifVideo = computed(() => (videoFile.value ? /\.gif$/i.test(videoFile.value.path) : false));

const videoStatusLabel = computed(() => {
  const asset = videoAsset.value;
  if (!asset) {
    return videoFile.value
      ? 'Vídeo disponible para descarga.'
      : 'Generación pendiente. Ejecuta PERSEO para crear el recurso.';
  }
  if (asset.success === false) {
    return 'No se pudo generar el vídeo. Revisa dependencias (MoviePy + FFmpeg).';
  }
  if (asset.status === 'fallback_gif') {
    return 'GIF generado como fallback. Instala MoviePy + FFmpeg para exportar MP4.';
  }
  if (asset.status === 'generated') {
    return 'Vídeo MP4 generado automáticamente por PERSEO.';
  }
  return videoFile.value ? 'Vídeo disponible para descarga.' : 'Generación pendiente.';
});

const videoStatusClass = computed(() => {
  const asset = videoAsset.value;
  if (!asset) {
    return videoFile.value ? 'status-success' : 'status-warning';
  }
  if (asset.success === false) {
    return 'status-error';
  }
  if (asset.status === 'fallback_gif') {
    return 'status-warning';
  }
  return 'status-success';
});

const videoDownloadLabel = computed(() =>
  videoFile.value ? (isGifVideo.value ? 'Descargar GIF' : 'Descargar MP4') : ''
);

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
    const preferred =
      deliverables.value.find((item: any) => item.isWorkspace) || deliverables.value[0];
    selectedId.value = preferred.id;
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

const formatTitle = (item?: { id: string; displayTitle?: string }) => {
  if (!item) return 'Entregable';
  if (item.displayTitle) return item.displayTitle;
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

const formatWorkspacePayload = (payload: unknown) => {
  try {
    return JSON.stringify(payload ?? {}, null, 2);
  } catch {
    return String(payload);
  }
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
  gap: 28px;
  padding: 32px 48px 64px;
  background: radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 55%);
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
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
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

.tip-card {
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.15) 0%, #ffffff 65%);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.tip-body {
  color: #1d4ed8;
  font-size: 14px;
  line-height: 1.6;
}

.workspace-expectations-card {
  border-left: 4px solid #6366f1;
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.08) 0%, #ffffff 55%);
}

.subtle-expectation {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.card-description {
  color: #475569;
  font-size: 14px;
}

.video-card {
  padding-bottom: 26px;
}

.video-status {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 16px;
  width: fit-content;
}

.video-status .status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: currentColor;
}

.video-status.status-success {
  color: #16a34a;
  background: rgba(134, 239, 172, 0.2);
}

.video-status.status-warning {
  color: #d97706;
  background: rgba(251, 191, 36, 0.2);
}

.video-status.status-error {
  color: #dc2626;
  background: rgba(248, 113, 113, 0.2);
}

.video-player {
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #000;
  max-height: 520px;
  object-fit: cover;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
}

.video-gif {
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
  background: #0f172a;
  object-fit: contain;
}

.video-gif {
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
  background: #0f172a;
  object-fit: contain;
}

.media-card {
  border: 1px solid rgba(59, 130, 246, 0.2);
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, #ffffff 60%);
}

.media-image,
.media-video {
  width: 100%;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: #0f172a;
  max-height: 460px;
  object-fit: contain;
}

.media-video-fallback {
  padding: 16px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.06);
  border: 1px dashed rgba(148, 163, 184, 0.45);
  font-size: 14px;
  color: #475569;
}

.media-video-fallback p {
  margin: 0 0 12px;
}

.media-generated-copy {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(15, 23, 42, 0.08);
  margin-bottom: 4px;
}

.generated-copy-body {
  margin: 0;
  font-size: 15px;
  line-height: 1.55;
  color: #0f172a;
  white-space: pre-wrap;
}

.generated-copy-meta {
  margin: 10px 0 0;
  font-size: 13px;
  color: #475569;
}

.media-ref-caption {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}

.media-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.media-block-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.media-pending {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px dashed rgba(59, 130, 246, 0.35);
}

.pending-text {
  margin: 0;
  font-size: 14px;
  color: #1d4ed8;
}

.media-failed {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.failed-text {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
}

.media-pdf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.video-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
  font-size: 13px;
  color: #475569;
  gap: 12px;
}

.video-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 28px 20px;
  border-radius: 14px;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  background: rgba(248, 250, 252, 0.7);
  color: #475569;
  text-align: center;
}

.video-empty i {
  font-size: 32px;
  color: rgba(59, 130, 246, 0.6);
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

.workspace-persisted-card .workspace-json {
  margin: 0;
  padding: 16px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1.45;
  overflow-x: auto;
  max-height: 420px;
}

.workspace-ad h6 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #0f172a;
}

.workspace-copy {
  margin: 0;
  color: #1f2937;
  line-height: 1.5;
}

.workspace-meta {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-chip {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #1e40af;
}

.workspace-raw summary {
  cursor: pointer;
  margin-top: 10px;
  font-size: 12px;
  color: #475569;
}

@media (max-width: 900px) {
  .workspace-body {
    grid-template-columns: 1fr;
    max-height: none;
  }

  .deliverable-details {
    padding: 20px;
  }
}

@media (max-width: 600px) {
  .perseo-workspace {
    padding: 24px 18px 80px;
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

  .video-meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
