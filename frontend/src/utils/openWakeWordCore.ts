/**
 * Nucleo de openWakeWord (https://github.com/dscripka/openWakeWord, codigo Apache-2.0) portado a
 * TypeScript: la misma cadena de inferencia que `openwakeword/utils.py` (AudioFeatures) y
 * `openwakeword/model.py`, sin dependencias del navegador para poder probarla tambien en Node.
 *
 *   audio 16 kHz PCM int16, bloques de 1280 muestras (80 ms)
 *     -> melspectrogram.onnx  [1, 1280 + 480]  (int16 como float, SIN normalizar a +-1)
 *        salida [1, 1, 8, 32], transformada mel / 10 + 2; bufer de los ultimos 76 frames
 *     -> embedding_model.onnx [1, 76, 32, 1] -> 96 valores; se guardan los ultimos 16
 *     -> modelo de la palabra [1, 16, 96]   -> puntuacion 0..1
 *
 * Aqui no hay umbral ni periodo refractario: eso lo decide quien escucha (openWakeWord.ts).
 */

export const WAKE_SAMPLE_RATE = 16000;
/** 80 ms a 16 kHz: el paso de openWakeWord. */
export const WAKE_CHUNK_SAMPLES = 1280;
/** Contexto extra que AudioFeatures pasa al melspectrograma (160 * 3 muestras). */
const MEL_CONTEXT_SAMPLES = 480;
const MEL_BINS = 32;
const EMBEDDING_WINDOW = 76;
const EMBEDDING_DIM = 96;
const FEATURE_FRAMES = 16;

/** Lo minimo que se usa de onnxruntime (web o node): constructor de tensores. */
export interface OrtTensorFactory {
  Tensor: new (type: 'float32', data: Float32Array, dims: readonly number[]) => unknown;
}

/** Lo minimo que se usa de una InferenceSession. */
export interface WakeSession {
  readonly inputNames: readonly string[];
  readonly outputNames: readonly string[];
  run(feeds: Record<string, any>): Promise<Record<string, { data: unknown; dims: readonly number[] }>>;
}

export interface WakeSessions {
  melspectrogram: WakeSession;
  embedding: WakeSession;
  wakeword: WakeSession;
}

export class WakeWordFeaturePipeline {
  private readonly ort: OrtTensorFactory;
  private readonly s: WakeSessions;
  private raw = new Float32Array(WAKE_CHUNK_SAMPLES + MEL_CONTEXT_SAMPLES);
  private melFrames: Float32Array[] = [];
  private embeddings: Float32Array[] = [];

  constructor(ort: OrtTensorFactory, sessions: WakeSessions) {
    this.ort = ort;
    this.s = sessions;
    this.reset();
  }

  /** Vacia los buferes (al soltar y recuperar el micro no se mezcla audio viejo con el nuevo). */
  reset(): void {
    this.raw = new Float32Array(WAKE_CHUNK_SAMPLES + MEL_CONTEXT_SAMPLES);
    // Igual que AudioFeatures: el bufer mel empieza con 76 frames a 1.
    this.melFrames = Array.from({ length: EMBEDDING_WINDOW }, () => new Float32Array(MEL_BINS).fill(1));
    this.embeddings = [];
  }

