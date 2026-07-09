<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { scanFlowApi } from '@/api/scanFlow'
import { capturePhotoBase64, getScanRuntime } from '@/services/scanHardware'

const emit = defineEmits<{
  (e: 'parsed', result: Record<string, unknown>): void
  (e: 'error', message: string): void
}>()

const mode = ref<'manual' | 'camera'>('manual')
const mrz = ref('')
const email = ref('')
const phone = ref('')
const status = ref('Pega las 3 líneas completas del MRZ o usa la cámara del reverso')
const loading = ref(false)
const lastResult = ref<Record<string, unknown> | null>(null)
const runtime = ref({ native: false, platform: 'web', nfcMode: 'manual' as string })

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const cameraActive = ref(false)
let stream: MediaStream | null = null

const DEMO_MRZ = `I<UTOD231458907<<<<<<<
7408122F1204159UTO<<<<<<<<<<<6
ERIKSSON<<ANNA<MARIA<<<<<<<<<<`

function normalizeMrzInput(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n')
}

function fillDemoMrz() {
  mrz.value = DEMO_MRZ
  mode.value = 'manual'
  status.value = 'MRZ de ejemplo cargado. Pulsa «Crear cliente desde DNI».'
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
  cameraActive.value = false
}

async function startCamera() {
  stopCamera()
  if (!navigator.mediaDevices?.getUserMedia) {
    status.value = 'Cámara no disponible en este dispositivo'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    })
    const video = videoRef.value
    if (!video) return
    video.srcObject = stream
    await video.play()
    cameraActive.value = true
    status.value = 'Enfoca solo el reverso: las 3 líneas MRZ deben verse nítidas y con buena luz'
  } catch (err) {
    status.value = err instanceof Error ? err.message : 'No se pudo abrir la cámara'
    emit('error', status.value)
  }
}

async function captureFromVideo(): Promise<string> {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas || !video.videoWidth) {
    throw new Error('Cámara no lista')
  }
  const fullW = video.videoWidth
  const fullH = video.videoHeight
  const cropTop = Math.floor(fullH * 0.58)
  const cropH = fullH - cropTop
  canvas.width = fullW
  canvas.height = cropH
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('No se pudo capturar imagen')
  ctx.drawImage(video, 0, cropTop, fullW, cropH, 0, 0, fullW, cropH)
  return canvas.toDataURL('image/jpeg', 0.95)
}

async function submitCameraMrz() {
  loading.value = true
  status.value = 'Capturando y extrayendo MRZ (OCR)…'
  try {
    let imageBase64 = ''
    try {
      imageBase64 = await capturePhotoBase64()
    } catch (err) {
      if (err instanceof Error && err.message === 'USE_INLINE_CAMERA') {
        imageBase64 = await captureFromVideo()
      } else {
        throw err
      }
    }
    const result = await scanFlowApi.scanDniImage(imageBase64, {
      email: email.value.trim() || undefined,
      phone: phone.value.trim() || undefined,
    })
    lastResult.value = result
    emit('parsed', result)
    status.value = String(result.message || 'DNI procesado por OCR')
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Error OCR DNI'
    status.value = msg
    emit('error', msg)
    if (msg.toLowerCase().includes('checksum') || msg.toLowerCase().includes('mrz')) {
      status.value = `${msg}. Prueba MRZ manual o vuelve a capturar con más luz.`
    }
  } finally {
    loading.value = false
  }
}

async function submitMrz() {
  const normalizedMrz = normalizeMrzInput(mrz.value)
  if (!normalizedMrz) {
    status.value = 'MRZ requerido'
    emit('error', status.value)
    return
  }
  const lines = normalizedMrz.split('\n').filter(Boolean)
  if (lines.length === 2 && Math.max(lines[0]?.length || 0, lines[1]?.length || 0) < 36) {
    status.value = 'Para DNIe español pega las 3 líneas completas del MRZ'
    emit('error', status.value)
    return
  }
  loading.value = true
  status.value = 'Validando MRZ y creando cliente…'
  try {
    const result = await scanFlowApi.scanDni(normalizedMrz, {
      email: email.value.trim() || undefined,
      phone: phone.value.trim() || undefined,
    })
    lastResult.value = result
    emit('parsed', result)
    status.value = String(result.message || 'DNI procesado')
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Error parseando DNI'
    status.value = msg
    emit('error', msg)
  } finally {
    loading.value = false
  }
}

function switchMode(next: 'manual' | 'camera') {
  mode.value = next
  if (next === 'camera') {
    startCamera()
  } else {
    stopCamera()
    status.value = 'Pega las 3 líneas completas del MRZ del reverso del DNIe'
  }
}

