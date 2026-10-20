import * as ort from 'onnxruntime-web/wasm';
import ortWasmUrl from 'onnxruntime-web/ort-wasm-simd-threaded.wasm?url';
import {
  Pcm16Chunker,
  WAKE_SAMPLE_RATE,
  WakeWordFeaturePipeline,
  type WakeSession,
} from './openWakeWordCore';

/**
 * Palabra de activacion con openWakeWord en el navegador (onnxruntime-web, WASM local, sin CDN ni
 * clave). Todo el audio se procesa en el dispositivo: nada sale del navegador.
 *
 * Este modulo SOLO detecta la palabra. Se carga con import() diferido desde useJarvisVoice.ts y va en
 * su propio chunk (vite.config.ts), asi que no pesa en la carga inicial de la app.
 */

export type WakeEngineErrorCode = 'model-missing' | 'runtime' | 'unsupported' | 'cancelled';

export class WakeEngineError extends Error {
  readonly code: WakeEngineErrorCode;
  constructor(code: WakeEngineErrorCode, message: string) {
    super(message);
    this.name = 'WakeEngineError';
    this.code = code;
  }
}

export interface OpenWakeWordOptions {
  /** Modelo de la palabra (p. ej. /openwakeword/local/hey_jarvis_v0.1.onnx). */
  modelPath: string;
  melspectrogramPath: string;
  embeddingPath: string;
  /** Puntuacion minima (0..1) para considerar la palabra oida. */
  threshold: number;
  /** Tras una deteccion se ignoran nuevas durante este tiempo (una palabra = un disparo). */
  refractoryMs?: number;
  onDetection: (score: number) => void;
  /** Error durante la escucha (no al arrancar): p. ej. el micro desaparece. */
  onError?: (err: unknown) => void;
}

const DEFAULT_REFRACTORY_MS = 2000;
/** AudioWorklet de captura, servido desde public/ (mismo origen; ver el comentario del archivo). */
const CAPTURE_WORKLET_PATH = `${import.meta.env.BASE_URL}openwakeword/capture-worklet.js`;
/** Si la inferencia se retrasa, no se acumulan mas de ~2 s de audio pendiente. */
const MAX_PENDING_CHUNKS = 25;

let ortConfigured = false;
function configureOrt(): void {
  if (ortConfigured) return;
  // WASM servido por la propia app (sin CDN: funciona offline) y 1 hilo: no exige cross-origin isolation.
  ort.env.wasm.wasmPaths = { wasm: ortWasmUrl };
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.proxy = false;
  ort.env.logLevel = 'error';
  ortConfigured = true;
}

async function fetchModel(path: string): Promise<Uint8Array> {
  let res: Response;
  try {
    res = await fetch(path, { cache: 'force-cache' });
  } catch {
    throw new WakeEngineError('model-missing', `No se pudo descargar ${path}`);
  }
  // Un servidor SPA devuelve index.html (200) para rutas inexistentes: eso tampoco es un modelo.
  const type = res.headers.get('content-type') || '';
  if (!res.ok || type.includes('text/html')) {
    throw new WakeEngineError('model-missing', `Modelo no encontrado: ${path} (${res.status})`);
  }
  return new Uint8Array(await res.arrayBuffer());
}

async function createSession(bytes: Uint8Array): Promise<ort.InferenceSession> {
  try {
    return await ort.InferenceSession.create(bytes, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    });
  } catch (e) {
    throw new WakeEngineError('runtime', `onnxruntime no pudo cargar el modelo: ${String((e as any)?.message || e)}`);
  }
}

