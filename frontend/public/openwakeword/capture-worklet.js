// AudioWorklet de la palabra de activacion: solo copia el audio del micro (mono, a la frecuencia del
// AudioContext) en bloques de 2048 muestras y los pasa al hilo principal, donde se remuestrea a 16 kHz
// y se procesa con openWakeWord (src/utils/openWakeWord.ts). No produce sonido.
// Vive en public/ (y no como import ?url) porque Vite lo incrustaria como data: URL, que la CSP de
// index.html (script-src sin data:) bloquearia en addModule().
const BLOCK = 2048;

class ZeusWakeCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(BLOCK);
    this.n = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      for (let i = 0; i < channel.length; i++) {
        this.buf[this.n++] = channel[i];
        if (this.n === BLOCK) {
          this.port.postMessage(this.buf, [this.buf.buffer]);
          this.buf = new Float32Array(BLOCK);
          this.n = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('zeus-wake-capture', ZeusWakeCapture);
