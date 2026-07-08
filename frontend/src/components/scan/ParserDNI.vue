<script setup lang="ts">
import { ref } from 'vue'
import { scanFlowApi } from '@/api/scanFlow'

const emit = defineEmits<{
  (e: 'parsed', result: Record<string, unknown>): void
  (e: 'error', message: string): void
}>()

const mrz = ref('')
const email = ref('')
const phone = ref('')
const status = ref('Pega las 3 líneas completas del MRZ del reverso del DNIe')
const loading = ref(false)
const lastResult = ref<Record<string, unknown> | null>(null)

function normalizeMrzInput(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n')
}

const DEMO_MRZ = `I<UTOD231458907<<<<<<<
7408122F1204159UTO<<<<<<<<<<<6
ERIKSSON<<ANNA<MARIA<<<<<<<<<<`

function fillDemoMrz() {
  mrz.value = DEMO_MRZ
  status.value = 'MRZ de ejemplo cargado. Pulsa «Crear cliente desde DNI».'
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
</script>

<template>
  <div class="parser-dni">
    <p class="status">{{ status }}</p>
    <label>MRZ del DNIe (3 líneas completas)</label>
    <textarea
      v-model="mrz"
      class="mrz-input"
      rows="4"
      placeholder="I&lt;ESPABC123456&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&#10;9001011M3001017ESP&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;2&#10;APELLIDO&lt;&lt;NOMBRE&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;"
      spellcheck="false"
    />
    <small class="hint">El texto gris del campo no cuenta como MRZ: debes pegar o cargar el ejemplo.</small>
    <button type="button" class="btn demo" @click="fillDemoMrz">Cargar MRZ de ejemplo</button>
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
    <button type="button" class="btn" :disabled="loading" @click="submitMrz">
      {{ loading ? 'Procesando…' : 'Crear cliente desde DNI' }}
    </button>
    <pre v-if="lastResult" class="result">{{ JSON.stringify(lastResult, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.parser-dni { display: flex; flex-direction: column; gap: 0.75rem; }
.status { margin: 0; color: #cbd5e1; }
.hint { color: #94a3b8; font-size: 0.8rem; margin-top: -0.25rem; }
.mrz-input, .input {
  width: 100%; padding: 0.5rem 0.75rem; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; color: #f8fafc; font-family: ui-monospace, monospace; font-size: 0.85rem;
}
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.field { display: flex; flex-direction: column; gap: 0.35rem; }
.btn {
  align-self: flex-start; background: #10b981; color: #fff; border: none;
  padding: 0.55rem 1.1rem; border-radius: 8px; cursor: pointer; font-weight: 600;
}
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
