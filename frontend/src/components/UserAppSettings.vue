<template>
  <div class="user-app-settings">
    <div class="settings-card">
      <h3>🎨 {{ $t('userSettings.appearance') }}</h3>
      <div class="setting-item">
        <label for="us-theme">{{ $t('userSettings.theme') }}</label>
        <select
          id="us-theme"
          class="setting-select"
          :value="settingsStore.settings.theme"
          :disabled="settingsStore.isPatching"
          @change="onThemeChange"
        >
          <option value="dark">{{ $t('userSettings.themeDark') }}</option>
          <option value="light">{{ $t('userSettings.themeLight') }}</option>
          <option value="auto">{{ $t('userSettings.themeAuto') }}</option>
        </select>
      </div>
      <div class="setting-item">
        <label for="us-lang">{{ $t('userSettings.language') }}</label>
        <select
          id="us-lang"
          class="setting-select"
          :value="settingsStore.settings.language"
          :disabled="settingsStore.isPatching"
          @change="onLanguageChange"
        >
          <option v-for="lang in supportedLanguages" :key="lang" :value="lang">
            {{ lang === 'es' ? 'Español' : lang === 'en' ? 'English' : lang.toUpperCase() }}
          </option>
        </select>
      </div>
    </div>

    <div class="settings-card">
      <h3>🔐 {{ $t('userSettings.security') }}</h3>
      <div class="setting-item setting-item-row">
        <label for="us-2fa">{{ $t('userSettings.twoFactor') }}</label>
        <input
          id="us-2fa"
          type="checkbox"
          :checked="settingsStore.settings.two_factor_enabled"
          :disabled="settingsStore.isPatching"
          @change="onTwoFactorChange"
        />
      </div>
      <p class="setting-hint">{{ $t('userSettings.twoFactorHint') }}</p>
      <div class="setting-item">
        <label for="us-timeout">{{ $t('userSettings.sessionTimeout') }}</label>
        <select
          id="us-timeout"
          class="setting-select"
          :value="String(settingsStore.settings.session_timeout)"
          :disabled="settingsStore.isPatching"
          @change="onSessionTimeoutChange"
        >
          <option value="15">15 {{ $t('userSettings.minutes') }}</option>
          <option value="30">30 {{ $t('userSettings.minutes') }}</option>
          <option value="60">60 {{ $t('userSettings.minutes') }}</option>
          <option value="120">120 {{ $t('userSettings.minutes') }}</option>
          <option value="240">240 {{ $t('userSettings.minutes') }}</option>
        </select>
      </div>
      <p class="setting-hint">{{ $t('userSettings.sessionTimeoutHint') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { getSupportedLocales } from '@/i18n'
import { useNotifications } from '@/composables/useNotifications'
import { useSettingsStore } from '@/stores/settings'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const { error: notifyError } = useNotifications()
const settingsStore = useSettingsStore()
const supportedLanguages = getSupportedLocales()

async function onThemeChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  const ok = await settingsStore.patchPartial({ theme: v as 'dark' | 'light' | 'auto' })
  if (!ok) notifyError(t('userSettings.saveError'))
}

async function onLanguageChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  const ok = await settingsStore.patchPartial({ language: v })
  if (!ok) notifyError(t('userSettings.saveError'))
}

async function onTwoFactorChange(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  const ok = await settingsStore.patchPartial({ two_factor_enabled: checked })
  if (!ok) notifyError(t('userSettings.saveError'))
}

async function onSessionTimeoutChange(e: Event) {
  const raw = (e.target as HTMLSelectElement).value
  const minutes = parseInt(raw, 10)
  const ok = await settingsStore.patchPartial({ session_timeout: minutes })
  if (!ok) notifyError(t('userSettings.saveError'))
}
</script>

<style scoped>
.user-app-settings {
  display: contents;
}

.settings-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.settings-card h3 {
  margin: 0 0 16px 0;
  color: #fff;
  font-size: 1.1rem;
}

.setting-item {
  margin-bottom: 14px;
}

.setting-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.setting-item label {
  display: block;
  margin-bottom: 6px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.9rem;
}

.setting-item-row label {
  margin-bottom: 0;
}

.setting-select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.35);
  color: #fff;
  font-size: 0.95rem;
}

.setting-hint {
  margin: -8px 0 12px;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.35;
}
</style>
