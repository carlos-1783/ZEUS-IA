import { ref, computed, onUnmounted } from 'vue';

/**
 * J11: capa de voz UNICA de JARVIS (Web Speech API del navegador).
 *
 * La voz es solo un canal de entrada/salida del mismo chat de texto: este composable no habla con el
 * backend. Quien lo usa recibe la transcripcion final en `onFinal` y la envia por su MISMA funcion de
 * envio de texto con `channel: 'voice'`. Confirmacion humana, THALOS y registro siguen en el servidor.
 *
 * Seguridad: mientras el sintetizador habla, el reconocimiento esta PARADO y cualquier transcripcion
 * tardia se descarta, para que ZEUS no se oiga a si mismo y dispare una confirmacion («confirmar»).
 * `speak()` lee solo el texto de respuesta, sin URLs.
 */

export const VOICE_LANG = 'es-ES';
// Watchdog de sintesis: ~100 ms por caracter (ritmo lento) + margen, minimo 3 s.
export const WATCHDOG_MS_PER_CHAR = 100;
export const WATCHDOG_MARGIN_MS = 3000;
export const WATCHDOG_MIN_MS = 3000;

export interface JarvisVoiceOptions {
  /** Reconocimiento continuo (true) o una frase por pulsacion (false). */
  continuous?: boolean;
  /** Velocidad de la voz sintetizada. */
  rate?: number;
  /** Se invoca solo con transcripciones FINALES, nunca mientras el agente habla. */
  onFinal?: (transcript: string) => void;
  /**
   * Genero de la voz sintetizada para este agente (cada agente tiene una personalidad y voz
   * propias). La Web Speech API no expone el genero de una voz: se infiere por nombres conocidos
   * de voces es-ES/es-* de los motores TTS mas comunes (Windows/SAPI, macOS, Chrome/Android). Si
   * no hay ninguna voz reconocible de ese genero, se usa la primera voz en espanol disponible.
   */
  voiceGender?: 'male' | 'female';
  /**
   * Palabra de activacion (manos libres) con Picovoice Porcupine, motor LOCAL en el dispositivo: el
   * audio de la escucha en espera nunca sale del navegador. Al oir la palabra se llama a `onWake` y se
   * arranca el reconocimiento de UNA frase (la orden), que llega por `onFinal` como siempre.
   */
  wakeWord?: boolean;
  onWake?: (label: string) => void;
  /** Si devuelve false, la palabra se ignora (p. ej. mientras el agente esta trabajando). */
  canWake?: () => boolean;
}

/**
 * Configuracion de Porcupine (solo variables de entorno de Vite; nada en el codigo):
 * - VITE_PICOVOICE_ACCESS_KEY: AccessKey de console.picovoice.ai. Sin ella, la escucha en espera no
 *   arranca y el orbe se queda en estado limpio con el texto como respaldo.
 * - VITE_PICOVOICE_KEYWORD_PATH (opcional): ruta publica de un .ppn propio (p. ej. «Zeus»). Sin ella se
 *   usa la palabra incluida gratis «Jarvis».
 * - VITE_PICOVOICE_KEYWORD_LABEL (opcional): nombre que se muestra para ese .ppn (por defecto «Zeus»).
 * - VITE_PICOVOICE_MODEL_PATH (opcional): modelo .pv del idioma del .ppn (por defecto el ingles,
 *   /porcupine/porcupine_params.pv, que es el de «Jarvis»).
 */
export type WakeState = 'off' | 'loading' | 'armed' | 'unavailable';

const DEFAULT_MODEL_PATH = '/porcupine/porcupine_params.pv';

function wakeConfig() {
  const env = (import.meta as any).env || {};
  const accessKey = String(env.VITE_PICOVOICE_ACCESS_KEY || '').trim();
  const keywordPath = String(env.VITE_PICOVOICE_KEYWORD_PATH || '').trim();
  return {
    accessKey,
    keywordPath,
    keywordLabel: String(env.VITE_PICOVOICE_KEYWORD_LABEL || 'Zeus').trim() || 'Zeus',
    modelPath: String(env.VITE_PICOVOICE_MODEL_PATH || '').trim() || DEFAULT_MODEL_PATH,
  };
}

/** Nombre de la palabra que esta configurada (para decirle al usuario que palabra decir). */
export function configuredWakeLabel(): string {
  const c = wakeConfig();
  return c.keywordPath ? c.keywordLabel : 'Jarvis';
}

