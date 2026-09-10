<template>
  <div class="settings-page">
    <header class="settings-page-header">
      <button type="button" class="back-btn" @click="goBack">{{ $t('userSettings.back') }}</button>
      <h1>{{ $t('userSettings.pageTitle') }}</h1>
    </header>
    <div class="settings-page-grid">
      <UserAppSettings />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import UserAppSettings from '@/components/UserAppSettings.vue'
import { useSettingsStore } from '@/stores/settings'

const router = useRouter()
const settingsStore = useSettingsStore()

onMounted(() => {
  void settingsStore.bootstrapFromBackend()
})

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/dashboard')
}
</script>

<style scoped>
/* Sistema de diseño Ronda 2: bandas metálicas obligatorias en toda la
   vista (antes degradado oscuro plano #1a1f2e→#0f1419). Botón "Volver"
   secundario blanco/borde — no es la acción de mayor jerarquía. */
.settings-page {
  position: relative;
  overflow: hidden;
  min-height: 100vh;
  padding: 24px 20px 48px;
  background-image: var(--zeus-bg);
  color: var(--zeus-text, #0f172a);
  box-sizing: border-box;
}

.settings-page::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}

.settings-page-header {
  position: relative;
  max-width: 720px;
  margin: 0 auto 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-page-header h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--zeus-text, #0f172a);
}

.back-btn {
  align-self: flex-start;
  padding: 8px 14px;
  border-radius: var(--zeus-radius-sm, 8px);
  border: 1px solid #D1D5DB;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  cursor: pointer;
  font-size: 0.9rem;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.back-btn:hover {
  border-color: #9aa2af;
}

.settings-page-grid {
  position: relative;
  max-width: 720px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}
</style>
