<template>
  <button
    type="button"
    class="theme-toggle"
    :aria-label="label"
    :title="label"
    :aria-pressed="isDark"
    :disabled="settingsStore.isPatching"
    @click="toggle"
  >
    <!-- Luna: estás en platino, pulsa para oscuro -->
    <svg v-if="!isDark" viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
      <path
        d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <!-- Sol: estás en oscuro, pulsa para platino -->
    <svg v-else viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
      <g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
      </g>
    </svg>
  </button>
</template>

<script setup lang="ts">
/**
 * Toggle sol/luna de la barra superior. Persiste de verdad: PATCH
 * /api/v1/settings (preferencia del usuario en backend) + localStorage
 * 'zeus_theme' (lo lee el script inline de index.html para pintar sin
 * flash). Si el PATCH falla, el store revierte el cambio (no se finge).
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settings'

const { t } = useI18n()
const settingsStore = useSettingsStore()

// Tema efectivo pintado (resuelve también 'auto'): se lee de <html>.
const resolved = ref<string>(document.documentElement.getAttribute('data-theme') || 'light')
let observer: MutationObserver | null = null

onMounted(() => {
  observer = new MutationObserver(() => {
    resolved.value = document.documentElement.getAttribute('data-theme') || 'light'
  })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onUnmounted(() => {
  observer?.disconnect()
  observer = null
})

const isDark = computed(() => resolved.value === 'dark')
const label = computed(() =>
  isDark.value ? t('userSettings.switchToLight') : t('userSettings.switchToDark'),
)

async function toggle() {
  await settingsStore.patchPartial({ theme: isDark.value ? 'light' : 'dark' })
}
</script>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--zeus-surface-2, var(--panel-2));
  border: 1px solid var(--zeus-border, var(--line));
  color: var(--zeus-text, var(--fg));
  cursor: pointer;
  transition: background var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.theme-toggle:hover:not(:disabled) {
  background: var(--zeus-accent-soft);
  border-color: var(--zeus-border-strong);
  color: var(--zeus-accent);
}

.theme-toggle:focus-visible {
  outline: 2px solid var(--zeus-accent);
  outline-offset: 2px;
}

.theme-toggle:disabled {
  opacity: 0.6;
  cursor: progress;
}
</style>
