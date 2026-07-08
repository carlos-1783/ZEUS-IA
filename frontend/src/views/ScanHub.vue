<script setup lang="ts">
import { ref } from 'vue'
import ScannerQR from '@/components/scan/ScannerQR.vue'
import ScannerNFC from '@/components/scan/ScannerNFC.vue'
import ParserDNI from '@/components/scan/ParserDNI.vue'

const tab = ref<'qr' | 'nfc' | 'dni'>('qr')
const feedback = ref('')

function onSuccess(msg: Record<string, unknown>) {
  feedback.value = String(msg.message || 'Operación completada')
}

function onError(msg: string) {
  feedback.value = msg
}
</script>

<template>
  <div class="scan-hub">
    <header class="header">
      <h1>Escaneo físico</h1>
      <p>QR · NFC · DNI — flujo real v2 (pipeline unificado + OCR)</p>
    </header>

    <nav class="tabs">
      <button type="button" :class="{ active: tab === 'qr' }" @click="tab = 'qr'">Cámara QR</button>
      <button type="button" :class="{ active: tab === 'nfc' }" @click="tab = 'nfc'">NFC</button>
      <button type="button" :class="{ active: tab === 'dni' }" @click="tab = 'dni'">DNI / MRZ</button>
    </nav>

    <section class="panel">
      <ScannerQR v-if="tab === 'qr'" @scanned="onSuccess" @error="onError" />
      <ScannerNFC v-else-if="tab === 'nfc'" @scanned="onSuccess" @error="onError" />
      <ParserDNI v-else @parsed="onSuccess" @error="onError" />
    </section>

    <p v-if="feedback" class="feedback">{{ feedback }}</p>
  </div>
</template>

<style scoped>
.scan-hub {
  max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem 3rem;
  color: #f1f5f9;
}
.header h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
.header p { margin: 0; color: #94a3b8; font-size: 0.95rem; }
.tabs { display: flex; gap: 0.5rem; margin: 1.25rem 0; flex-wrap: wrap; }
.tabs button {
  background: #1e293b; color: #cbd5e1; border: 1px solid #334155;
  padding: 0.45rem 0.9rem; border-radius: 999px; cursor: pointer;
}
.tabs button.active { background: #0ea5e9; color: #fff; border-color: #0ea5e9; }
.panel {
  background: #111827; border: 1px solid #1f2937; border-radius: 16px; padding: 1rem;
}
.feedback {
  margin-top: 1rem; padding: 0.75rem 1rem; background: #0f172a;
  border-radius: 8px; border-left: 3px solid #22d3ee;
}
</style>