onMounted(async () => {
  runtime.value = await getScanRuntime()
})

onBeforeUnmount(stopCamera)
</script>

<template>
  <div class="parser-dni">
    <p class="status">{{ status }}</p>
    <p class="runtime">Modo: {{ runtime.native ? `nativo (${runtime.platform})` : 'web/PWA' }}</p>

    <nav class="mode-tabs">
      <button type="button" :class="{ active: mode === 'manual' }" @click="switchMode('manual')">MRZ manual</button>
      <button type="button" :class="{ active: mode === 'camera' }" @click="switchMode('camera')">Cámara OCR</button>
    </nav>

    <template v-if="mode === 'manual'">
      <label>MRZ del DNIe (3 líneas completas)</label>
      <textarea
        v-model="mrz"
        class="mrz-input"
        rows="4"
        placeholder="I&lt;ESPABC123456&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&#10;9001011M3001017ESP&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;2&#10;APELLIDO&lt;&lt;NOMBRE&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;"
        spellcheck="false"
      />
      <small class="hint">El texto gris no cuenta como MRZ. Pega las líneas o carga el ejemplo.</small>
      <button type="button" class="btn demo" @click="fillDemoMrz">Cargar MRZ de ejemplo</button>
      <button type="button" class="btn" :disabled="loading" @click="submitMrz">
        {{ loading ? 'Procesando…' : 'Crear cliente desde DNI' }}
      </button>
    </template>

    <template v-else>
      <div class="camera-wrap">
        <video ref="videoRef" class="preview" playsinline muted />
        <canvas ref="canvasRef" class="hidden-canvas" />
        <div class="mrz-guide">Zona MRZ (reverso)</div>
      </div>
      <small class="hint">Consejo: apoya el DNI, evita reflejos y captura solo el reverso con las 3 líneas.</small>
      <button type="button" class="btn secondary" @click="startCamera">Reiniciar cámara</button>
      <button type="button" class="btn" :disabled="loading || !cameraActive" @click="submitCameraMrz">
        {{ loading ? 'OCR en curso…' : 'Capturar reverso y crear cliente' }}
      </button>
    </template>

    <div class="row">
      <div class="field">
        <label>Email (opcional)</label>
        <input v-model="email" type="email" class="input" placeholder="cliente@empresa.com" />
      </div>
      <div class="field">
        <label>Teléfono (opcional)</label>
        <input v-model="phone" type="tel" class="input" placeholder="+34 600 000 000" />
      </div>
    </div>

    <pre v-if="lastResult" class="result">{{ JSON.stringify(lastResult, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.parser-dni { display: flex; flex-direction: column; gap: 0.75rem; }
.status { margin: 0; color: #cbd5e1; }
.runtime { margin: 0; color: #64748b; font-size: 0.8rem; }
.mode-tabs { display: flex; gap: 0.5rem; }
.mode-tabs button {
  border: 1px solid #334155; background: #1e293b; color: #cbd5e1;
  border-radius: 999px; padding: 0.35rem 0.85rem; cursor: pointer;
}
.mode-tabs button.active { background: #10b981; color: #fff; border-color: #10b981; }
.hint { color: #94a3b8; font-size: 0.8rem; margin-top: -0.25rem; }
.mrz-input, .input {
  width: 100%; padding: 0.5rem 0.75rem; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; color: #f8fafc; font-family: ui-monospace, monospace; font-size: 0.85rem;
}
.camera-wrap { position: relative; background: #111; border-radius: 12px; overflow: hidden; }
.preview { width: 100%; max-height: 280px; object-fit: cover; display: block; }
.mrz-guide {
  position: absolute; left: 8%; right: 8%; bottom: 8%; height: 34%;
  border: 2px dashed #22d3ee; border-radius: 8px;
  color: #7dd3fc; font-size: 0.75rem; display: flex; align-items: flex-end; justify-content: center;
  padding-bottom: 6px; pointer-events: none;
}
.hidden-canvas { display: none; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.field { display: flex; flex-direction: column; gap: 0.35rem; }
.btn {
  align-self: flex-start; background: #10b981; color: #fff; border: none;
  padding: 0.55rem 1.1rem; border-radius: 8px; cursor: pointer; font-weight: 600;
}
.btn.secondary { background: #334155; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn.demo {
  align-self: flex-start; background: #334155; color: #fff; border: none;
  padding: 0.45rem 0.9rem; border-radius: 8px; cursor: pointer; font-weight: 600;
}
.result {
  background: #0f172a; color: #e2e8f0; padding: 0.75rem; border-radius: 8px;
  font-size: 0.75rem; overflow: auto; max-height: 240px;
}
@media (max-width: 640px) { .row { grid-template-columns: 1fr; } }
</style>
