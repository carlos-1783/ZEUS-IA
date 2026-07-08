<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { scanFlowApi } from '@/api/scanFlow'
import { getScanRuntime, startNativeNfc } from '@/services/scanHardware'

const emit = defineEmits<{
  (e: 'scanned', result: Record<string, unknown>): void
  (e: 'error', message: string): void
}>()

const status = ref('Iniciando NFC…')
const supported = ref(false)
const scanning = ref(false)
const lastResult = ref<Record<string, unknown> | null>(null)
const checkinType = ref('entrada')
const fallbackText = ref('')

interface NdefRecordLike {
  recordType?: string
  data?: DataView
}

interface NdefReadingEventLike {
  message?: { records?: NdefRecordLike[] }
}

interface NdefReaderLike {
  scan: (opts?: { signal?: AbortSignal }) => Promise<void>
  addEventListener: (type: string, listener: (ev: NdefReadingEventLike) => void) => void
}

let abort: AbortController | null = null
let handled = false
let stopNative: (() => void) | null = null

function recordsToText(records: NdefRecordLike[]): string {
  const parts = records.map(decodeRecord).filter(Boolean)
  return parts[0] || parts.join('')
}

function decodeRecord(record: NdefRecordLike): string {
  if (!record.data) return ''
  const decoder = new TextDecoder()
  if (record.recordType === 'text') {
    const langLen = record.data.getUint8(0) & 0x3f
    return decoder.decode(record.data.buffer.slice(record.data.byteOffset + 1 + langLen))
  }
  return decoder.decode(record.data)
}

async function startNfcScan() {
  handled = false
  stopNative?.()
  stopNative = null
  const runtime = await getScanRuntime()
  const nativeStop = await startNativeNfc((text) => submitNfc(text))
  if (nativeStop) {
    stopNative = nativeStop
    supported.value = true
    scanning.value = true
    status.value = 'NFC nativo activo — acerca la etiqueta…'
    return
  }

  const NdefReaderCtor = (window as unknown as { NDEFReader?: new () => NdefReaderLike }).NDEFReader
  if (!NdefReaderCtor) {
    supported.value = false
    status.value = 'NFC no disponible — usa el campo de texto (etiqueta programada)'
    return
  }
  supported.value = true
  scanning.value = true
  status.value = 'Acerca la etiqueta NFC al dispositivo…'
  abort = new AbortController()
  try {
    const reader = new NdefReaderCtor()
    reader.addEventListener('reading', async (event) => {
      if (handled) return
      const records = event.message?.records || []
      const text = recordsToText(records)
      if (text) await submitNfc(text)
    })
    await reader.scan({ signal: abort.signal })
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    const msg = err instanceof Error ? err.message : 'Error NFC'
    status.value = msg
    emit('error', msg)
    scanning.value = false
  }
}

async function submitNfc(text: string) {
  const payload = text.trim()
  if (!payload) {
    status.value = 'Etiqueta NFC vacía'
    emit('error', status.value)
    return
  }
  if (handled) return
  handled = true
  scanning.value = false
  abort?.abort()
  status.value = 'NFC detectado — procesando…'
  try {
    const payloadHex = [...new TextEncoder().encode(payload)].map((b) => b.toString(16).padStart(2, '0')).join('')
    const result = await scanFlowApi.scanNfc({
      text: payload,
      payload_hex: payloadHex,
      checkin_type: checkinType.value,
    })
    lastResult.value = result
    emit('scanned', result)
    status.value = String(result.message || 'NFC procesado')
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Error procesando NFC'
    status.value = msg
    emit('error', msg)
    handled = false
  }
}

async function submitFallback() {
  if (!fallbackText.value.trim()) {
    status.value = 'Introduce el contenido de la etiqueta NFC'
    return
  }
  await submitNfc(fallbackText.value.trim())
}

function stopScan() {
  abort?.abort()
  stopNative?.()
  stopNative = null
  scanning.value = false
  status.value = 'Escaneo detenido'
}

onMounted(startNfcScan)
onBeforeUnmount(stopScan)
</script>

<template>
  <div class="scanner-nfc">
    <p class="status">{{ status }}</p>
    <div class="field">
      <label>Tipo de fichaje</label>
      <select v-model="checkinType" class="input">
        <option value="entrada">Entrada</option>
        <option value="salida">Salida</option>
        <option value="pausa_inicio">Pausa inicio</option>
        <option value="pausa_fin">Pausa fin</option>
      </select>
    </div>
    <div v-if="!supported" class="fallback">
      <label>Contenido NFC (fallback)</label>
      <input v-model="fallbackText" class="input" placeholder="ZEUSCHECK|W001|2026-05-29T10:00:00Z" />
      <button type="button" class="btn" @click="submitFallback">Procesar etiqueta</button>
    </div>
    <div v-else class="fallback">
      <label>Contenido NFC (manual)</label>
      <input v-model="fallbackText" class="input" placeholder="ZEUSCHECK|W001|2026-05-29T10:00:00Z" />
      <button type="button" class="btn" @click="submitFallback">Procesar sin lector</button>
    </div>
    <div class="actions">
      <button v-if="supported" type="button" class="btn" @click="startNfcScan">Escanear NFC</button>
      <button type="button" class="btn secondary" @click="stopScan">Detener</button>
    </div>
    <p v-if="!supported" class="hint">Web NFC solo en Android/Chrome. En escritorio usa el fallback con el texto de la etiqueta.</p>
    <pre v-if="lastResult" class="result">{{ JSON.stringify(lastResult, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.scanner-nfc { display: flex; flex-direction: column; gap: 0.75rem; }
.status { margin: 0; color: #cbd5e1; }
.field, .fallback { display: flex; flex-direction: column; gap: 0.35rem; }
.input {
  padding: 0.5rem 0.75rem; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; color: #f8fafc;
}
.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.btn {
  background: #8b5cf6; color: #fff; border: none; padding: 0.5rem 1rem;
  border-radius: 8px; cursor: pointer; font-weight: 600;
}
.btn.secondary { background: #334155; }
.hint { font-size: 0.85rem; color: #94a3b8; margin: 0; }
.result {
  background: #0f172a; color: #e2e8f0; padding: 0.75rem; border-radius: 8px;
  font-size: 0.75rem; overflow: auto; max-height: 200px;
}
</style>
