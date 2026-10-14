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

/* Instalar: única acción con el acento del rayo en esta barra.
   Stop claro del degradado oscurecido de #2a74d8 a #2567c4 (AA): el blanco sobre
   #2a74d8 daba 4.58:1, justo en el límite de 4.5:1; con #2567c4 sube a 5.5:1 con
   margen real, mismo tono de azul, mismo degradado/acento. */
.pwa-btn--install {
  background: linear-gradient(170deg, #2567c4, #1559c6);
  border-color: rgba(255, 255, 255, 0.22);
  color: #fff;
  box-shadow: 0 4px 11px -3px var(--volt-glow, rgba(47, 130, 240, 0.5)), inset 0 1px 1px rgba(255, 255, 255, 0.25);
}

.pwa-btn--install:hover:not(:disabled) {
  box-shadow: 0 6px 16px -4px var(--volt-glow, rgba(47, 130, 240, 0.5)), inset 0 1px 1px rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

/* Resto: chapas metálicas pequeñas, texto en tinta (el color va al punto). */
.pwa-btn--cache,
.pwa-status,
.pwa-debug {
  background: var(--metal-face, var(--zeus-surface));
  border: 1px solid var(--metal-edge, var(--zeus-border));
  border-bottom-color: var(--metal-edge-bottom, var(--zeus-border));
  box-shadow: var(--metal-shadow-sm, none);
  color: var(--ink, var(--zeus-text));
}

.pwa-btn--cache:hover:not(:disabled) {
  box-shadow: var(--metal-shadow, none);
}

.pwa-btn:focus-visible {
  outline: 2px solid var(--volt, #2f82f0);
  outline-offset: 2px;
}

.pwa-status {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.pwa-status.online::first-letter {
  color: var(--ok, #10b981);
}

.pwa-status.degraded::first-letter {
  color: var(--warn, #ffa500);
}

.pwa-debug {
  padding: 4px 8px;
  border-radius: 10px;
  color: var(--warn-ink, #ffa500);
  font-size: 10px;
  cursor: help;
}

/* Solo visible con !isProd (nunca en build de producción real). En tema platino, el
   --warn-ink compartido (#683b00) da 3.77:1 contra el extremo mas oscuro del degradado
   metalico de esta chapa (falla AA 4.5:1); en dark ya pasa (6.72:1+), no se toca. Override
   local (no se cambia el token --warn-ink global, que se usa en más sitios) con mas
   contraste: 5.18:1 contra ese mismo extremo. */
:root:not([data-theme="dark"]) .pwa-debug {
  color: #4a2900;
}

@media (prefers-reduced-motion: reduce) {
  .pwa-btn {
    transition: none;
  }

  .pwa-btn--install:hover:not(:disabled) {
    transform: none;
  }
}
</style>