function wakeErrorMessage(err: any): string {
  const name = String(err?.name || '');
  const msg = String(err?.message || err || '');
  if (/NotAllowed|Permission|SecurityError/i.test(name + msg)) {
    return 'Sin permiso de micrófono: la palabra de activación no puede escuchar. Actívalo en el navegador.';
  }
  if (/Activation|AccessKey|10008|10009|10010|10011/i.test(name + msg)) {
    return 'La clave de Picovoice no es válida o ha superado su límite: la palabra de activación está desactivada.';
  }
  if (/NotFound|audio-capture|device/i.test(name + msg)) {
    return 'No se encontró ningún micrófono para la palabra de activación.';
  }
  return 'La palabra de activación no pudo arrancar en este navegador.';
}

const MALE_VOICE_HINTS = [
  'jorge', 'pablo', 'diego', 'juan', 'miguel', 'carlos', 'enrique', 'raul', 'raúl', 'alvaro',
  'álvaro', 'fernando', 'antonio', 'male', 'hombre',
];
const FEMALE_VOICE_HINTS = [
  'monica', 'mónica', 'helena', 'laura', 'elvira', 'paulina', 'lucia', 'lucía', 'sabina',
  'conchita', 'marisol', 'esperanza', 'camila', 'female', 'mujer',
];

function pickVoiceByGender(voices: SpeechSynthesisVoice[], gender?: 'male' | 'female'): SpeechSynthesisVoice | undefined {
  const esVoices = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith('es'));
  if (!esVoices.length) return undefined;
  if (!gender) return esVoices[0];
  const hints = gender === 'male' ? MALE_VOICE_HINTS : FEMALE_VOICE_HINTS;
  const byName = esVoices.find((v) => {
    const name = v.name.toLowerCase();
    return hints.some((h) => name.includes(h));
  });
  return byName || esVoices[0];
}

