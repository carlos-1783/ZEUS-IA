<template>
  <section
    class="voice-orb"
    :class="[`is-${stage}`, { 'is-deployed': deployed, 'has-holo': holoPanels.length > 0, 'wake-armed': voice.wakeState.value === 'armed' }]"
    :aria-label="`Asistente de voz de ${agentLabel}`"
  >
    <!-- Sin cabecera propia: el encuadre y la identidad del agente (avatar/nombre/rol) son los de
         AgentActivityPanel.vue — un solo marco, una sola cabecera. El fondo es el metal/platino de la
         app (no se pinta otro): el orbe solo IRRADIA su luz azul de marca encima. -->

    <!-- Escena: orbe en el centro; los paneles holograma se despliegan a su alrededor. -->
    <div class="orb-scene">
      <TransitionGroup name="holo" tag="div" class="holo-side holo-left">
        <HoloPanelCard v-for="p in holoLeft" :key="p.key" :panel="p" side="left" @close="closeHolo(p.key)" />
      </TransitionGroup>

      <div class="orb-stage">
        <!-- Toque en el orbe = hablar ahora (respaldo de la palabra de activación); no es un botón visible. -->
        <div
          class="orb"
          role="button"
          tabindex="0"
          :aria-label="stage === 'listening' ? 'Dejar de escuchar' : `Hablar con ${agentLabel}`"
          @click="tapOrb"
          @keydown.enter.prevent="tapOrb"
          @keydown.space.prevent="tapOrb"
        >
          <span class="orb-aura" aria-hidden="true"></span>
          <span class="orb-bloom" aria-hidden="true"></span>

          <svg class="hud hud-ticks" viewBox="0 0 400 400" fill="none" aria-hidden="true">
            <line
              v-for="t in 60"
              :key="t"
              x1="200"
              y1="14"
              x2="200"
              :y2="t % 5 === 1 ? 38 : 26"
              :class="t % 5 === 1 ? 'tick-major' : 'tick-minor'"
              :transform="`rotate(${(t - 1) * 6} 200 200)`"
            />
          </svg>
          <svg class="hud hud-arc" viewBox="0 0 400 400" fill="none" aria-hidden="true">
            <defs>
              <linearGradient :id="`arc-${uid}`" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" class="stop-hi" />
                <stop offset="1" class="stop-fade" />
              </linearGradient>
            </defs>
            <circle cx="200" cy="200" r="158" class="ring-dots" />
            <circle cx="200" cy="200" r="158" class="ring-arc" :stroke="`url(#arc-${uid})`" />
            <circle cx="200" cy="200" r="158" class="ring-arc ring-arc-2" :stroke="`url(#arc-${uid})`" />
          </svg>
          <svg class="hud hud-fast" viewBox="0 0 400 400" fill="none" aria-hidden="true">
            <circle cx="200" cy="200" r="128" class="ring-dash" />
            <path class="ring-marks" d="M200 58 v18 M200 342 v-18 M58 200 h18 M342 200 h-18" />
          </svg>
          <svg class="hud hud-inner" viewBox="0 0 400 400" fill="none" aria-hidden="true">
            <circle cx="200" cy="200" r="108" class="ring-thin" />
            <circle cx="200" cy="200" r="108" class="ring-seg" />
          </svg>

          <span class="orb-pulse p1" aria-hidden="true"></span>
          <span class="orb-pulse p2" aria-hidden="true"></span>

          <span class="orb-core" aria-hidden="true">
            <img v-if="agent.image" :src="agent.image" :alt="agent.name" />
            <span class="orb-scan"></span>
          </span>
          <span class="orb-flare" aria-hidden="true"></span>

          <div class="orb-eq" :class="{ live: stage === 'listening' || voice.speaking.value }" aria-hidden="true">
            <span v-for="n in 7" :key="n"></span>
          </div>
        </div>

        <div class="orb-copy" aria-live="polite">
          <template v-if="stage === 'listening'">
            <p class="orb-title">Escuchando…</p>
            <p class="orb-sub">{{ voice.transcript.value || 'Habla con normalidad; paro al terminar la frase.' }}</p>
          </template>
          <template v-else-if="stage === 'busy'">
            <p class="orb-title">{{ agentLabel }} está trabajando…</p>
            <p class="orb-sub">«{{ lastAsked }}»</p>
          </template>
          <p v-else-if="voice.speaking.value" class="orb-sub">Respondiendo…</p>
          <template v-else-if="!deployed">
            <p v-if="voice.wakeState.value === 'armed'" class="orb-hint">
              Di <strong>«{{ voice.wakeLabel.value }}»</strong> y pide lo que necesites
            </p>
            <p v-else-if="voice.wakeState.value === 'loading'" class="orb-hint">Preparando la escucha…</p>
          </template>
        </div>
      </div>

      <TransitionGroup name="holo" tag="div" class="holo-side holo-right">
        <HoloPanelCard v-for="p in holoRight" :key="p.key" :panel="p" side="right" @close="closeHolo(p.key)" />
      </TransitionGroup>
    </div>

    <p v-if="voiceError" class="orb-alert" role="alert">{{ voiceError }}</p>

    <!-- Deck: respuestas del chat (windows) y los paneles del menú ⋮ (herramientas / actividad /
         métricas), con el mismo tratamiento holograma. -->
    <div v-if="windows.length || activePanel" class="orb-deck">
      <TransitionGroup name="orb-win" tag="div" class="orb-windows">
        <article
          v-for="w in windows"
          :key="w.id"
          class="orb-win holo-surface"
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

      <section v-if="activePanel" class="orb-panel holo-surface">
        <header class="panel-head">
          <h4>{{ panelTitle }}</h4>
          <button type="button" class="win-close" @click="closePanel">OK, cerrar</button>
        </header>
        <div class="panel-body">
          <slot :name="`panel-${activePanel}`" />
        </div>
      </section>
    </div>

    <!-- Respaldo de texto, discreto: un enlace, no un botón. Dentro, adjuntar estilo WhatsApp
         (foto/factura -> bandeja de ZEUS; PERSEO: medio para su vídeo). -->
    <form v-if="typing" class="orb-type" @submit.prevent="sendTyped">
      <label class="sr-only" :for="inputId">Escribe a {{ agentLabel }}</label>
      <button type="button" class="orb-type-attach" title="Adjuntar foto o factura" aria-label="Adjuntar foto o factura" @click="onPhoto">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="M21 11.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9" />
        </svg>
      </button>
      <input
        ref="photoInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        hidden
        @change="onPhotoChosen"
      />
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

    <div v-if="typing && supportsMediaAttachment" class="orb-attach-wrapper">
      <ImageUploader @uploaded="handleMediaUploaded" />
      <div v-if="mediaReferenceUrl" class="orb-attach-chip">
        <span>Medio adjunto (imagen / vídeo / PDF)</span>
        <a :href="mediaReferenceUrl" target="_blank" rel="noopener">Ver</a>
        <button type="button" class="chip-remove" @click="clearMediaReference">Quitar</button>
      </div>
    </div>

    <p class="orb-foot">
      <a href="#" class="orb-text-link" @click.prevent="toggleTyping">{{ typing ? 'Ocultar texto' : 'Prefiero escribir' }}</a>
      <span v-if="voice.wakeState.value === 'unavailable' && voice.wakeReason.value" class="orb-wake-note">
        · {{ voice.wakeReason.value }}
      </span>
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, ref, type PropType } from 'vue';
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
import { detectHoloRequest, loadHoloPanel, HOLO_TITLES, type HoloKey, type HoloPanel } from '@/utils/jarvisHoloPanels';
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

