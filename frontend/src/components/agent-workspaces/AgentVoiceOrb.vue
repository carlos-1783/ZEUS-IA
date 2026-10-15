<template>
  <section
    class="voice-orb"
    :class="[`is-${stage}`, { 'is-deployed': deployed }]"
    :aria-label="`Asistente de voz de ${agentLabel}`"
  >
    <!-- Sin cabecera propia: el encuadre y la identidad del agente (avatar/nombre/rol) son los de
         AgentActivityPanel.vue — un solo marco, una sola cabecera. El menú ⋮ de paneles vive ahí
         también y controla este componente por referencia (choosePanel/closePanel expuestos). -->

    <!-- El orbe es la pantalla de inicio: grande y centrado en reposo; se encoge y sube
         cuando hay algo que enseñar (respuesta del chat, panel elegido en el menú ⋮). -->
    <div class="orb-stage">
      <div class="orb" :aria-hidden="true">
        <span class="orb-ring r-outer-dash"></span>
        <span class="orb-ring r1"></span>
        <span class="orb-ring r2"></span>
        <span class="orb-ring r3"></span>
        <span class="orb-pulse p1"></span>
        <span class="orb-pulse p2"></span>
        <span class="orb-core">
          <img v-if="agent.image" :src="agent.image" :alt="agent.name" />
          <span class="orb-scan"></span>
        </span>
      </div>

      <div class="orb-eq" :class="{ live: stage === 'listening' || voice.speaking.value }" aria-hidden="true">
        <span v-for="n in 6" :key="n"></span>
      </div>

      <!-- Sin rótulo de saludo: si hay algo que decir (escuchando/trabajando/hablando) se dice ahí;
           en reposo, solo una pista breve de cómo empezar, nunca "Hola <nombre>". -->
      <div class="orb-copy" aria-live="polite">
        <template v-if="stage === 'listening'">
          <p class="orb-title">Escuchando…</p>
          <p class="orb-sub">{{ voice.transcript.value || 'Habla con normalidad; paro al terminar la frase.' }}</p>
        </template>
        <template v-else-if="stage === 'busy'">
          <p class="orb-title">{{ agentLabel }} está trabajando…</p>
          <p class="orb-sub">«{{ lastAsked }}»</p>
        </template>
        <template v-else-if="!deployed">
          <p class="orb-sub">{{ voice.supported ? 'Pulsa el micro para hablar' : 'Tu navegador no reconoce voz: usa ⌨️ para escribir' }}</p>
        </template>
        <p v-if="voice.speaking.value" class="orb-sub">Respondiendo en voz alta…</p>
      </div>
    </div>

    <p v-if="voiceError" class="orb-alert" role="alert">{{ voiceError }}</p>

    <!-- Deck: aquí se despliega TODO lo que el orbe abre — respuestas del chat (windows) y los
         paneles elegidos en el menú ⋮ (herramientas / actividad / métricas), con el mismo
         tratamiento visual de panel HUD. -->
    <div v-if="deployed" class="orb-deck">
      <TransitionGroup name="orb-win" tag="div" class="orb-windows">
        <article
          v-for="w in windows"
          :key="w.id"
          class="orb-win"
          :class="`kind-${w.kind}`"
          :role="w.kind === 'blocked' || w.kind === 'error' ? 'alert' : 'region'"
          :aria-label="w.title"
        >
          <header class="win-head">
            <div>
              <h4 class="win-title">{{ w.title }}</h4>
              <p class="win-source">{{ w.source }}</p>
            </div>
            <button type="button" class="win-close" @click="closeWindow(w.id)">OK, cerrar</button>
          </header>

          <p class="win-text">{{ w.text }}</p>

          <div v-if="w.figures.length" class="win-figures">
            <div v-for="f in w.figures" :key="f.label" class="win-figure">
              <span class="fig-value">{{ f.value }}</span>
              <span class="fig-label">{{ f.label }}</span>
            </div>
          </div>

          <dl v-if="w.rows.length" class="win-kv">
            <div v-for="(r, i) in w.rows" :key="`${r.label}-${i}`" class="kv-row">
              <dt>{{ r.label }}</dt>
              <dd>{{ r.value }}</dd>
            </div>
          </dl>

          <div v-for="t in w.tables" :key="t.title" class="win-table-wrap">
            <p class="win-table-title">{{ t.title }}</p>
            <table class="win-table">
              <thead>
                <tr><th v-for="c in t.columnLabels" :key="c" scope="col">{{ c }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in t.rows" :key="ri">
                  <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="t.more" class="win-more">y {{ t.more }} más</p>
          </div>

          <ul v-if="w.evidence.length" class="win-evidence">
            <li v-for="ev in w.evidence" :key="`${ev.kind}-${ev.id}`">
              <a :href="ev.url" :title="`${ev.agent} · ${ev.status}`" @click.prevent="openEvidenceLink(ev, w)">{{ ev.title }}</a>
            </li>
          </ul>

          <p v-if="w.nextStep" class="win-next">{{ w.nextStep }}</p>

          <div v-if="w.needsConfirmation" class="win-confirm">
            <button type="button" class="win-btn-confirm" :disabled="stage === 'busy'" @click="answerConfirmation(w, 'confirmar')">Confirmar</button>
            <button type="button" class="win-btn-cancel" :disabled="stage === 'busy'" @click="answerConfirmation(w, 'cancelar')">Cancelar</button>
          </div>
        </article>
      </TransitionGroup>

      <section v-if="activePanel" class="orb-panel">
        <header class="panel-head">
          <h4>{{ panelTitle }}</h4>
          <button type="button" class="win-close" @click="closePanel">OK, cerrar</button>
        </header>
        <div class="panel-body">
          <slot :name="`panel-${activePanel}`" />
        </div>
      </section>
    </div>

    <!-- Adjuntar imagen/factura/vídeo al siguiente mensaje (hoy: PERSEO la usa para generar el
         vídeo de presentación real). Mismo mecanismo verificado que antes vivía en la pestaña de
         Chat; se mueve aquí porque el orbe es ahora la única superficie de chat. -->
    <div v-if="supportsMediaAttachment" class="orb-attach-wrapper">
      <ImageUploader @uploaded="handleMediaUploaded" />
      <div v-if="mediaReferenceUrl" class="orb-attach-chip">
        <span>Medio adjunto (imagen / vídeo / PDF)</span>
        <a :href="mediaReferenceUrl" target="_blank" rel="noopener">Ver</a>
        <button type="button" class="chip-remove" @click="clearMediaReference">Quitar</button>
      </div>
    </div>

    <form v-if="typing" class="orb-type" @submit.prevent="sendTyped">
      <label class="sr-only" :for="inputId">Escribe a {{ agentLabel }}</label>
      <input
        :id="inputId"
        ref="typeInput"
        v-model="typed"
        type="text"
        autocomplete="off"
        :placeholder="`Escribe a ${agentLabel}…`"
        :disabled="stage === 'busy'"
      />
      <button type="submit" class="orb-type-send" :disabled="stage === 'busy' || !typed.trim()">Enviar</button>
    </form>

    <!-- Texto/Voz: voz por defecto (micro), el teclado siempre disponible sin perder nada. -->
    <footer class="orb-bar">
      <button
        type="button"
        class="orb-side-btn"
        aria-label="Enviar foto o factura a ZEUS"
        title="Foto / factura"
        @click="onPhoto"
      >
        📷
      </button>
      <input
        ref="photoInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        hidden
        @change="onPhotoChosen"
      />
      <button
        type="button"
        class="orb-mic"
        :class="{ live: stage === 'listening' }"
        :aria-pressed="stage === 'listening' ? 'true' : 'false'"
        :aria-label="stage === 'listening' ? 'Dejar de escuchar' : `Hablar con ${agentLabel}`"
        :disabled="stage === 'busy'"
        @click="toggleMic"
      >
        <span aria-hidden="true">🎙️</span>
      </button>
      <button
        type="button"
        class="orb-side-btn"
        :aria-pressed="typing ? 'true' : 'false'"
        aria-label="Escribir en lugar de hablar"
        title="Escribir"
        @click="toggleTyping"
      >
        ⌨️
      </button>
    </footer>
    <p class="orb-bar-hint">{{ typing ? 'Texto · escribe y pulsa Enviar' : 'Voz · pulsa el micro y habla' }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useJarvisVoice } from '@/composables/useJarvisVoice';
import { getAgentChatUrl, AGENT_CHAT_TIMEOUT_MS, openEvidence, type ChatEvidence } from '@/utils/chatApi';
import {
  windowsForChatResponse,
  windowForHttpError,
  errorWindow,
  sourceLabel,
  windowForInboxItem,
  type JarvisWindow,
} from '@/utils/jarvisWindows';
import { API_BASE_URL } from '@/config';
import ImageUploader from '@/components/ImageUploader.jsx';

const props = defineProps<{
  agent: { name: string; role?: string; image?: string };
  /** Título del panel abierto desde el menú ⋮ (herramientas/actividad/métricas), si hay uno. */
  panelTitles?: Record<string, string>;
}>();

const emit = defineEmits<{
  (e: 'panel-opened', key: 'tools' | 'activity' | 'metrics'): void;
  (e: 'panel-closed', key: 'tools' | 'activity' | 'metrics'): void;
}>();

const authStore = useAuthStore();

// Mismo hilo que el resto del workspace: una confirmación pendiente se puede cerrar desde aquí.
const THREAD_ID = 'main';
const MIN_INTERVAL_MS = 3000; // límite anti-429

const windows = ref<JarvisWindow[]>([]);
const busy = ref(false);
const lastAsked = ref('');
const typing = ref(false);
const typed = ref('');
const typeInput = ref<HTMLInputElement | null>(null);
const localError = ref('');
let lastSentAt = 0;

const inputId = `orb-input-${Math.random().toString(36).slice(2, 8)}`;

const voice = useJarvisVoice({
  continuous: false,
  rate: 0.95,
  onFinal: (text) => send(text, 'voice'),
});

const agentLabel = computed(() => {
  const n = String(props.agent?.name || 'Agente');
  return n.split(' ')[0].charAt(0).toUpperCase() + n.split(' ')[0].slice(1).toLowerCase();
});

const stage = computed<'idle' | 'listening' | 'busy'>(() => {
  if (busy.value) return 'busy';
  if (voice.listening.value) return 'listening';
  return 'idle';
});

const voiceError = computed(() => localError.value || voice.error.value);

// --------------------------------------------------------------------- panel desplegado (menú ⋮ en AgentActivityPanel.vue)

const activePanel = ref<'tools' | 'activity' | 'metrics' | null>(null);

function choosePanel(key: 'tools' | 'activity' | 'metrics'): void {
  if (activePanel.value === key) {
    activePanel.value = null;
    emit('panel-closed', key);
    return;
  }
  const previous = activePanel.value;
  activePanel.value = key;
  if (previous) emit('panel-closed', previous);
  emit('panel-opened', key);
}

function closePanel(): void {
  const key = activePanel.value;
  activePanel.value = null;
  if (key) emit('panel-closed', key);
}

const panelTitle = computed(() => {
  const k = activePanel.value;
  if (!k) return '';
  return props.panelTitles?.[k] || { tools: 'Herramientas', activity: 'Actividad', metrics: 'Métricas' }[k];
});

/** El orbe se encoge y aparece el deck si hay respuesta de chat, un panel del menú abierto, o está ocupado. */
const deployed = computed(() => windows.value.length > 0 || activePanel.value !== null || stage.value === 'busy');

function token(): string | null {
  return (authStore as any).getToken?.() ?? (authStore as any).token ?? null;
}

async function send(raw: string, channel: 'voice' | 'text'): Promise<void> {
  const message = String(raw || '').trim();
  if (!message || busy.value) return;
  const now = Date.now();
  if (now - lastSentAt < MIN_INTERVAL_MS) {
    localError.value = 'Espera unos segundos entre mensajes.';
    return;
  }
  lastSentAt = now;
  localError.value = '';
  voice.stop();
  voice.cancel();
  lastAsked.value = message;
  busy.value = true;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AGENT_CHAT_TIMEOUT_MS);
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const t = token();
    if (t) headers.Authorization = `Bearer ${t}`;
    // El servidor resuelve empresa y usuario desde la sesión: no se envía company_id.
    const context: Record<string, string> = { channel };
    if (supportsMediaAttachment.value && mediaReferenceUrl.value) {
      context[mediaContextKey.value] = mediaReferenceUrl.value;
    }
    const res = await fetch(getAgentChatUrl(props.agent.name), {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, thread_id: THREAD_ID, context }),
      signal: controller.signal,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status !== 403 && res.status !== 501 && res.status !== 503) lastSentAt = 0;
      showWindows([windowForHttpError(res.status, body, props.agent.name)]);
      return;
    }
    const wins = windowsForChatResponse(body, props.agent.name);
    showWindows(wins);
    // Solo se lee en voz alta si se preguntó por voz; nunca las URLs de la evidencia.
    if (channel === 'voice' && wins[0]?.text) voice.speak(wins[0].text);
  } catch (err: any) {
    lastSentAt = 0;
    const text =
      err?.name === 'AbortError'
        ? 'Tiempo de espera agotado. No sé si la petición llegó a procesarse; revisa la actividad antes de repetirla.'
        : /failed to fetch|networkerror|load failed/i.test(String(err?.message || ''))
          ? 'No se pudo contactar con el servidor. Comprueba la conexión.'
          : String(err?.message || 'Error desconocido.');
    showWindows([errorWindow('No se pudo completar', sourceLabel(props.agent.name), text)]);
  } finally {
    clearTimeout(timer);
    busy.value = false;
  }
}

