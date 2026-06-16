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
const status = ref('Pega las líneas MRZ del reverso del DNIe')
const loading = ref(false)
const lastResult = ref<Record<string, unknown> | null>(null)

async function submitMrz() {
  if (!mrz.value.trim()) {
    status.value = 'MRZ requerido'
    emit('error', status.value)
    return
  }
  loading.value = true
  status.value = 'Validando MRZ y creando cliente…'
  try {
    const result = await scanFlowApi.scanDni(mrz.value.trim(), {
      email: email.value || undefined,
      phone: phone.value || undefined,
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
    <label>MRZ (líneas del DNIe)</label>
    <textarea
      v-model="mrz"
      class="mrz-input"
      rows="4"
      placeholder="IDESP12345678Z&#10;7408122M2504159ESP…"
      spellcheck="false"
    />
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
.result {
  background: #0f172a; color: #e2e8f0; padding: 0.75rem; border-radius: 8px;
  font-size: 0.75rem; overflow: auto; max-height: 240px;
}
@media (max-width: 640px) { .row { grid-template-columns: 1fr; } }
</style>