const uid = Math.random().toString(36).slice(2, 8);
const inputId = `orb-input-${uid}`;

// Voz por agente: masculina (ZEUS, PERSEO, RAFAEL, THALOS) o femenina (JUSTICIA, AFRODITA),
// coherente con la personalidad de cada uno definida en su system prompt (config/prompts.json).
const FEMALE_VOICE_AGENTS = new Set(['JUSTICIA', 'AFRODITA']);
const voiceGender = computed<'male' | 'female'>(() =>
  FEMALE_VOICE_AGENTS.has((props.agent?.name || '').toUpperCase().split(' ')[0]) ? 'female' : 'male',
);

// Manos libres: openWakeWord escucha la palabra en el dispositivo; al oírla capta UNA frase y la envía.
const voice = useJarvisVoice({
  continuous: false,
  rate: 0.95,
  voiceGender: voiceGender.value,
  wakeWord: true,
  canWake: () => !busy.value,
  onWake: () => {
    localError.value = '';
    voice.cancel();
    // Oída la palabra pero el navegador no transcribe la orden: se abre el texto, sin romper nada.
    if (!voice.supported) {
      typing.value = true;
      nextTick(() => typeInput.value?.focus());
    }
  },
  onFinal: (text) => send(text, 'voice'),
});

onMounted(() => {
  voice.armWake();
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

// --------------------------------------------------------------------- paneles holograma (por voz)

type HoloView = HoloPanel & { loading: boolean };
const MAX_HOLO = 2; // uno a cada lado del orbe
const holoPanels = ref<HoloView[]>([]);
// El más reciente a la derecha; el anterior pasa a la izquierda.
const holoRight = computed(() => holoPanels.value.slice(0, 1));
const holoLeft = computed(() => holoPanels.value.slice(1, 2));

async function openHolo(key: HoloKey): Promise<HoloView> {
  const placeholder: HoloView = {
    key,
    title: HOLO_TITLES[key],
    source: 'Cargando datos reales…',
    state: 'ok',
    message: '',
    figures: [],
    columns: [],
    rows: [],
    loading: true,
  };
  holoPanels.value = [placeholder, ...holoPanels.value.filter((p) => p.key !== key)].slice(0, MAX_HOLO);
  const api = (await import('@/services/api')).default;
  const panel = await loadHoloPanel(key, (endpoint) => api.get(endpoint, token()), props.agent.name);
  const view: HoloView = { ...panel, loading: false };
  // Solo si sigue abierto (el usuario pudo cerrarlo mientras cargaba).
  if (holoPanels.value.some((p) => p.key === key)) {
    holoPanels.value = holoPanels.value.map((p) => (p.key === key ? view : p));
  }
  return view;
}

function closeHolo(key: HoloKey): void {
  holoPanels.value = holoPanels.value.filter((p) => p.key !== key);
}

const CLOSE_RE = /^(?:ok[, ]*)?(?:cierra|cerrar|cierralo|cierralos|cierra todo|cierra (?:el|los) panel(?:es)?|quita(?:lo)?|vale,? cierra)$/;

function isCloseCommand(message: string): boolean {
  const m = message
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[.,!¡?¿]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return CLOSE_RE.test(m);
}

function closeEverything(): void {
  holoPanels.value = [];
  windows.value = [];
  closePanel();
}

/** El orbe se encoge si hay algo desplegado (respuesta, panel ⋮, holograma) o está ocupado. */
const deployed = computed(
  () => windows.value.length > 0 || activePanel.value !== null || holoPanels.value.length > 0 || stage.value === 'busy',
);

function token(): string | null {
  return (authStore as any).getToken?.() ?? (authStore as any).token ?? null;
}

async function send(raw: string, channel: 'voice' | 'text'): Promise<void> {
  const message = String(raw || '').trim();
  if (!message || busy.value) return;

  // Órdenes de pantalla que resuelve el propio orbe (sin pasar por el agente): cerrar y mostrar.
  if (isCloseCommand(message)) {
    closeEverything();
    voice.cancel();
    return;
  }
  const holoKey = detectHoloRequest(message);
  if (holoKey) {
    localError.value = '';
    lastAsked.value = message;
    const view = await openHolo(holoKey);
    if (channel === 'voice') {
      voice.speak(view.state === 'ok' ? `Aquí tienes: ${view.title.split(' ·')[0].toLowerCase()}.` : view.message);
    }
    return;
  }

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

/** Tocar el orbe = hablar ya (sin esperar a la palabra). Sin reconocimiento de voz, abre el texto. */
function tapOrb(): void {
  localError.value = '';
  if (busy.value) return;
  if (voice.listening.value) {
    voice.stop();
    return;
  }
  if (!voice.supported) {
    typing.value = true;
    nextTick(() => typeInput.value?.focus());
    return;
  }
  voice.cancel();
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
 * Foto / factura estilo WhatsApp: la recibe ZEUS (POST /api/v1/zeus/inbox), la guarda en R2, la
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

/** Tarjeta holograma: solo pinta lo que trae `panel` (datos reales, «Sin datos» o el error). */
const HoloPanelCard = defineComponent({
  name: 'HoloPanelCard',
  props: {
    panel: { type: Object as PropType<HoloView>, required: true },
    side: { type: String as PropType<'left' | 'right'>, default: 'right' },
  },
  emits: ['close'],
  setup(p, { emit: emitCard }) {
    return () => {
      const panel = p.panel;
      const body: any[] = [];
      if (panel.loading) {
        body.push(h('p', { class: 'holo-msg' }, 'Cargando datos reales…'));
      } else if (panel.state !== 'ok') {
        body.push(h('p', { class: ['holo-msg', `is-${panel.state}`], role: panel.state === 'error' ? 'alert' : undefined }, panel.message));
      }
      if (panel.figures.length) {
        body.push(
          h(
            'div',
            { class: 'holo-figures' },
            panel.figures.map((f) =>
              h('div', { class: 'holo-figure', key: f.label }, [h('span', { class: 'holo-fig-value' }, f.value), h('span', { class: 'holo-fig-label' }, f.label)]),
            ),
          ),
        );
      }
      if (panel.rows.length) {
        body.push(
          h('div', { class: 'holo-table-wrap' }, [
            h('table', { class: 'holo-table' }, [
              h('thead', [h('tr', panel.columns.map((c) => h('th', { scope: 'col', key: c }, c)))]),
              h('tbody', panel.rows.map((r, ri) => h('tr', { key: ri }, r.map((cell, ci) => h('td', { key: ci }, cell))))),
            ]),
          ]),
        );
      }
      return h('article', { class: ['holo-panel', 'holo-surface', `from-${p.side}`], role: 'region', 'aria-label': panel.title }, [
        h('header', { class: 'win-head' }, [
          h('div', [h('h4', { class: 'win-title' }, panel.title), h('p', { class: 'win-source' }, panel.source)]),
          h('button', { type: 'button', class: 'win-close', onClick: () => emitCard('close') }, 'OK, cerrar'),
        ]),
        ...body,
      ]);
    };
  },
});

defineExpose({ closePanel, choosePanel, activePanel });
</script>

<style scoped>
/* ======================================================================
   Tokens: todo sale del sistema de diseño de la app (zeus-theme-tokens.css), en claro y oscuro.
   --volt es el azul de marca; el "azul eléctrico" es ese mismo volt aclarado hacia cian, y la
   luz del orbe es --volt-glow. El fondo NO se pinta aquí: es el metal/platino de .activity-panel.
   ====================================================================== */
.voice-orb {
  --orb-volt: var(--volt, #2f82f0);
  --orb-volt-hi: color-mix(in srgb, var(--orb-volt) 55%, #8fe3ff);
  --orb-volt-deep: color-mix(in srgb, var(--orb-volt) 70%, #0a1a3a);
  --orb-glow: var(--volt-glow, rgba(47, 130, 240, 0.5));
  --orb-panel: var(--panel, var(--zeus-surface, #ffffff));
  --orb-panel-2: var(--panel-2, #f3f5f9);
  --orb-line: var(--line, var(--zeus-border, rgba(20, 28, 56, 0.1)));
  --orb-fg: var(--fg, var(--zeus-text, #141a2b));
  --orb-muted: var(--muted, var(--zeus-text-secondary, #56607a));
  --orb-faint: var(--faint, var(--zeus-text-muted, #8891a6));
  --orb-amber: var(--amber, var(--zeus-warning, #f5a623));
  --orb-red: var(--red, var(--zeus-danger, #ff5d6c));
  /* Intensidad de la luz: algo menor sobre platino (claro) para que no lave el metal. */
  --orb-light: 0.95;
  --orb-size: 380px;
  --orb-stage-min-h: 470px;

  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 4px 4px 8px;
  color: var(--orb-fg);
  font-family: var(--zeus-font-sans, inherit);
}

:global(:root[data-theme='dark']) .voice-orb {
  --orb-light: 1.15;
}

/* Rejilla HUD con el azul de marca, desvanecida hacia los bordes: se apoya en el metal, no lo tapa. */
.voice-orb::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.55;
  background-image:
    linear-gradient(color-mix(in srgb, var(--orb-volt) 9%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--orb-volt) 9%, transparent) 1px, transparent 1px);
  background-size: 38px 38px;
  mask: radial-gradient(circle at 50% 36%, #000 0%, transparent 70%);
  -webkit-mask: radial-gradient(circle at 50% 36%, #000 0%, transparent 70%);
  transition: opacity 400ms ease;
}

.voice-orb.is-deployed::before {
  opacity: 0.2;
}

.orb:focus-visible,
.win-close:focus-visible,
.orb-text-link:focus-visible {
  outline: none;
  box-shadow: var(--zeus-shadow-focus, 0 0 0 3px rgba(47, 130, 240, 0.35));
}

/* ------------------------------------------------------------------ escena: orbe + hologramas */
.orb-scene {
  position: relative;
  z-index: 2;
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 18px;
}

.holo-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.holo-left {
  align-items: flex-end;
}

.holo-right {
  align-items: flex-start;
}

.orb-stage {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: var(--orb-stage-min-h);
  transition: min-height 420ms cubic-bezier(0.3, 0.1, 0.2, 1);
}

.voice-orb.is-deployed .orb-stage {
  min-height: 0;
  gap: 6px;
}

/* Con hologramas abiertos el orbe se queda a tamaño medio, en el centro, emitiéndolos. */
.voice-orb.is-deployed {
  --orb-size: 120px;
}

.voice-orb.has-holo {
  --orb-size: 210px;
}

/* ------------------------------------------------------------------ orbe */
.orb {
  position: relative;
  width: var(--orb-size);
  height: var(--orb-size);
  display: grid;
  place-items: center;
  cursor: pointer;
  border-radius: 50%;
  transition: width 480ms cubic-bezier(0.3, 0.1, 0.2, 1), height 480ms cubic-bezier(0.3, 0.1, 0.2, 1);
}

/* Charco de luz que el orbe proyecta sobre el metal (más grande que el propio orbe). */
.orb-aura {
  position: absolute;
  inset: -45%;
  border-radius: 50%;
  pointer-events: none;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--orb-volt-hi) calc(55% * var(--orb-light)), transparent) 0%,
    color-mix(in srgb, var(--orb-volt) calc(30% * var(--orb-light)), transparent) 30%,
    color-mix(in srgb, var(--orb-volt) calc(10% * var(--orb-light)), transparent) 52%,
    transparent 70%
  );
}

/* Bloom: halo brillante y difuminado detrás del núcleo. */
.orb-bloom {
  position: absolute;
  inset: 6%;
  border-radius: 50%;
  pointer-events: none;
  /* Degradado ya difuso: sin filter:blur, que es caro de repintar en equipos sin GPU. */
  background: radial-gradient(
    circle,
    #ffffff 0%,
    var(--orb-volt-hi) 18%,
    color-mix(in srgb, var(--orb-volt) 80%, transparent) 38%,
    color-mix(in srgb, var(--orb-volt) 30%, transparent) 56%,
    transparent 72%
  );
  opacity: calc(0.7 * var(--orb-light));
  animation: orb-bloom 6.5s ease-in-out infinite;
}

.hud {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.hud-ticks {
  animation: orb-spin 60s linear infinite;
}

.tick-major {
  stroke: var(--orb-volt-hi);
  stroke-width: 2.4;
}

.tick-minor {
  stroke: color-mix(in srgb, var(--orb-volt) 65%, transparent);
  stroke-width: 1.4;
}

.hud-arc {
  animation: orb-spin 22s linear infinite;
}

.ring-dots {
  stroke: color-mix(in srgb, var(--orb-volt) 40%, transparent);
  stroke-width: 1.6;
  stroke-dasharray: 3 9;
}

.ring-arc {
  stroke-width: 4;
  stroke-linecap: round;
  stroke-dasharray: 150 843;
}

.ring-arc-2 {
  stroke-dasharray: 60 933;
  stroke-dashoffset: -480;
}

.stop-hi {
  stop-color: var(--orb-volt-hi);
}

.stop-fade {
  stop-color: var(--orb-volt);
  stop-opacity: 0;
}

.hud-fast {
  animation: orb-spin 12s linear infinite reverse;
}

.ring-dash {
  stroke: color-mix(in srgb, var(--orb-volt) 60%, transparent);
  stroke-width: 2;
  stroke-dasharray: 44 22;
}

.ring-marks {
  stroke: var(--orb-volt-hi);
  stroke-width: 3;
}

.ring-thin {
  stroke: color-mix(in srgb, var(--orb-volt) 35%, transparent);
  stroke-width: 1;
}

.ring-seg {
  stroke: var(--orb-volt-hi);
  stroke-width: 2.5;
  stroke-dasharray: 8 30;
  opacity: 0.8;
}

.orb-pulse {
  position: absolute;
  inset: 25%;
  border-radius: 50%;
  border: 2px solid var(--orb-volt-hi);
  box-shadow: 0 0 14px var(--orb-glow);
  opacity: 0;
  pointer-events: none;
  animation: orb-pulse-ring 3.2s ease-out infinite;
}

.orb-pulse.p2 {
  animation-delay: -1.6s;
}

.orb-core {
  position: absolute;
  inset: 28%;
  border-radius: 50%;
  overflow: hidden;
  background: var(--orb-volt-deep);
  border: 3px solid color-mix(in srgb, var(--orb-volt-hi) 85%, white);
  box-shadow:
    0 0 0 5px color-mix(in srgb, var(--orb-volt) 30%, transparent),
    0 0 50px var(--orb-glow),
    0 0 110px color-mix(in srgb, var(--orb-volt) calc(45% * var(--orb-light)), transparent),
    inset 0 0 30px rgba(6, 18, 44, 0.55);
}

.orb-core img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  filter: saturate(1.08) contrast(1.04);
  animation: orb-breathe-img 6.5s ease-in-out infinite;
}

/* Viñeta azul sobre el avatar: el dios queda "dentro" de la luz. */
.orb-core::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 32%, transparent 42%, color-mix(in srgb, var(--orb-volt-deep) 60%, transparent));
  pointer-events: none;
}

.orb-scan {
  position: absolute;
  left: -10%;
  right: -10%;
  height: 42%;
  z-index: 2;
  pointer-events: none;
  mix-blend-mode: screen;
  background: linear-gradient(
    180deg,
    transparent,
    color-mix(in srgb, var(--orb-volt-hi) 32%, transparent) 48%,
    color-mix(in srgb, var(--orb-volt-hi) 60%, white) 50%,
    color-mix(in srgb, var(--orb-volt-hi) 32%, transparent) 52%,
    transparent
  );
  animation: orb-scan 4.6s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

/* Destello especular arriba-izquierda: da volumen de esfera de luz. */
.orb-flare {
  position: absolute;
  inset: 30%;
  border-radius: 50%;
  pointer-events: none;
  background: radial-gradient(circle at 32% 24%, rgba(255, 255, 255, 0.55), transparent 28%);
  mix-blend-mode: screen;
}

/* Escuchando: todo se acelera y la luz sube. Trabajando: el arco gira rápido. */
.voice-orb.is-listening .orb-pulse {
  animation-duration: 1.1s;
}

.voice-orb.is-listening .orb-bloom {
  animation-duration: 1.4s;
}

.voice-orb.is-listening .hud-arc {
  animation-duration: 5s;
}

.voice-orb.is-busy .hud-arc,
.voice-orb.is-busy .hud-fast {
  animation-duration: 2.6s;
}

.orb-eq {
  position: absolute;
  bottom: 2%;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 26px;
  opacity: 0.45;
  pointer-events: none;
  transition: opacity 300ms ease;
}

.voice-orb.is-deployed .orb-eq {
  display: none;
}

.orb-eq span {
  width: 4px;
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(var(--orb-volt-hi), var(--orb-volt));
  box-shadow: 0 0 6px var(--orb-glow);
}

.orb-eq span:nth-child(2) { height: 18px; }
.orb-eq span:nth-child(3) { height: 24px; }
.orb-eq span:nth-child(4) { height: 14px; }
.orb-eq span:nth-child(5) { height: 22px; }
.orb-eq span:nth-child(6) { height: 16px; }
.orb-eq span:nth-child(7) { height: 9px; }

.orb-eq.live {
  opacity: 1;
}

.orb-eq.live span {
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
  color: var(--orb-fg);
}

.orb-sub,
.orb-hint {
  margin: 4px 0 0;
  color: var(--orb-muted);
  font-size: var(--zeus-text-sm, 13px);
  overflow-wrap: anywhere;
}

.orb-hint {
  letter-spacing: 0.02em;
}

.orb-hint strong {
  color: var(--volt-ink, var(--orb-volt));
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

/* ------------------------------------------------------------------ superficie holograma */
.holo-surface {
  position: relative;
  border: 1px solid color-mix(in srgb, var(--orb-volt) 45%, transparent);
  border-radius: var(--zeus-radius, 12px);
  background:
    repeating-linear-gradient(0deg, color-mix(in srgb, var(--orb-volt) 5%, transparent) 0 1px, transparent 1px 4px),
    linear-gradient(160deg, color-mix(in srgb, var(--orb-panel) 72%, transparent), color-mix(in srgb, var(--orb-panel) 52%, color-mix(in srgb, var(--orb-volt) 12%, transparent)));
  backdrop-filter: blur(10px) saturate(1.2);
  -webkit-backdrop-filter: blur(10px) saturate(1.2);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--orb-volt-hi) 12%, transparent) inset,
    0 0 26px color-mix(in srgb, var(--orb-volt) calc(28% * var(--orb-light)), transparent),
    0 18px 40px -18px rgba(5, 15, 40, 0.45);
  padding: 14px 16px;
}

/* Corchetes HUD luminosos en las esquinas. */
.holo-surface::before,
.holo-surface::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid var(--orb-volt-hi);
  filter: drop-shadow(0 0 4px var(--orb-glow));
  pointer-events: none;
}

.holo-surface::before {
  top: 6px;
  left: 6px;
  border-right: none;
  border-bottom: none;
  border-radius: 4px 0 0 0;
}

.holo-surface::after {
  bottom: 6px;
  right: 6px;
  border-left: none;
  border-top: none;
  border-radius: 0 0 4px 0;
}

.holo-panel {
  width: min(380px, 100%);
}

.orb-win.kind-blocked {
  border: 1.5px solid var(--orb-amber);
  box-shadow: 0 0 22px color-mix(in srgb, var(--orb-amber) 30%, transparent);
}

.orb-win.kind-error {
  border-color: color-mix(in srgb, var(--orb-red) 60%, transparent);
}

/* ------------------------------------------------------------------ deck */
.orb-deck {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 760px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  animation: orb-deploy 460ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
  transform-origin: 50% 0;
}

.orb-windows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.win-head,
.panel-head,
:deep(.win-head) {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.panel-head h4,
.win-title,
:deep(.win-title) {
  margin: 0;
  font-size: var(--zeus-text-base, 15px);
  font-weight: var(--zeus-weight-semibold, 600);
}

.win-source,
:deep(.win-source) {
  margin: 2px 0 0;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-faint);
  letter-spacing: 0.04em;
}

.win-close,
:deep(.win-close) {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: var(--zeus-radius-full, 999px);
  border: 1px solid color-mix(in srgb, var(--orb-volt) 40%, transparent);
  background: color-mix(in srgb, var(--orb-panel) 70%, transparent);
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

.win-figures,
:deep(.holo-figures) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.win-figure,
:deep(.holo-figure) {
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  border: 1px solid color-mix(in srgb, var(--orb-volt) 22%, transparent);
  background: color-mix(in srgb, var(--orb-volt) 7%, transparent);
}

.fig-value,
:deep(.holo-fig-value) {
  font-size: var(--zeus-text-2xl, 28px);
  font-weight: var(--zeus-weight-bold, 700);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--volt-ink, var(--orb-fg));
}

.fig-label,
:deep(.holo-fig-label) {
  margin-top: 2px;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-muted);
}

:deep(.holo-msg) {
  margin: 12px 0 0;
  font-size: var(--zeus-text-sm, 13px);
  color: var(--orb-muted);
}

:deep(.holo-msg.is-error) {
  color: var(--orb-fg);
  padding: 8px 10px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: color-mix(in srgb, var(--orb-red) 12%, transparent);
}

.win-kv {
  margin: 12px 0 0;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-top: 1px solid color-mix(in srgb, var(--orb-volt) 18%, transparent);
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

.win-table-wrap,
:deep(.holo-table-wrap) {
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

.win-table,
:deep(.holo-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--zeus-text-sm, 13px);
}

.win-table th,
.win-table td,
:deep(.holo-table th),
:deep(.holo-table td) {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--orb-volt) 16%, transparent);
}

.win-table th,
:deep(.holo-table th) {
  color: var(--orb-muted);
  font-weight: var(--zeus-weight-medium, 500);
  font-size: var(--zeus-text-xs, 12px);
  text-transform: uppercase;
  letter-spacing: 0.05em;
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
  border: 1px solid color-mix(in srgb, var(--orb-volt) 30%, transparent);
  color: var(--volt-ink, var(--orb-volt));
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
  background: var(--zeus-accent-gradient, var(--orb-volt));
  color: var(--btn-fg, #ffffff);
}

.win-btn-cancel {
  border: 1px solid var(--orb-line);
  background: color-mix(in srgb, var(--orb-panel) 70%, transparent);
  color: var(--orb-fg);
}

/* ------------------------------------------------------------------ texto de respaldo (discreto) */
.orb-type {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 620px;
  display: flex;
  gap: 8px;
}

.orb-type input[type='text'] {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border-radius: var(--zeus-radius, 12px);
  border: 1px solid color-mix(in srgb, var(--orb-volt) 35%, transparent);
  background: color-mix(in srgb, var(--orb-panel) 80%, transparent);
  color: var(--orb-fg);
  font-size: 16px; /* evita el zoom automático en iOS */
}

.orb-type-attach {
  display: grid;
  place-items: center;
  width: 42px;
  flex-shrink: 0;
  border-radius: var(--zeus-radius, 12px);
  border: 1px solid color-mix(in srgb, var(--orb-volt) 35%, transparent);
  background: color-mix(in srgb, var(--orb-panel) 80%, transparent);
  color: var(--orb-muted);
  cursor: pointer;
}

.orb-type-attach svg {
  width: 20px;
  height: 20px;
}

.orb-type-send {
  padding: 10px 16px;
  border-radius: var(--zeus-radius, 12px);
  border: none;
  background: var(--zeus-accent-gradient, var(--orb-volt));
  color: #ffffff;
  font-weight: var(--zeus-weight-semibold, 600);
  cursor: pointer;
}

.orb-type-send:disabled {
  opacity: 0.55;
  cursor: default;
}

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
  color: var(--volt-ink, var(--orb-volt));
}

.chip-remove {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--orb-faint);
  cursor: pointer;
  font-size: var(--zeus-text-xs, 12px);
}

.orb-foot {
  position: relative;
  z-index: 2;
  margin: 2px 0 0;
  font-size: var(--zeus-text-xs, 12px);
  color: var(--orb-faint);
  text-align: center;
}

.orb-text-link {
  color: var(--orb-muted);
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, var(--orb-volt) 40%, transparent);
  text-underline-offset: 3px;
  border-radius: 4px;
}

.orb-wake-note {
  opacity: 0.85;
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

/* ------------------------------------------------------------------ animaciones */
/* El holograma nace desde el orbe: entra encogido, desplazado hacia el centro y con destello. */
.holo-enter-active {
  transition:
    opacity 520ms cubic-bezier(0.2, 0.8, 0.2, 1),
    transform 520ms cubic-bezier(0.2, 0.8, 0.2, 1),
    filter 520ms ease;
}
.holo-right .holo-enter-active {
  transform-origin: 0% 50%;
}
.holo-left .holo-enter-active {
  transform-origin: 100% 50%;
}
.holo-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}
.holo-right .holo-enter-from {
  opacity: 0;
  transform: translateX(-90px) scale(0.25);
  filter: brightness(2.2) blur(6px);
}
.holo-left .holo-enter-from {
  opacity: 0;
  transform: translateX(90px) scale(0.25);
  filter: brightness(2.2) blur(6px);
}
.holo-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
.holo-enter-active {
  animation: holo-flicker 520ms steps(6, end) 1;
}

.orb-win-enter-active {
  transition: opacity 280ms var(--zeus-ease-enter, ease), transform 280ms var(--zeus-ease-enter, ease), filter 280ms ease;
}
.orb-win-leave-active {
  transition: opacity 180ms var(--zeus-ease-exit, ease);
}
.orb-win-enter-from {
  opacity: 0;
  transform: translateY(-24px) scale(0.92);
  filter: brightness(1.8) blur(3px);
}
.orb-win-leave-to {
  opacity: 0;
}

@keyframes orb-deploy {
  from { opacity: 0; transform: translateY(-20px) scale(0.94); filter: brightness(1.6) blur(3px); }
  to { opacity: 1; transform: none; filter: none; }
}

@keyframes holo-flicker {
  0% { opacity: 0.2; }
  40% { opacity: 0.9; }
  55% { opacity: 0.4; }
  100% { opacity: 1; }
}

@keyframes orb-bloom {
  0%, 100% { transform: scale(0.92); opacity: calc(0.6 * var(--orb-light)); }
  50% { transform: scale(1.15); opacity: calc(0.95 * var(--orb-light)); }
}

@keyframes orb-breathe-img {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}

@keyframes orb-scan {
  0% { transform: translateY(-130%); }
  100% { transform: translateY(250%); }
}

@keyframes orb-spin {
  to { transform: rotate(360deg); }
}

@keyframes orb-pulse-ring {
  0% { transform: scale(0.75); opacity: 0.6; }
  100% { transform: scale(1.55); opacity: 0; }
}

@keyframes orb-eq-beat {
  0%, 100% { transform: scaleY(0.4); }
  50% { transform: scaleY(1); }
}

@media (prefers-reduced-motion: reduce) {
  .orb,
  .hud,
  .orb-aura,
  .orb-bloom,
  .orb-core img,
  .orb-pulse,
  .orb-scan,
  .orb-eq span,
  .orb-deck,
  .holo-enter-active,
  .holo-leave-active,
  .orb-win-enter-active,
  .orb-win-leave-active {
    animation: none !important;
    transition: none !important;
  }
}

/* Pantallas medianas/pequeñas: los hologramas bajan debajo del orbe (no caben a los lados). */
@media (max-width: 1100px) {
  .orb-scene {
    grid-template-columns: minmax(0, 1fr);
  }
  .orb-stage {
    order: 1;
  }
  .holo-right {
    order: 2;
  }
  .holo-left {
    order: 3;
  }
  .holo-left,
  .holo-right {
    align-items: center;
  }
  .holo-panel {
    width: min(620px, 100%);
  }
  .voice-orb.has-holo {
    --orb-size: 150px;
  }
  .holo-right .holo-enter-from,
  .holo-left .holo-enter-from {
    transform: translateY(-60px) scale(0.3);
  }
}

@media (max-width: 768px) {
  .voice-orb {
    --orb-size: 250px;
    --orb-stage-min-h: 330px;
    padding: 12px 16px 16px;
  }
  .voice-orb.is-deployed {
    --orb-size: 100px;
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