function showWindows(wins: JarvisWindow[]): void {
  // Las respuestas nuevas aparecen arriba; las anteriores siguen abiertas hasta "OK, cerrar".
  windows.value = [...wins, ...windows.value].slice(0, 6);
}

function closeWindow(id: string): void {
  windows.value = windows.value.filter((w) => w.id !== id);
  if (!windows.value.length) voice.cancel();
}

/** Confirmar/Cancelar con un clic explícito: mismo hilo, canal texto. La voz nunca salta esta confirmación. */
async function answerConfirmation(w: JarvisWindow, word: 'confirmar' | 'cancelar'): Promise<void> {
  w.needsConfirmation = false;
  lastSentAt = 0;
  closeWindow(w.id);
  await send(word, 'text');
}

async function openEvidenceLink(ev: ChatEvidence, w: JarvisWindow): Promise<void> {
  try {
    await openEvidence(ev, token());
  } catch (err: any) {
    showWindows([errorWindow(`No se pudo abrir «${ev.title}»`, w.source, String(err?.message || err))]);
  }
}

function toggleMic(): void {
  localError.value = '';
  if (voice.listening.value) {
    voice.stop();
    return;
  }
  if (!voice.supported) {
    localError.value = voice.unsupportedMessage.value;
    typing.value = true;
    nextTick(() => typeInput.value?.focus());
    return;
  }
  voice.start();
}