/** Quita URLs y enlaces del texto antes de leerlo en voz alta (la evidencia no se lee). */
export function speakableText(text: string): string {
  return String(text || '')
    .replace(/\bhttps?:\/\/\S+/gi, '')
    .replace(/\b(?:www\.)\S+/gi, '')
    .replace(/(?:^|\s)\/[\w.~-]+(?:\/[\w.~%?=&#:@+-]*)+/g, ' ') // rutas relativas /algo/...
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function recognitionCtor(): any {
  if (typeof window === 'undefined') return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function synth(): SpeechSynthesis | null {
  return typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
}

function errorMessage(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Permiso de micrófono denegado. Actívalo en el navegador o sigue escribiendo.';
    case 'no-speech':
      return 'No se oyó nada. Vuelve a llamarme o toca el orbe y habla.';
    case 'audio-capture':
      return 'No se encontró ningún micrófono.';
    case 'network':
      return 'El reconocimiento de voz del navegador no pudo conectarse. Sigue escribiendo.';
    case 'aborted':
      return '';
    default:
      return 'Error en el reconocimiento de voz. Sigue escribiendo.';
  }
}

export function useJarvisVoice(options: JarvisVoiceOptions = {}) {
  const recognitionSupported = !!recognitionCtor();
  const synthesisSupported = !!synth();
  const supported = recognitionSupported;

  const listening = ref(false);
  const speaking = ref(false);
  const transcript = ref('');
  const error = ref('');

  const unsupportedMessage = computed(() =>
    recognitionSupported
      ? ''
      : 'Tu navegador no soporta reconocimiento de voz. Usa Chrome, Edge o Safari, o escribe tu mensaje.',
  );

  let recognition: any = null;
  let utterance: SpeechSynthesisUtterance | null = null;
  let watchdog: ReturnType<typeof setTimeout> | null = null;

  function ensureRecognition(): any {
    if (recognition) return recognition;
    const Ctor = recognitionCtor();
    if (!Ctor) return null;
    const r = new Ctor();
    r.continuous = options.continuous ?? false;
    r.interimResults = true;
    r.lang = VOICE_LANG;
    r.onresult = (event: any) => {
      if (speaking.value) return; // se descarta lo captado mientras el agente habla
      const results = Array.from(event.results) as any[];
      const text = results.map((res) => res[0].transcript).join('');
      transcript.value = text;
      if (results.length && results[results.length - 1].isFinal && text.trim()) {
        options.onFinal?.(text);
      }
    };
    r.onerror = (event: any) => {
      listening.value = false;
      error.value = errorMessage(String(event?.error || ''));
    };
    r.onend = () => {
      listening.value = false;
      // Captada (o no) la orden, se vuelve a la escucha en espera de la palabra de activacion.
      if (options.wakeWord) resumeWake();
    };
    recognition = r;
    return r;
  }

  function start(): boolean {
    error.value = '';
    if (!recognitionSupported) {
      error.value = unsupportedMessage.value;
      return false;
    }
    if (speaking.value) return false; // nunca escuchar mientras habla
    const r = ensureRecognition();
    if (!r) return false;
    try {
      transcript.value = '';
      r.start();
      listening.value = true;
      return true;
    } catch (e: any) {
      // InvalidStateError si ya estaba arrancado
      listening.value = false;
      error.value = 'No se pudo iniciar el micrófono. Inténtalo de nuevo.';
      return false;
    }
  }

  function stop(): void {
    if (recognition && listening.value) {
      try {
        recognition.stop();
      } catch {
        /* ya parado */
      }
    }
    listening.value = false;
  }

  function clearWatchdog(): void {
    if (watchdog) {
      clearTimeout(watchdog);
      watchdog = null;
    }
  }

  /** Corta la voz actual. Invalida la utterance vigente ANTES de cancelar: sus eventos tardios se ignoran. */
  function cancel(): void {
    clearWatchdog();
    utterance = null;
    const s = synth();
    if (s) {
      try {
        if (s.speaking || s.pending) s.cancel();
      } catch {
        /* nada que cancelar */
      }
    }
    speaking.value = false;
  }

  /** Lee `text` en voz alta (sin URLs). Para el reconocimiento mientras dura. */
  function speak(text: string): boolean {
    const s = synth();
    const clean = speakableText(text);
    if (!s || !clean) return false;
    cancel();
    stop();
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = VOICE_LANG;
    u.rate = options.rate ?? 1.0;
    u.pitch = 1.0;
    try {
      const es = pickVoiceByGender(s.getVoices(), options.voiceGender);
      if (es) u.voice = es;
    } catch {
      /* voz por defecto */
    }
    // Solo la utterance vigente puede liberar `speaking`: un onend/onerror tardio de una anterior se ignora.
    const done = () => {
      if (utterance !== u) return;
      clearWatchdog();
      utterance = null;
      speaking.value = false;
    };
    u.onend = done;
    u.onerror = done;
    utterance = u;
    speaking.value = true; // activo ya: el reconocimiento no arranca ni acepta nada hasta el final
    // Watchdog: si el navegador nunca dispara onend/onerror, se libera solo para esta utterance.
    const ms = Math.max(
      WATCHDOG_MIN_MS,
      (clean.length * WATCHDOG_MS_PER_CHAR) / (options.rate && options.rate > 0 ? options.rate : 1) + WATCHDOG_MARGIN_MS,
    );
    watchdog = setTimeout(() => {
      if (utterance !== u) return;
      try {
        if (s.speaking) s.cancel();
      } catch {
        /* nada */
      }
      done();
    }, ms);
    try {
      s.speak(u);
    } catch {
      done();
      error.value = 'No se pudo reproducir la voz. Puedes leer la respuesta en pantalla.';
      return false;
    }
    return true;
  }

  // ------------------------------------------------------------------ palabra de activacion (Porcupine)
  const wakeState = ref<WakeState>('off');
  const wakeReason = ref('');
  const wakeLabel = ref(configuredWakeLabel());
  let porcupine: any = null;
  let wvp: any = null;
  let wakeSubscribed = false;
  let disposed = false;
  let gestureHooked = false;

  async function subscribeWake(): Promise<void> {
    if (!porcupine || !wvp || disposed) return;
    // subscribe() es idempotente y reanuda el AudioContext si el navegador lo dejo suspendido.
    await wvp.subscribe(porcupine);
    wakeSubscribed = true;
  }

  async function unsubscribeWake(): Promise<void> {
    if (!porcupine || !wvp || !wakeSubscribed) return;
    wakeSubscribed = false;
    try {
      await wvp.unsubscribe(porcupine);
    } catch {
      /* ya fuera */
    }
  }

  /** Algunos navegadores no dan audio hasta que hay un gesto: el primer toque/tecla reanuda la escucha. */
  function hookGestureResume(): void {
    if (gestureHooked || typeof document === 'undefined') return;
    gestureHooked = true;
    const resume = () => {
      document.removeEventListener('pointerdown', resume);
      document.removeEventListener('keydown', resume);
      if (wakeState.value === 'armed' && !listening.value && !speaking.value) subscribeWake().catch(() => {});
    };
    document.addEventListener('pointerdown', resume, { once: true });
    document.addEventListener('keydown', resume, { once: true });
  }

  function onDetection(detection: { label: string }): void {
    // Nunca reacciona mientras el agente habla (no se oye a si mismo) ni si ya esta captando la orden.
    if (speaking.value || listening.value || disposed) return;
    if (options.canWake && !options.canWake()) return;
    options.onWake?.(detection?.label || wakeLabel.value);
    // Se suelta el micro de la escucha en espera mientras se capta la orden; se recupera al terminar.
    unsubscribeWake().finally(() => {
      if (!start()) resumeWake();
    });
  }

  /** Arranca la escucha en espera. Sin clave o sin motor no rompe nada: queda `unavailable` con el motivo. */
  async function armWake(): Promise<boolean> {
    if (wakeState.value === 'armed' || wakeState.value === 'loading') return wakeState.value === 'armed';
    const cfg = wakeConfig();
    wakeLabel.value = configuredWakeLabel();
    if (!cfg.accessKey) {
      wakeState.value = 'unavailable';
      wakeReason.value = 'Palabra de activación sin configurar (falta la clave de Picovoice).';
      return false;
    }
    if (typeof window === 'undefined' || !navigator?.mediaDevices?.getUserMedia || typeof Worker === 'undefined') {
      wakeState.value = 'unavailable';
      wakeReason.value = 'Este navegador no permite la escucha en espera.';
      return false;
    }
    wakeState.value = 'loading';
    wakeReason.value = '';
    try {
      // Carga diferida: el motor (WASM) solo se descarga si hay clave y se va a usar.
      const [pv, vp] = await Promise.all([
        import('@picovoice/porcupine-web'),
        import('@picovoice/web-voice-processor'),
      ]);
      if (disposed) return false;
      const keyword = cfg.keywordPath
        ? { publicPath: cfg.keywordPath, label: cfg.keywordLabel, sensitivity: 0.6 }
        : { builtin: pv.BuiltInKeyword.Jarvis, sensitivity: 0.6 };
      porcupine = await pv.PorcupineWorker.create(cfg.accessKey, keyword, onDetection, {
        publicPath: cfg.modelPath,
        version: 1,
      }, {
        processErrorCallback: (e: any) => {
          wakeReason.value = wakeErrorMessage(e);
        },
      });
      wvp = vp.WebVoiceProcessor;
      if (disposed) {
        porcupine.terminate?.();
        porcupine = null;
        return false;
      }
      await subscribeWake();
      wakeState.value = 'armed';
      hookGestureResume();
      return true;
    } catch (e: any) {
      wakeState.value = 'unavailable';
      wakeReason.value = wakeErrorMessage(e);
      try {
        porcupine?.terminate?.();
      } catch {
        /* nada */
      }
      porcupine = null;
      return false;
    }
  }

  /** Vuelve a la escucha en espera (tras captar la orden o terminar de hablar). */
  function resumeWake(): void {
    if (wakeState.value !== 'armed' || listening.value || speaking.value || disposed) return;
    subscribeWake().catch((e) => {
      wakeReason.value = wakeErrorMessage(e);
    });
  }

  async function disposeWake(): Promise<void> {
    await unsubscribeWake();
    try {
      porcupine?.terminate?.();
    } catch {
      /* nada */
    }
    porcupine = null;
    if (wakeState.value !== 'unavailable') wakeState.value = 'off';
  }

  function dispose(): void {
    disposed = true;
    disposeWake();
    cancel();
    if (recognition) {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try {
        recognition.abort?.();
      } catch {
        /* nada */
      }
      recognition = null;
    }
    listening.value = false;
  }

  onUnmounted(dispose);

  return {
    supported,
    synthesisSupported,
    unsupportedMessage,
    listening,
    speaking,
    transcript,
    error,
    start,
    stop,
    speak,
    cancel,
    dispose,
    wakeState,
    wakeReason,
    wakeLabel,
    armWake,
    resumeWake,
  };
}