  /**
   * Procesa un bloque de 1280 muestras int16 y devuelve la puntuacion de la palabra, o null mientras
   * aun no hay 16 embeddings reales (los primeros ~1,3 s tras arrancar).
   */
  async process(chunk: Int16Array): Promise<number | null> {
    if (chunk.length !== WAKE_CHUNK_SAMPLES) {
      throw new Error(`openWakeWord espera bloques de ${WAKE_CHUNK_SAMPLES} muestras`);
    }
    this.raw.copyWithin(0, WAKE_CHUNK_SAMPLES);
    for (let i = 0; i < WAKE_CHUNK_SAMPLES; i++) this.raw[MEL_CONTEXT_SAMPLES + i] = chunk[i];

    // 1) melspectrograma de las ultimas 1760 muestras -> 8 frames nuevos.
    const melIn = new this.ort.Tensor('float32', this.raw.slice(), [1, this.raw.length]);
    const melOut = await this.s.melspectrogram.run({ [this.s.melspectrogram.inputNames[0]]: melIn });
    const mel = melOut[this.s.melspectrogram.outputNames[0]].data as Float32Array;
    for (let f = 0; f + MEL_BINS <= mel.length; f += MEL_BINS) {
      const frame = new Float32Array(MEL_BINS);
      for (let b = 0; b < MEL_BINS; b++) frame[b] = mel[f + b] / 10 + 2;
      this.melFrames.push(frame);
    }
    if (this.melFrames.length > EMBEDDING_WINDOW) this.melFrames.splice(0, this.melFrames.length - EMBEDDING_WINDOW);

    // 2) embedding de los ultimos 76 frames mel.
    const window = new Float32Array(EMBEDDING_WINDOW * MEL_BINS);
    this.melFrames.forEach((frame, i) => window.set(frame, i * MEL_BINS));
    const embIn = new this.ort.Tensor('float32', window, [1, EMBEDDING_WINDOW, MEL_BINS, 1]);
    const embOut = await this.s.embedding.run({ [this.s.embedding.inputNames[0]]: embIn });
    const emb = embOut[this.s.embedding.outputNames[0]].data as Float32Array;
    this.embeddings.push(Float32Array.from(emb.subarray(0, EMBEDDING_DIM)));
    if (this.embeddings.length > FEATURE_FRAMES) this.embeddings.shift();
    if (this.embeddings.length < FEATURE_FRAMES) return null;

    // 3) modelo de la palabra sobre los ultimos 16 embeddings.
    const feats = new Float32Array(FEATURE_FRAMES * EMBEDDING_DIM);
    this.embeddings.forEach((e, i) => feats.set(e, i * EMBEDDING_DIM));
    const wwIn = new this.ort.Tensor('float32', feats, [1, FEATURE_FRAMES, EMBEDDING_DIM]);
    const wwOut = await this.s.wakeword.run({ [this.s.wakeword.inputNames[0]]: wwIn });
    const score = (wwOut[this.s.wakeword.outputNames[0]].data as Float32Array)[0];
    return Number.isFinite(score) ? score : 0;
  }
}

/**
 * Pasa audio float32 a la frecuencia del dispositivo (p. ej. 48 kHz) a bloques PCM int16 de 1280
 * muestras a 16 kHz. Remuestreo por promedio de cada intervalo de salida (filtro caja), suficiente
 * para voz; si la entrada ya va a 16 kHz es un paso directo.
 */
export class Pcm16Chunker {
  private readonly ratio: number;
  private readonly onChunk: (chunk: Int16Array) => void;
  private nextEdge: number;
  private consumed = 0;
  private acc = 0;
  private accCount = 0;
  private chunk = new Int16Array(WAKE_CHUNK_SAMPLES);
  private filled = 0;

  constructor(inputRate: number, onChunk: (chunk: Int16Array) => void) {
    this.ratio = inputRate / WAKE_SAMPLE_RATE;
    this.nextEdge = this.ratio;
    this.onChunk = onChunk;
  }

  push(input: Float32Array): void {
    for (let i = 0; i < input.length; i++) {
      this.acc += input[i];
      this.accCount++;
      this.consumed++;
      if (this.consumed >= this.nextEdge) {
        this.emit(this.acc / this.accCount);
        this.acc = 0;
        this.accCount = 0;
        this.nextEdge += this.ratio;
      }
    }
  }

  private emit(v: number): void {
    const s = Math.max(-1, Math.min(1, v));
    this.chunk[this.filled++] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767);
    if (this.filled === WAKE_CHUNK_SAMPLES) {
      const out = this.chunk;
      this.chunk = new Int16Array(WAKE_CHUNK_SAMPLES);
      this.filled = 0;
      this.onChunk(out);
    }
  }
}