/** Desconecta nodos, para las pistas del micro y cierra el AudioContext (sin lanzar). */
async function releaseAudio(stream: MediaStream | null, ctx: AudioContext | null, nodes: AudioNode[]): Promise<void> {
  for (const n of nodes) {
    try {
      n.disconnect();
    } catch {
      /* ya desconectado */
    }
    if (typeof AudioWorkletNode !== 'undefined' && n instanceof AudioWorkletNode) n.port.onmessage = null;
    if (typeof ScriptProcessorNode !== 'undefined' && n instanceof ScriptProcessorNode) n.onaudioprocess = null;
  }
  stream?.getTracks().forEach((t) => t.stop());
  if (ctx && ctx.state !== 'closed') await ctx.close().catch(() => {});
}

export class OpenWakeWordEngine {
  private readonly opts: OpenWakeWordOptions;
  private readonly sessions: ort.InferenceSession[];
  private readonly pipeline: WakeWordFeaturePipeline;
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private nodes: AudioNode[] = [];
  private queue: Int16Array[] = [];
  private pumping: Promise<void> | null = null;
  private generation = 0;
  private lastDetection = 0;
  private starting: Promise<void> | null = null;
  /** Puntuacion maxima vista desde el ultimo start() (diagnostico). */
  peakScore = 0;

  constructor(opts: OpenWakeWordOptions, sessions: ort.InferenceSession[], pipeline: WakeWordFeaturePipeline) {
    this.opts = opts;
    this.sessions = sessions;
    this.pipeline = pipeline;
  }

  get running(): boolean {
    return !!this.stream;
  }

  /** Abre el micro y empieza a escuchar. Idempotente; si ya escucha, reanuda el AudioContext suspendido. */
  start(): Promise<void> {
    if (this.stream) {
      if (this.ctx && this.ctx.state === 'suspended') return this.ctx.resume().catch(() => {});
      return Promise.resolve();
    }
    if (!this.starting) {
      this.starting = this.open().finally(() => {
        this.starting = null;
      });
    }
    return this.starting;
  }

  private async open(): Promise<void> {
    if (this.pumping) await this.pumping; // no se mezcla audio de la sesion anterior
    this.pipeline.reset();
    this.queue = [];
    this.peakScore = 0;
    const gen = ++this.generation;
    const cancelled = () => gen !== this.generation;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    // Todo lo creado en este arranque se libera si algo falla o si stop()/dispose() llega mientras tanto
    // (p. ej. el orbe se desmonta con el aviso de permiso del micro abierto): ni micro ni AudioContext
    // quedan vivos.
    let ctx: AudioContext | null = null;
    const nodes: AudioNode[] = [];
    try {
      if (cancelled()) throw new WakeEngineError('cancelled', 'detenido mientras arrancaba');
      const created = this.createContext(stream);
      ctx = created.ctx;
      nodes.push(created.source);
      const chunker = new Pcm16Chunker(ctx.sampleRate, (chunk) => this.enqueue(chunk, gen));
      let sink: AudioNode;
      if (ctx.audioWorklet && typeof AudioWorkletNode !== 'undefined') {
        try {
          await ctx.audioWorklet.addModule(CAPTURE_WORKLET_PATH);
        } catch (err) {
          throw new WakeEngineError('runtime', `No se pudo cargar la captura de audio: ${String((err as any)?.message || err)}`);
        }
        if (cancelled()) throw new WakeEngineError('cancelled', 'detenido mientras arrancaba');
        const node = new AudioWorkletNode(ctx, 'zeus-wake-capture', { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 });
        node.port.onmessage = (ev: MessageEvent<Float32Array>) => chunker.push(ev.data);
        sink = node;
      } else {
        // Respaldo para navegadores sin AudioWorklet.
        const node = ctx.createScriptProcessor(2048, 1, 1);
        node.onaudioprocess = (ev) => chunker.push(ev.inputBuffer.getChannelData(0));
        sink = node;
      }
      nodes.push(sink);
      created.source.connect(sink);
      sink.connect(ctx.destination); // no suena (salida en silencio), pero mantiene el nodo procesando
      if (cancelled()) throw new WakeEngineError('cancelled', 'detenido mientras arrancaba');
      this.stream = stream;
      this.ctx = ctx;
      this.nodes = nodes;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    } catch (e) {
      await releaseAudio(stream, ctx, nodes);
      throw e;
    }
  }

