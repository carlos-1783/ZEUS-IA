<template>
  <div class="pwa-controls" :class="{ 'pwa-controls--compact': compact }">
    <button
      v-if="!isInstalled"
      type="button"
      class="pwa-btn pwa-btn--install"
      :disabled="installing"
      :title="installTitle"
      @click="installApp"
    >
      📲 {{ t('dashboardPro.pwa.install') }}
    </button>
    <button
      type="button"
      class="pwa-btn pwa-btn--cache"
      :title="t('dashboardPro.pwa.clearCacheTitle')"
      @click="openClearPwaCachePage"
    >
      🧹 {{ t('dashboardPro.pwa.clearCache') }}
    </button>
    <div
      v-if="showStatus"
      class="pwa-status"
      :class="systemOnline ? 'online' : 'degraded'"
    >
      ● {{ systemOnline ? t('dashboardPro.systemOnline') : systemDetail }}
    </div>
    <div
      v-if="!isProd && showDebug"
      class="pwa-debug"
      :title="`PWA: installable=${isInstallable}, installed=${isInstalled}`"
    >
      🔧 {{ debugLabel }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { openClearPwaCachePage, usePWA } from '@/composables/usePWA'

const props = defineProps({
  systemOnline: { type: Boolean, default: true },
  systemDetail: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  showStatus: { type: Boolean, default: true },
  showDebug: { type: Boolean, default: true },
})

const { t } = useI18n()
const { isInstallable, isInstalled, promptInstall } = usePWA()
const isProd = import.meta.env.PROD
const installing = ref(false)

const installTitle = computed(() => {
  if (isInstallable.value) return t('dashboardPro.pwa.installTitle')
  return `${t('dashboardPro.pwa.installTitle')} — ${t('dashboardPro.pwa.stateUnavailable')}`
})

const debugLabel = computed(() => {
  if (isInstalled.value) return t('dashboardPro.pwa.stateInstalled')
  if (isInstallable.value) return t('dashboardPro.pwa.stateInstallable')
  return t('dashboardPro.pwa.stateUnavailable')
})

const installApp = async () => {
  installing.value = true
  try {
    const ok = await promptInstall()
    if (ok) return
    alert(
      'No se pudo mostrar el instalador automático.\n\n' +
        'Instálala manualmente desde el menú del navegador:\n' +
        '• Chrome/Edge: Menú (⋮) → Instalar aplicación\n' +
        '• También puedes pulsar «Limpiar caché» para abrir la herramienta PWA.'
    )
  } finally {
    installing.value = false
  }
}
</script>

<style scoped>
.pwa-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pwa-controls--compact {
  gap: 6px;
}

.pwa-btn {
  padding: 6px 12px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  white-space: nowrap;
}

.pwa-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.pwa-btn--install {
  background: rgba(59, 130, 246, 0.9);
  border-color: rgba(59, 130, 246, 0.4);
  color: #fff;
}

.pwa-btn--install:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.75);
  transform: scale(1.03);
}

.pwa-btn--cache {
  background: rgba(255, 165, 0, 0.12);
  border-color: rgba(255, 165, 0, 0.35);
  color: #ffa500;
}

.pwa-btn--cache:hover:not(:disabled) {
  background: rgba(255, 165, 0, 0.22);
}

.pwa-status {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.pwa-status.online {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.pwa-status.degraded {
  background: rgba(255, 165, 0, 0.15);
  color: #ffa500;
  border: 1px solid rgba(255, 165, 0, 0.3);
}

.pwa-debug {
  padding: 4px 8px;
  background: rgba(255, 165, 0, 0.15);
  border: 1px solid rgba(255, 165, 0, 0.3);
  border-radius: 10px;
  color: #ffa500;
  font-size: 10px;
  cursor: help;
}
</style>
