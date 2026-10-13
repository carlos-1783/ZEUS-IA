<template>
  <section
    class="voice-orb"
    :class="[`is-${stage}`, { 'has-windows': windows.length > 0 }]"
    :aria-label="`Asistente de voz de ${agentLabel}`"
  >
    <header class="orb-head">
      <div class="orb-head-id">
        <strong>{{ agentLabel }}</strong>
        <span v-if="agent.role" class="orb-head-role">· {{ agent.role }}</span>
      </div>
      <button
        type="button"
        class="orb-icon-btn"
        :aria-expanded="toolsOpen ? 'true' : 'false'"
        :aria-label="toolsOpen ? 'Ocultar herramientas del workspace' : 'Mostrar herramientas del workspace'"
        :title="toolsOpen ? 'Ocultar herramientas' : 'Herramientas del workspace'"
        @click="$emit('toggle-tools')"
      >
        ⋮
      </button>
    </header>

    <div class="orb-stage">
      <div class="orb" aria-hidden="true">
        <span class="orb-ring r1"></span>
        <span class="orb-ring r2"></span>
        <span class="orb-ring r3"></span>
        <span class="orb-pulse"></span>
        <span class="orb-core">
          <img v-if="agent.image" :src="agent.image" alt="" />
        </span>
      </div>

      <div class="orb-wave" :class="{ live: stage === 'listening' || voice.speaking.value }" aria-hidden="true">
        <span v-for="n in 7" :key="n"></span>
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
        <template v-else-if="!windows.length">
          <p class="orb-title">{{ greeting }}</p>
          <p class="orb-sub">{{ voice.supported ? 'Pulsa el micro para hablar' : 'Tu navegador no reconoce voz: usa ⌨️ para escribir' }}</p>
        </template>
        <p v-if="voice.speaking.value" class="orb-sub">Respondiendo en voz alta…</p>
      </div>
    </div>

    <p v-if="voiceError" class="orb-alert" role="alert">{{ voiceError }}</p>

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
  infoWindow,
  errorWindow,
  sourceLabel,
  type JarvisWindow,
} from '@/utils/jarvisWindows';

const props = defineProps<{
  agent: { name: string; role?: string; image?: string };
  toolsOpen?: boolean;
}>();
defineEmits<{ (e: 'toggle-tools'): void }>();

const authStore = useAuthStore();

// Mismo hilo que la pestaña Chat: una confirmación pendiente abierta por voz se puede cerrar desde allí.
const THREAD_ID = 'main';
const MIN_INTERVAL_MS = 3000; // mismo límite anti-429 que AgentActivityPanel

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

const greeting = computed(() => {
  const full = String((authStore.user as any)?.name || '').trim();
  const first = full && !full.includes('@') ? full.split(/\s+/)[0] : '';
  return first ? `Hola ${first}, ¿en qué te ayudo?` : 'Hola, ¿en qué te ayudo?';
});

const stage = computed<'idle' | 'listening' | 'busy'>(() => {
  if (busy.value) return 'busy';
  if (voice.listening.value) return 'listening';
  return 'idle';
});

const voiceError = computed(() => localError.value || voice.error.value);

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
    const res = await fetch(getAgentChatUrl(props.agent.name), {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, thread_id: THREAD_ID, context: { channel } }),
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
 * 📷 Foto / factura. El backend NO tiene hoy un endpoint que lea una factura o nómina desde una foto
 * y la reparta (factura -> RAFAEL, nómina/pedido -> AFRODITA): /scan/ingest solo admite QR, NFC y
 * MRZ de DNI. No se simula ninguna extracción: se informa con honestidad y no se envía nada.
 */
function onPhoto(): void {
  showWindows([
    infoWindow(
      'Foto / factura · todavía no disponible',
      sourceLabel('ZEUS'),
      'Falta el enrutado de ZEUS: todavía no hay un servicio que lea una factura, nómina o pedido desde una foto y lo reparta a Rafael o Afrodita. No se ha enviado nada. Mientras tanto, registra la factura desde el workspace de Rafael.',
    ),
  ]);
}
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
  --orb-size: 220px;

  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 20px 20px;
  margin-bottom: 20px;
  border-radius: var(--zeus-radius-lg, 16px);
  border: 1px solid var(--orb-line);
  background:
    radial-gradient(420px 260px at 50% 0%, var(--violet-soft, rgba(106, 92, 255, 0.12)), transparent 70%),
    var(--orb-panel);
  color: var(--orb-fg);
  box-shadow: var(--zeus-shadow-md, 0 4px 16px rgba(15, 23, 42, 0.06));
  font-family: var(--zeus-font-sans, inherit);
}