  /** AudioContext a 16 kHz si el navegador lo admite con el micro; si no, el nativo y se remuestrea. */
  private createContext(stream: MediaStream): { ctx: AudioContext; source: MediaStreamAudioSourceNode } {
    const Ctor: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!Ctor) throw new WakeEngineError('unsupported', 'AudioContext no disponible');
    let ctx: AudioContext | null = null;
    try {
      ctx = new Ctor({ sampleRate: WAKE_SAMPLE_RATE });
      return { ctx, source: ctx.createMediaStreamSource(stream) };
    } catch {
      // frecuencia no admitida con este micro: se cierra y se usa la nativa
      ctx?.close().catch(() => {});
    }
    const native = new Ctor();
    try {
      return { ctx: native, source: native.createMediaStreamSource(stream) };
    } catch (e) {
      native.close().catch(() => {});
      throw e;
    }
  }

  /** Suelta el micro (p. ej. mientras el navegador capta la orden). */
  async stop(): Promise<void> {
    this.generation++;
    this.queue = [];
    if (this.starting) await this.starting.catch(() => {});
    const stream = this.stream;
    const ctx = this.ctx;
    const nodes = this.nodes;
    this.stream = null;
    this.ctx = null;
    this.nodes = [];
    await releaseAudio(stream, ctx, nodes);
  }

  async dispose(): Promise<void> {
    await this.stop();
    if (this.pumping) await this.pumping.catch(() => {});
    for (const s of this.sessions) {
      try {
        await s.release();
      } catch {
        /* nada */
      }
    }
  }

  private enqueue(chunk: Int16Array, gen: number): void {
    if (gen !== this.generation) return;
    this.queue.push(chunk);
    if (this.queue.length > MAX_PENDING_CHUNKS) this.queue.splice(0, this.queue.length - MAX_PENDING_CHUNKS);
    if (!this.pumping) {
      this.pumping = this.pump(gen).finally(() => {
        this.pumping = null;
      });
    }
  }

  private async pump(gen: number): Promise<void> {
    while (this.queue.length && gen === this.generation) {
      const chunk = this.queue.shift()!;
      let score: number | null;
      try {
        score = await this.pipeline.process(chunk);
      } catch (e) {
        this.queue = [];
        this.opts.onError?.(e);
        return;
      }
      if (score === null || gen !== this.generation) continue;
      if (score > this.peakScore) this.peakScore = score;
      const now = Date.now();
      const refractory = this.opts.refractoryMs ?? DEFAULT_REFRACTORY_MS;
      if (score >= this.opts.threshold && now - this.lastDetection >= refractory) {
        this.lastDetection = now;
        this.opts.onDetection(score);
      }
    }
  }
}

/**
 * Descarga los tres modelos y prepara onnxruntime. No abre el micro: eso lo hace start().
 * Lanza WakeEngineError ('model-missing' | 'runtime') si algo falta o no carga.
 */
export async function createOpenWakeWord(opts: OpenWakeWordOptions): Promise<OpenWakeWordEngine> {
  configureOrt();
  const [melBytes, embBytes, wwBytes] = await Promise.all([
    fetchModel(opts.melspectrogramPath),
    fetchModel(opts.embeddingPath),
    fetchModel(opts.modelPath),
  ]);
  const melspectrogram = await createSession(melBytes);
  const embedding = await createSession(embBytes);
  const wakeword = await createSession(wwBytes);
  const pipeline = new WakeWordFeaturePipeline(ort, {
    melspectrogram: melspectrogram as unknown as WakeSession,
    embedding: embedding as unknown as WakeSession,
    wakeword: wakeword as unknown as WakeSession,
  });
  return new OpenWakeWordEngine(opts, [melspectrogram, embedding, wakeword], pipeline);
}
