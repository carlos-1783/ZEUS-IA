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
   <div class="scan-hub-content">
    <header class="header">
      <h1>Escaneo físico</h1>
      <p>QR · NFC · DNI — flujo real v2 (pipeline unificado + OCR)</p>
    </header>

    <nav class="tabs">
      <button type="button" class="zeus-btn zeus-btn-secondary" :class="{ 'zeus-btn-secondary--selected': tab === 'qr' }" @click="tab = 'qr'">Cámara QR</button>
      <button type="button" class="zeus-btn zeus-btn-secondary" :class="{ 'zeus-btn-secondary--selected': tab === 'nfc' }" @click="tab = 'nfc'">NFC</button>
      <button type="button" class="zeus-btn zeus-btn-secondary" :class="{ 'zeus-btn-secondary--selected': tab === 'dni' }" @click="tab = 'dni'">DNI / MRZ</button>
    </nav>

    <section class="panel">
      <ScannerQR v-if="tab === 'qr'" @scanned="onSuccess" @error="onError" />
      <ScannerNFC v-else-if="tab === 'nfc'" @scanned="onSuccess" @error="onError" />
      <ParserDNI v-else @parsed="onSuccess" @error="onError" />
    </section>

    <p v-if="feedback" class="feedback">{{ feedback }}</p>
   </div>
  </div>
</template>

<style scoped>
/* Fondo de bandas metalicas obligatorio en toda pagina (ver
   zeus-light-system.css) -- ScanHub.vue no tenia ningun token del
   sistema nuevo y fijaba un tema oscuro permanente. */
.scan-hub {
  position: relative;
  left: 50%;
  right: 50%;
  width: 100vw;
  margin-left: -50vw;
  margin-right: -50vw;
  min-height: 100vh;
  overflow: hidden;
  background-image: var(--zeus-bg);
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  color: var(--zeus-text, #0f172a);
  box-sizing: border-box;
}
.scan-hub::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}
.scan-hub-content {
  position: relative;
  max-width: 720px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
.header h1 { margin: 0 0 0.25rem; font-size: var(--zeus-text-xl, 1.5rem); color: var(--zeus-text, #0f172a); }
.header p { margin: 0; color: var(--zeus-text-secondary, #52607a); font-size: 0.95rem; }
.tabs { display: flex; gap: 0.5rem; margin: 1.25rem 0; flex-wrap: wrap; }
.tabs button { border-radius: var(--zeus-radius-full, 999px); }
.panel {
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-lg, 16px);
  padding: 1rem;
  box-shadow: var(--zeus-shadow, 0 1px 3px rgba(15, 23, 42, 0.06));
}
.feedback {
  margin-top: 1rem; padding: 0.75rem 1rem;
  background: var(--zeus-accent-soft, #eef1ff);
  color: var(--zeus-text, #0f172a);
  border-radius: var(--zeus-radius-sm, 8px);
  border-left: 3px solid var(--zeus-accent, #4f46e5);
}
</style>
