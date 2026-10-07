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

export interface JarvisVoiceOptions {
  /** Reconocimiento continuo (true) o una frase por pulsacion (false). */
  continuous?: boolean;
  /** Velocidad de la voz sintetizada. */
  rate?: number;
  /** Se invoca solo con transcripciones FINALES, nunca mientras el agente habla. */
  onFinal?: (transcript: string) => void;
}

/** Quita URLs y enlaces del texto antes de leerlo en voz alta (la evidencia no se lee). */
export function speakableText(text: string): string {
  return String(text || '')
    .replace(/\bhttps?:\/\/\S+/gi, '')
    .replace(/\b(?:www\.)\S+/gi, '')
    .replace(/(?:^|\s)\/(?:api\/)\S+/g, ' ')
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
      return 'No se oyó nada. Pulsa de nuevo y habla.';
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

  function cancel(): void {
    const s = synth();
    if (s && (s.speaking || s.pending)) s.cancel();
    speaking.value = false;
    utterance = null;
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
    const es = s.getVoices().find((v) => v.lang && v.lang.toLowerCase().startsWith('es'));
    if (es) u.voice = es;
    u.onstart = () => {
      speaking.value = true;
    };
    const done = () => {
      speaking.value = false;
      if (utterance === u) utterance = null;
    };
    u.onend = done;
    u.onerror = done;
    utterance = u;
    speaking.value = true; // activo ya: el reconocimiento no arranca ni acepta nada hasta el final
    s.speak(u);
    return true;
  }

  function dispose(): void {
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
  };
}