function toggleTyping(): void {
  typing.value = !typing.value;
  if (typing.value) {
    voice.stop();
    nextTick(() => typeInput.value?.focus());
  }
}

async function sendTyped(): Promise<void> {
  const text = typed.value;
  if (!text.trim()) return;
  typed.value = '';
  await send(text, 'text');
}

/**
 * Adjuntar imagen/vídeo/PDF al SIGUIENTE mensaje del chat. Hoy solo PERSEO lo usa: con imagen +
 * mensaje en el mismo hilo, el backend genera en segundo plano un vídeo de presentación real
 * (ver services/perseo_chat_video_job.py). Mismo contrato (`context.image_url/video_url/pdf_url`)
 * que ya estaba verificado end-to-end antes de mover esto aquí desde la antigua pestaña de Chat.
 */
const isPerseoAgent = computed(() => (props.agent?.name || '').toUpperCase().includes('PERSEO'));
const supportsMediaAttachment = isPerseoAgent;
const mediaReferenceUrl = ref<string | null>(null);
const mediaUploadedAwaitingPrompt = ref(false);

const mediaContextKey = computed<'pdf_url' | 'video_url' | 'image_url'>(() => {
  const u = mediaReferenceUrl.value || '';
  if (/\.pdf($|\?)/i.test(u) || u.includes('/documents/')) return 'pdf_url';
  if (/\.(mp4|webm|mov|m4v)($|\?)/i.test(u) || u.includes('/videos/')) return 'video_url';
  return 'image_url';
});