.orb-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.orb-head-id strong {
  font-size: var(--zeus-text-md, 17px);
}

.orb-head-role {
  margin-left: 6px;
  color: var(--orb-muted);
  font-size: var(--zeus-text-sm, 13px);
}

.orb-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--zeus-radius-full, 999px);
  border: 1px solid var(--orb-line);
  background: var(--orb-panel);
  color: var(--orb-fg);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.orb-icon-btn:focus-visible,
.orb-side-btn:focus-visible,
.orb-mic:focus-visible,
.win-close:focus-visible {
  outline: none;
  box-shadow: var(--zeus-shadow-focus, 0 0 0 3px rgba(106, 92, 255, 0.3));
}

/* Escenario */
.orb-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
}

.orb {
  position: relative;
  width: var(--orb-size);
  height: var(--orb-size);
  transition: width 240ms var(--zeus-ease-enter, ease), height 240ms var(--zeus-ease-enter, ease);
}

.voice-orb.has-windows .orb,
.voice-orb.is-busy .orb {
  --orb-size: 120px;
}

.orb-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1.5px solid color-mix(in srgb, var(--orb-a) 35%, transparent);
  animation: orb-breathe 4.8s ease-in-out infinite;
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
  background: radial-gradient(circle, color-mix(in srgb, var(--orb-a) 30%, transparent), transparent 70%);
  animation: orb-breathe 4.8s ease-in-out infinite;
}

.orb-core {
  position: absolute;
  inset: 27%;
  border-radius: 50%;
  overflow: hidden;
  background: var(--orb-panel-2);
  box-shadow: 0 0 0 3px var(--orb-panel), 0 8px 28px color-mix(in srgb, var(--orb-a) 35%, transparent);
}

.orb-core img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.voice-orb.is-listening .orb-ring,
.voice-orb.is-listening .orb-pulse {
  animation-duration: 1.1s;
}

.voice-orb.is-busy .orb-ring.r3 {
  animation-duration: 2.4s;
}

.orb-wave {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 26px;
}

.orb-wave span {
  width: 4px;
  height: 6px;
  border-radius: 2px;
  background: linear-gradient(var(--orb-a), var(--orb-b));
  opacity: 0.45;
}

.orb-wave.live span {
  opacity: 1;
  animation: orb-wave 0.9s ease-in-out infinite;
}

.orb-wave.live span:nth-child(2n) { animation-delay: -0.3s; }
.orb-wave.live span:nth-child(3n) { animation-delay: -0.55s; }

.orb-copy {
  text-align: center;
  max-width: 460px;
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
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  background: color-mix(in srgb, var(--orb-amber) 14%, var(--orb-panel));
  color: var(--orb-fg);
  font-size: var(--zeus-text-sm, 13px);
}

/* Ventanas */
.orb-windows {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.orb-win {
  border: 1px solid var(--orb-line);
  border-radius: var(--zeus-radius, 12px);
  background: var(--orb-panel);
  padding: 14px 16px;
  box-shadow: var(--zeus-shadow, 0 1px 3px rgba(15, 23, 42, 0.06));
}

.orb-win.kind-blocked {
  border: 1.5px solid var(--orb-amber);
  background: color-mix(in srgb, var(--orb-amber) 8%, var(--orb-panel));
}

.orb-win.kind-error {
  border-color: color-mix(in srgb, var(--orb-red) 55%, transparent);
}

.win-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

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

/* Texto (solo si se pide) */
.orb-type {
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

/* Entrada/salida de ventanas */
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

@keyframes orb-breathe {
  0%, 100% { transform: scale(1); opacity: 0.85; }
  50% { transform: scale(1.04); opacity: 1; }
}

@keyframes orb-spin {
  to { transform: rotate(360deg); }
}

@keyframes orb-wave {
  0%, 100% { height: 6px; }
  50% { height: 24px; }
}

@keyframes orb-mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--orb-a) 45%, transparent); }
  50% { box-shadow: 0 0 0 12px color-mix(in srgb, var(--orb-a) 0%, transparent); }
}

@media (prefers-reduced-motion: reduce) {
  .orb,
  .orb-ring,
  .orb-pulse,
  .orb-wave span,
  .orb-mic,
  .orb-win-enter-active,
  .orb-win-leave-active {
    animation: none !important;
    transition: none !important;
  }
  .orb-wave.live span {
    height: 14px;
  }
}

@media (max-width: 768px) {
  .voice-orb {
    --orb-size: 180px;
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
