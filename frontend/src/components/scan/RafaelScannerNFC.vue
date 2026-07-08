<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { scanFlowApi } from '@/api/scanFlow'
import { workspaceTools } from '@/api/workspaceTools'

const emit = defineEmits<{
  (e: 'scanned', result: Record<string, unknown>): void
  (e: 'error', message: string): void
}>()

const status = ref('Acerca etiqueta NFC fiscal (TPV, cobro, cliente)…')
const supported = ref(false)
const fallbackHex = ref('')
const fallbackText = ref('')
const lastResult = ref<Record<string, unknown> | null>(null)

interface NdefRecordLike { recordType?: string; data?: DataView }
interface NdefReadingEventLike { message?: { records?: NdefRecordLike[] } }
interface NdefReaderLike {
  scan: (opts?: { signal?: AbortSignal }) => Promise<void>
  addEventListener: (type: string, listener: (ev: NdefReadingEventLike) => void) => void
}

let abort: AbortController | null = null
let handled = false

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

function toHex(text: string): string {
  return [...new TextEncoder().encode(text)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

async function processFiscalPayload(text: string) {
  const trimmed = text.trim()
  if (!trimmed) throw new Error('Etiqueta NFC vacía')
  if (handled) return
  handled = true

  status.value = 'Procesando etiqueta NFC (RAFAEL)…'
  let result: Record<string, unknown>

  if (trimmed.toUpperCase().startsWith('ZEUS|') || trimmed.toUpperCase().startsWith('ZEUSQR|')) {
    result = await scanFlowApi.scanQr(trimmed)
  } else {
    const out = await workspaceTools.runRafaelNfcScanner({ payload_hex: toHex(trimmed) })
    result = { ...(out as Record<string, unknown>), message: (out as any)?.text, ...(out as any)?.result }
  }

  lastResult.value = result
  emit('scanned', result)
  status.value = String(result.message || 'NFC fiscal procesado')
}

async function submitText() {
  if (!fallbackText.value.trim()) {
    emit('error', 'Introduce el contenido de la etiqueta NFC')
    return
  }
  try {
    await processFiscalPayload(fallbackText.value.trim())
  } catch (err) {
    handled = false
    const msg = err instanceof Error ? err.message : 'Error procesando NFC'
    status.value = msg
    emit('error', msg)
  }
}

async function startNfc() {
  handled = false
  const NdefReaderCtor = (window as unknown as { NDEFReader?: new () => NdefReaderLike }).NDEFReader
  if (!NdefReaderCtor) {
    supported.value = false
    status.value = 'Web NFC no disponible — introduce el payload HEX manual'
    return
  }
  supported.value = true
  abort = new AbortController()
  status.value = 'Acerca la etiqueta al móvil…'
  try {
    const reader = new NdefReaderCtor()
    reader.addEventListener('reading', async (event) => {
      if (handled) return
      const text = recordsToText(event.message?.records || [])
      if (text) {
        try {
          await processFiscalPayload(text)
        } catch (err) {
          handled = false
          const msg = err instanceof Error ? err.message : 'Error procesando NFC'
          status.value = msg
          emit('error', msg)
        }
      }
    })
    await reader.scan({ signal: abort.signal })
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      const msg = err instanceof Error ? err.message : 'Error NFC'
      status.value = msg
      emit('error', msg)
    }
  }
}

async function submitHex() {
  if (!fallbackHex.value.trim()) {
    emit('error', 'Introduce payload HEX')
    return
  }
  try {
    const bytes = fallbackHex.value.trim()
    const text = new TextDecoder().decode(
      Uint8Array.from(bytes.match(/.{1,2}/g) || [], (h) => parseInt(h, 16)),
    )
    await processFiscalPayload(text || bytes)
  } catch (err) {
    handled = false
    const msg = err instanceof Error ? err.message : 'Error procesando NFC'
    status.value = msg
    emit('error', msg)
  }
}

onMounted(startNfc)
</script>

<template>
  <div class="rafael-nfc">
    <p class="status">{{ status }}</p>
    <p class="hint">RAFAEL: etiquetas con formato <code>ZEUS|Cliente|importe|EUR</code> o payload de terminal.</p>
    <div class="fallback">
      <label>Contenido NFC (manual)</label>
      <input
        v-model="fallbackText"
        class="input"
        placeholder="ZEUS|Cliente Demo|120.00|EUR|cliente@empresa.com"
        spellcheck="false"
      />
      <button type="button" class="btn" @click="submitText">Procesar NFC fiscal manual</button>
    </div>
    <div v-if="!supported" class="fallback">
      <label>Payload HEX (fallback)</label>
      <input v-model="fallbackHex" class="input" placeholder="5a4555537c436c69656e74657c313230" />
      <button type="button" class="btn" @click="submitHex">Procesar NFC fiscal</button>
    </div>
    <button v-else type="button" class="btn" @click="startNfc">Reintentar lectura NFC</button>
    <pre v-if="lastResult" class="result">{{ JSON.stringify(lastResult, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.rafael-nfc { display: flex; flex-direction: column; gap: 0.6rem; color: #e2e8f0; }
.status { margin: 0; }
.hint { margin: 0; font-size: 0.85rem; color: #94a3b8; }
.fallback { display: flex; flex-direction: column; gap: 0.4rem; }
.input {
  padding: 0.5rem; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; color: #f8fafc; font-family: monospace; font-size: 0.85rem;
}
.btn {
  align-self: flex-start; background: #d97706; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; font-weight: 600;
}
.result {
  background: #020617; padding: 0.6rem; border-radius: 8px;
  font-size: 0.75rem; overflow: auto; max-height: 160px;
}
</style>