function handleMediaUploaded(payload: { url?: string } | undefined): void {
  mediaReferenceUrl.value = payload?.url || null;
  mediaUploadedAwaitingPrompt.value = Boolean(payload?.url);
}

function clearMediaReference(): void {
  mediaReferenceUrl.value = null;
  mediaUploadedAwaitingPrompt.value = false;
}

/**
 * 📷 Foto / factura estilo WhatsApp: la recibe ZEUS (POST /api/v1/zeus/inbox), la guarda en R2, la
 * clasifica con visión y la reparte para revisión humana (factura/ticket -> RAFAEL, nómina/albarán/
 * pedido -> AFRODITA, contrato -> JUSTICIA). La ventana muestra solo lo que el servidor leyó; si falta
 * R2 u OPENAI_API_KEY el servidor responde 503 y se enseña el bloqueo tal cual. Empresa: la de la sesión.
 */
const photoInput = ref<HTMLInputElement | null>(null);
const MAX_PHOTO_BYTES = 15 * 1024 * 1024;

function onPhoto(): void {
  if (busy.value) return;
  photoInput.value?.click();
}

async function onPhotoChosen(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file || busy.value) return;
  if (file.size > MAX_PHOTO_BYTES) {
    showWindows([errorWindow('Archivo demasiado grande', sourceLabel('ZEUS'), 'El máximo son 15 MB.')]);
    return;
  }
  voice.stop();
  voice.cancel();
  lastAsked.value = `📷 ${file.name}`;
  busy.value = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AGENT_CHAT_TIMEOUT_MS);
  try {
    const headers: Record<string, string> = {};
    const t = token();
    if (t) headers.Authorization = `Bearer ${t}`;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE_URL.replace(/\/+$/, '')}/zeus/inbox`, {
      method: 'POST',
      headers,
      body: form,
      signal: controller.signal,
    });
    const body = await res.json().catch(() => ({}));
    if (res.ok && body?.item) {
      showWindows([windowForInboxItem(body.item)]);
    } else if (body?.item) {
      // 502/503 con el documento guardado como pendiente de clasificar.
      showWindows([windowForInboxItem(body.item, body.detail)]);
    } else {
      showWindows([windowForHttpError(res.status, body, 'ZEUS')]);
    }
  } catch (err: any) {
    const text =
      err?.name === 'AbortError'
        ? 'Tiempo de espera agotado. Revisa la bandeja de ZEUS antes de volver a enviarla.'
        : 'No se pudo enviar la foto. Comprueba la conexión.';
    showWindows([errorWindow('No se pudo enviar', sourceLabel('ZEUS'), text)]);
  } finally {
    clearTimeout(timer);
    busy.value = false;
  }
}

defineExpose({ closePanel, choosePanel, activePanel });
</script>

<style scoped>
.voice-orb {
  --orb-a: var(--violet, var(--zeus-accent, #6a5cff));
  --orb-b: var(--blue, var(--zeus-info, #5b8cff));
  --orb-c: var(--teal, #36c6c6);
  --orb-panel: var(--panel, var(--zeus-surface, #ffffff));
  --orb-panel-2: var(--panel-2, #f3f5f9);
  --orb-line: var(--line, var(--zeus-border, rgba(20, 28, 56, 0.1)));
  --orb-fg: var(--fg, var(--zeus-text, #141a2b));
  --orb-muted: var(--muted, var(--zeus-text-secondary, #56607a));
  --orb-faint: var(--faint, var(--zeus-text-muted, #8891a6));
  --orb-amber: var(--amber, var(--zeus-warning, #f5a623));
  --orb-red: var(--red, var(--zeus-danger, #ff5d6c));
  --orb-size: 340px;
  --orb-stage-min-h: 420px;

  /* Sin tarjeta propia: este componente vive DENTRO del único encuadre platino de
     AgentActivityPanel.vue (.activity-panel) — sin borde/fondo/sombra/radio propios,
     para no duplicar esa tarjeta ("doble marco"). */
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 4px 4px 8px;
  color: var(--orb-fg);
  font-family: var(--zeus-font-sans, inherit);
}

/* Rejilla HUD sutil de fondo, solo mientras el orbe está en reposo grande (pantalla principal). */
.voice-orb::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.45;
  background-image:
    linear-gradient(color-mix(in srgb, var(--orb-a) 7%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--orb-a) 7%, transparent) 1px, transparent 1px);
  background-size: 34px 34px;
  mask: radial-gradient(circle at 50% 30%, #000 0%, transparent 72%);
  -webkit-mask: radial-gradient(circle at 50% 30%, #000 0%, transparent 72%);
  transition: opacity 400ms ease;
}

.voice-orb.is-deployed::before {
  opacity: 0.15;
}

.orb-side-btn:focus-visible,
.orb-mic:focus-visible,
.win-close:focus-visible {
  outline: none;
  box-shadow: var(--zeus-shadow-focus, 0 0 0 3px rgba(106, 92, 255, 0.3));
}

/* ------------------------------------------------------------------ escenario del orbe */
.orb-stage {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: var(--orb-stage-min-h);
  justify-content: center;
  padding-top: 4px;
  transition: min-height 420ms cubic-bezier(0.3, 0.1, 0.2, 1);
}

.voice-orb.is-deployed .orb-stage {
  --orb-stage-min-h: 0px;
  min-height: 0;
  padding-top: 6px;
  gap: 6px;
}

.orb {
  position: relative;
  width: var(--orb-size);
  height: var(--orb-size);
  transition: width 420ms cubic-bezier(0.3, 0.1, 0.2, 1), height 420ms cubic-bezier(0.3, 0.1, 0.2, 1);
}

.voice-orb.is-deployed .orb {
  --orb-size: 92px;
}

.orb-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1.5px solid color-mix(in srgb, var(--orb-a) 35%, transparent);
  animation: orb-breathe 4.8s ease-in-out infinite;
}

.orb-ring.r-outer-dash {
  inset: -4%;
  border: 1.5px dashed color-mix(in srgb, var(--orb-a) 28%, transparent);
  animation: orb-spin 48s linear infinite;
}

.orb-ring.r1 {
  animation: orb-spin 24s linear infinite reverse, orb-breathe 4.8s ease-in-out infinite;
}

.orb-ring.r2 {
  inset: 9%;
  border-color: color-mix(in srgb, var(--orb-b) 45%, transparent);
  animation-delay: -1.6s;
}

.orb-ring.r3 {
  inset: 18%;
  border: 2px solid transparent;
  background:
    conic-gradient(from 0deg, var(--orb-a), var(--orb-b), var(--orb-c), var(--orb-a)) border-box;
  -webkit-mask: linear-gradient(#000 0 0) padding-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: orb-spin 14s linear infinite;
}

.orb-pulse {
  position: absolute;
  inset: 22%;
  border-radius: 50%;
  border: 1.5px solid color-mix(in srgb, var(--orb-a) 55%, transparent);
  opacity: 0;
  animation: orb-pulse-ring 3.2s ease-out infinite;
}

.orb-pulse.p2 {
  animation-delay: -1.6s;
}

.orb-core {
  position: absolute;
  inset: 27%;
  border-radius: 50%;
  overflow: hidden;
  background: var(--orb-panel-2);
  box-shadow: 0 0 0 3px var(--orb-panel), 0 8px 28px color-mix(in srgb, var(--orb-a) 35%, transparent);
  animation: orb-glow 6.5s ease-in-out infinite;
}

.orb-core img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  animation: orb-breathe-img 6.5s ease-in-out infinite;
}

/* Barrido de escaneo sobre el avatar, como un sensor pasando — motivo de la referencia aprobada. */
.orb-scan {
  position: absolute;
  left: -10%;
  right: -10%;
  height: 40%;
  pointer-events: none;
  mix-blend-mode: screen;
  background: linear-gradient(
    180deg,
    transparent,
    color-mix(in srgb, var(--orb-b) 55%, transparent) 48%,
    color-mix(in srgb, var(--orb-c) 70%, white 10%) 50%,
    color-mix(in srgb, var(--orb-b) 55%, transparent) 52%,
    transparent
  );
  animation: orb-scan 4.6s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.voice-orb.is-listening .orb-ring,
.voice-orb.is-listening .orb-pulse {
  animation-duration: 1.1s;
}

.voice-orb.is-busy .orb-ring.r3 {
  animation-duration: 2.4s;
}

.orb-eq {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 28px;
  opacity: 0.85;
  transition: height 300ms ease, opacity 300ms ease;
}

.voice-orb.is-deployed .orb-eq {
  height: 0;
  opacity: 0;
  overflow: hidden;
}

.orb-eq span {
  width: 4px;
  border-radius: 2px;
  background: linear-gradient(var(--orb-a), var(--orb-b));
  opacity: 0.5;
  height: 8px;
}

.orb-eq span:nth-child(1) { height: 8px; }
.orb-eq span:nth-child(2) { height: 16px; }
.orb-eq span:nth-child(3) { height: 22px; }
.orb-eq span:nth-child(4) { height: 13px; }
.orb-eq span:nth-child(5) { height: 19px; }
.orb-eq span:nth-child(6) { height: 10px; }

.orb-eq.live span {
  opacity: 1;
  animation: orb-eq-beat 1s ease-in-out infinite;
}

.orb-eq.live span:nth-child(2n) { animation-delay: -0.3s; }
.orb-eq.live span:nth-child(3n) { animation-delay: -0.55s; }

.orb-copy {
  text-align: center;
  max-width: 460px;
  min-height: 1px;
}

.orb-title {
  margin: 0;
  font-size: var(--zeus-text-lg, 20px);
  font-weight: var(--zeus-weight-semibold, 600);
}

.orb-sub {
  margin: 4px 0 0;
  color: var(--orb-muted);
  font-size: var(--zeus-text-sm, 13px);
  overflow-wrap: anywhere;
}

.orb-alert {
  position: relative;
  z-index: 2;
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: color-mix(in srgb, var(--orb-amber) 14%, var(--orb-panel));
  color: var(--orb-fg);
  font-size: var(--zeus-text-sm, 13px);
}

/* ------------------------------------------------------------------ deck: todo lo que se despliega */
.orb-deck {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 760px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  animation: orb-deploy 420ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.orb-windows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.orb-win,
.orb-panel {
  position: relative;
  border: 1px solid var(--orb-line);
  border-radius: var(--zeus-radius, 12px);
  background: var(--orb-panel);
  padding: 14px 16px;
  box-shadow: var(--zeus-shadow, 0 1px 3px rgba(15, 23, 42, 0.06));
}

/* Corchetes HUD en las esquinas de cada panel desplegado, eco discreto de la referencia. */
.orb-win::before,
.orb-win::after,
.orb-panel::before,
.orb-panel::after {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  border: 1.5px solid color-mix(in srgb, var(--orb-a) 55%, transparent);
  opacity: 0.6;
  pointer-events: none;
}

.orb-win::before,
.orb-panel::before {
  top: 6px;
  left: 6px;
  border-right: none;
  border-bottom: none;
  border-radius: 4px 0 0 0;
}

.orb-win::after,
.orb-panel::after {
  bottom: 6px;
  right: 6px;
  border-left: none;
  border-top: none;
  border-radius: 0 0 4px 0;
}

.orb-win.kind-blocked {
  border: 1.5px solid var(--orb-amber);
  background: color-mix(in srgb, var(--orb-amber) 8%, var(--orb-panel));
}

.orb-win.kind-error {
  border-color: color-mix(in srgb, var(--orb-red) 55%, transparent);
}

.win-head,
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.panel-head h4,
.win-title {
  margin: 0;
  font-size: var(--zeus-text-base, 15px);
  font-weight: var(--zeus-weight-semibold, 600);
}

.win-source {
  margin: 2px 0 0;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-faint);
}

.win-close {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: var(--zeus-radius-full, 999px);
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  color: var(--orb-fg);
  font-size: var(--zeus-text-sm, 13px);
  cursor: pointer;
}

.panel-body {
  margin-top: 10px;
  max-height: min(60vh, 560px);
  overflow: auto;
}

.win-text {
  margin: 10px 0 0;
  font-size: var(--zeus-text-base, 15px);
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.win-figures {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.win-figure {
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: var(--orb-panel-2);
}

.fig-value {
  font-size: var(--zeus-text-2xl, 32px);
  font-weight: var(--zeus-weight-bold, 700);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.fig-label {
  margin-top: 2px;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-muted);
}

.win-kv {
  margin: 12px 0 0;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-top: 1px solid var(--orb-line);
  font-size: var(--zeus-text-sm, 13px);
}

.kv-row dt {
  color: var(--orb-muted);
}

.kv-row dd {
  margin: 0;
  text-align: right;
  font-weight: var(--zeus-weight-medium, 500);
  overflow-wrap: anywhere;
}

.win-table-wrap {
  margin-top: 12px;
  overflow-x: auto;
}

.win-table-title {
  margin: 0 0 6px;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.win-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--zeus-text-sm, 13px);
}

.win-table th,
.win-table td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--orb-line);
}

.win-table th {
  color: var(--orb-muted);
  font-weight: var(--zeus-weight-medium, 500);
}

.win-more {
  margin: 6px 0 0;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-faint);
}

.win-evidence {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.win-evidence a {
  display: inline-block;
  padding: 4px 10px;
  border-radius: var(--zeus-radius-full, 999px);
  background: var(--orb-panel-2);
  color: var(--orb-a);
  font-size: var(--zeus-text-sm, 13px);
  text-decoration: none;
}

.win-next {
  margin: 10px 0 0;
  font-size: var(--zeus-text-sm, 13px);
  color: var(--orb-muted);
}

.win-confirm {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.win-btn-confirm,
.win-btn-cancel {
  padding: 8px 16px;
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: var(--zeus-text-sm, 13px);
  font-weight: var(--zeus-weight-semibold, 600);
  cursor: pointer;
}

.win-btn-confirm {
  border: none;
  background: var(--btn, var(--orb-fg));
  color: var(--btn-fg, #ffffff);
}

.win-btn-cancel {
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  color: var(--orb-fg);
}

/* ------------------------------------------------------------------ adjuntar medio (PERSEO) */
.orb-attach-wrapper {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 420px;
}

.orb-attach-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding: 6px 10px;
  border-radius: var(--zeus-radius-full, 999px);
  border: 1px solid var(--orb-line);
  background: var(--orb-panel-2);
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-muted);
}

.orb-attach-chip a {
  color: var(--orb-a);
}

.chip-remove {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--orb-faint);
  cursor: pointer;
  font-size: var(--zeus-text-xs, 12px);
}

/* Texto (solo si se pide) */
.orb-type {
  position: relative;
  z-index: 2;
  width: 100%;
  display: flex;
  gap: 8px;
}

.orb-type input {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border-radius: var(--zeus-radius, 12px);
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  color: var(--orb-fg);
  font-size: 16px; /* evita el zoom automático en iOS */
}

.orb-type-send {
  padding: 10px 16px;
  border-radius: var(--zeus-radius, 12px);
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  color: var(--orb-fg);
  font-weight: var(--zeus-weight-semibold, 600);
  cursor: pointer;
}

/* Barra inferior: el micro es la única acción con el gradiente de acento */
.orb-bar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 4px;
}

.orb-side-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  font-size: 20px;
  cursor: pointer;
}

.orb-side-btn[aria-pressed='true'] {
  border-color: var(--orb-a);
}

.orb-mic {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: none;
  background: var(--zeus-accent-gradient, linear-gradient(135deg, #14b8a6 0%, #8b5cf6 50%, #ec4899 100%));
  box-shadow: var(--zeus-accent-gradient-shadow, 0 2px 8px rgba(0, 0, 0, 0.15));
  font-size: 28px;
  cursor: pointer;
  transition: transform var(--zeus-dur-press, 100ms) var(--zeus-ease-micro, ease);
}

.orb-mic:active {
  transform: scale(0.96);
}

.orb-mic.live {
  animation: orb-mic-pulse 1.1s ease-in-out infinite;
}

.orb-mic:disabled {
  opacity: 0.55;
  cursor: progress;
}

.orb-bar-hint {
  position: relative;
  z-index: 2;
  margin: 0;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-faint);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

/* Entrada/salida de ventanas y paneles del deck */
.orb-win-enter-active {
  transition: opacity 240ms var(--zeus-ease-enter, ease), transform 240ms var(--zeus-ease-enter, ease);
}
.orb-win-leave-active {
  transition: opacity 180ms var(--zeus-ease-exit, ease);
}
.orb-win-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.orb-win-leave-to {
  opacity: 0;
}

@keyframes orb-deploy {
  from { opacity: 0; transform: translateY(18px) scale(0.98); }
  to { opacity: 1; transform: none; }
}

@keyframes orb-breathe {
  0%, 100% { transform: scale(1); opacity: 0.85; }
  50% { transform: scale(1.04); opacity: 1; }
}

@keyframes orb-breathe-img {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.055); }
}

@keyframes orb-glow {
  0%, 100% { box-shadow: 0 0 0 3px var(--orb-panel), 0 8px 24px color-mix(in srgb, var(--orb-a) 30%, transparent); }
  50% { box-shadow: 0 0 0 4px var(--orb-panel), 0 10px 40px color-mix(in srgb, var(--orb-a) 48%, transparent); }
}

@keyframes orb-scan {
  0% { transform: translateY(-130%); }
  100% { transform: translateY(250%); }
}

@keyframes orb-spin {
  to { transform: rotate(360deg); }
}

@keyframes orb-pulse-ring {
  0% { transform: scale(0.75); opacity: 0.5; }
  100% { transform: scale(1.5); opacity: 0; }
}

@keyframes orb-eq-beat {
  0%, 100% { transform: scaleY(0.45); }
  50% { transform: scaleY(1); }
}

@keyframes orb-mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--orb-a) 45%, transparent); }
  50% { box-shadow: 0 0 0 12px color-mix(in srgb, var(--orb-a) 0%, transparent); }
}

@media (prefers-reduced-motion: reduce) {
  .orb,
  .orb-ring,
  .orb-pulse,
  .orb-scan,
  .orb-eq span,
  .orb-mic,
  .orb-deck,
  .orb-win-enter-active,
  .orb-win-leave-active {
    animation: none !important;
    transition: none !important;
  }
  .orb-eq.live span {
    height: 14px;
  }
}

@media (max-width: 768px) {
  .voice-orb {
    --orb-size: 220px;
    --orb-stage-min-h: 300px;
    padding: 12px 16px 16px;
  }
  .orb-bar {
    gap: 16px;
  }
  .kv-row {
    flex-direction: column;
    gap: 2px;
  }
  .kv-row dd {
    text-align: left;
  }
}
</style>
