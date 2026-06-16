<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { scanFlowApi } from '@/api/scanFlow'

const emit = defineEmits<{
  (e: 'scanned', result: Record<string, unknown>): void
  (e: 'error', message: string): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const status = ref('Solicitando cámara…')
const scanning = ref(false)
const lastResult = ref<Record<string, unknown> | null>(null)
const facingMode = ref<'environment' | 'user'>('environment')

let stream: MediaStream | null = null
let rafId = 0
let handled = false
let decoding = false
let barcodeDetector: BarcodeDetector | null = null

async function ensureBarcodeDetector(): Promise<BarcodeDetector | null> {
  if (barcodeDetector) return barcodeDetector
  if (typeof BarcodeDetector === 'undefined') return null
  try {
    barcodeDetector = new BarcodeDetector({ formats: ['qr_code'] })
    return barcodeDetector
  } catch {
    return null
  }
}

async function decodeQrFrame(imageData: ImageData): Promise<string | null> {
  const detector = await ensureBarcodeDetector()
  if (detector) {
    try {
      const hits = await detector.detect(imageData)
      if (hits[0]?.rawValue) return hits[0].rawValue
    } catch {
      /* fallback jsQR */
    }
  }
  try {
    const mod = await import('jsqr')
    const jsQR = mod.default
    const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: 'dontInvert' })
    return code?.data ?? null
  } catch {
    return null
  }
}
function stopCamera() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
  scanning.value = false
}

async function startCamera() {
  handled = false
  stopCamera()
  status.value = 'Abriendo cámara…'
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facingMode.value, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    })
    const video = videoRef.value
    if (!video) return
    video.srcObject = stream
    await video.play()
    scanning.value = true
    status.value = 'Apunta al código QR'
    tick()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'No se pudo abrir la cámara'
    status.value = msg
    emit('error', msg)
  }
}

function switchCamera() {
  facingMode.value = facingMode.value === 'environment' ? 'user' : 'environment'
  startCamera()
}

async function onQrDetected(data: string) {
  if (handled) return
  handled = true
  stopCamera()
  status.value = 'QR detectado — procesando…'
  try {
    const result = await scanFlowApi.scanQr(data)
    lastResult.value = result
    emit('scanned', result)
    status.value = String(result.message || 'QR procesado')
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Error procesando QR'
    status.value = msg
    emit('error', msg)
    handled = false
    await startCamera()
  }
}

function tick() {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas || !scanning.value || decoding) return

  const w = video.videoWidth
  const h = video.videoHeight
  if (w && h) {
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(video, 0, 0, w, h)
      const imageData = ctx.getImageData(0, 0, w, h)
      decoding = true
      decodeQrFrame(imageData)
        .then((data) => {
          decoding = false
          if (data) {
            onQrDetected(data)
            return
          }
          if (scanning.value) rafId = requestAnimationFrame(tick)
        })
        .catch(() => {
          decoding = false
          if (scanning.value) rafId = requestAnimationFrame(tick)
        })
      return
    }
  }
  rafId = requestAnimationFrame(tick)
}
onMounted(() => {
  if (!navigator.mediaDevices?.getUserMedia) {
    status.value = 'Cámara no disponible en este navegador'
    emit('error', status.value)
    return
  }
  startCamera()
})

onBeforeUnmount(stopCamera)
</script>

<template>
  <div class="scanner-qr">
    <div class="preview-wrap">
      <video ref="videoRef" class="preview" playsinline muted />
      <canvas ref="canvasRef" class="hidden-canvas" />
      <div v-if="scanning" class="overlay">QR</div>
    </div>
    <p class="status">{{ status }}</p>
    <div class="actions">
      <button type="button" class="btn" @click="switchCamera">Cambiar cámara</button>
      <button type="button" class="btn secondary" @click="startCamera">Reiniciar</button>
    </div>
    <pre v-if="lastResult" class="result">{{ JSON.stringify(lastResult, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.scanner-qr { display: flex; flex-direction: column; gap: 0.75rem; }
.preview-wrap { position: relative; background: #111; border-radius: 12px; overflow: hidden; }
.preview { width: 100%; max-height: 360px; object-fit: cover; display: block; }
.hidden-canvas { display: none; }
.overlay {
  position: absolute; inset: 20% 15%; border: 2px solid #22d3ee; border-radius: 8px;
  pointer-events: none; box-shadow: 0 0 0 9999px rgba(0,0,0,0.35);
}
.status { margin: 0; color: #cbd5e1; font-size: 0.95rem; }
.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.btn {
  background: #0ea5e9; color: #fff; border: none; padding: 0.5rem 1rem;
  border-radius: 8px; cursor: pointer; font-weight: 600;
}
.btn.secondary { background: #334155; }
.result {
  background: #0f172a; color: #e2e8f0; padding: 0.75rem; border-radius: 8px;
  font-size: 0.75rem; overflow: auto; max-height: 200px;
}
</style>
