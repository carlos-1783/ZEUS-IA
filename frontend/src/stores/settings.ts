import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import i18n, { getSupportedLocales } from '@/i18n'
import api from '@/services/api'

export type AppTheme = 'dark' | 'light' | 'auto'

export interface UserAppSettingsState {
  language: string
  theme: AppTheme
  two_factor_enabled: boolean
  session_timeout: number
}

const DEFAULTS: UserAppSettingsState = {
  language: 'es',
  theme: 'dark',
  two_factor_enabled: false,
  session_timeout: 60,
}

function normalizePayload(raw: unknown): UserAppSettingsState {
  if (!raw || typeof raw !== 'object') return { ...DEFAULTS }
  const o = raw as Record<string, unknown>
  const lang = typeof o.language === 'string' ? o.language : DEFAULTS.language
  const theme = (typeof o.theme === 'string' ? o.theme : DEFAULTS.theme) as AppTheme
  return {
    language: getSupportedLocales().includes(lang) ? lang : DEFAULTS.language,
    theme: ['dark', 'light', 'auto'].includes(theme) ? theme : DEFAULTS.theme,
    two_factor_enabled: Boolean(o.two_factor_enabled),
    session_timeout:
      typeof o.session_timeout === 'number' && o.session_timeout > 0
        ? o.session_timeout
        : DEFAULTS.session_timeout,
  }
}

function applyThemeToDom(theme: AppTheme) {
  const resolved =
    theme === 'auto'
      ? window.matchMedia?.('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : theme
  document.documentElement.setAttribute('data-theme', resolved)
  try {
    localStorage.setItem('zeus_theme', theme)
  } catch {
    /* ignore */
  }
}

function applyLanguageToI18n(language: string) {
  const supported = getSupportedLocales()
  const lang = supported.includes(language) ? language : DEFAULTS.language
  i18n.global.locale.value = lang as 'es' | 'en'
  try {
    localStorage.setItem('zeus_locale', lang)
  } catch {
    /* ignore */
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<UserAppSettingsState>({ ...DEFAULTS })
  const hasSynced = ref(false)
  const isPatching = ref(false)
  const lastError = shallowRef<string | null>(null)

  let idleInterval: ReturnType<typeof setInterval> | null = null
  let lastActivity = Date.now()

  function bumpActivity() {
    lastActivity = Date.now()
  }

  function clearIdleWatcher() {
    if (idleInterval) {
      clearInterval(idleInterval)
      idleInterval = null
    }
    window.removeEventListener('pointerdown', bumpActivity)
    window.removeEventListener('keydown', bumpActivity)
  }

  function armIdleWatcher() {
    clearIdleWatcher()
    window.addEventListener('pointerdown', bumpActivity, { passive: true })
    window.addEventListener('keydown', bumpActivity)
    lastActivity = Date.now()
    idleInterval = setInterval(() => {
      const mins = settings.value.session_timeout || DEFAULTS.session_timeout
      const maxMs = mins * 60 * 1000
      if (Date.now() - lastActivity >= maxMs) {
        console.warn('[settingsStore] idle timeout, forcing logout flow')
        window.dispatchEvent(new CustomEvent('unauthorized'))
      }
    }, 30_000)
  }

  function applyFromState() {
    applyThemeToDom(settings.value.theme)
    applyLanguageToI18n(settings.value.language)
    armIdleWatcher()
  }

  function applyLocalFallback() {
    try {
      const loc = localStorage.getItem('zeus_locale')
      const th = localStorage.getItem('zeus_theme') as AppTheme | null
      const st = localStorage.getItem('zeus_session_timeout')
      if (loc && getSupportedLocales().includes(loc)) settings.value.language = loc
      if (th && ['dark', 'light', 'auto'].includes(th)) settings.value.theme = th
      if (st) {
        const n = parseInt(st, 10)
        if (Number.isFinite(n) && n >= 5) settings.value.session_timeout = n
      }
    } catch {
      /* ignore */
    }
    applyFromState()
  }

  async function bootstrapFromBackend(): Promise<void> {
    lastError.value = null
    try {
      const data = await api.get('/api/v1/settings')
      console.log('[settingsStore] GET /api/v1/settings', data)
      settings.value = normalizePayload(data)
      hasSynced.value = true
      applyFromState()
    } catch (e: unknown) {
      console.warn('[settingsStore] GET /settings failed, using local fallback', e)
      hasSynced.value = false
      applyLocalFallback()
    }
  }

  async function patchPartial(
    partial: Partial<UserAppSettingsState>,
  ): Promise<boolean> {
    const prev = { ...settings.value }
    Object.assign(settings.value, partial)
    applyFromState()
    isPatching.value = true
    lastError.value = null
    try {
      const body: Record<string, unknown> = {}
      if (partial.language !== undefined) body.language = partial.language
      if (partial.theme !== undefined) body.theme = partial.theme
      if (partial.two_factor_enabled !== undefined)
        body.two_factor_enabled = partial.two_factor_enabled
      if (partial.session_timeout !== undefined) body.session_timeout = partial.session_timeout
      const merged = await api.patch('/api/v1/settings', body)
      console.log('[settingsStore] PATCH /api/v1/settings', body, merged)
      settings.value = normalizePayload(merged)
      applyFromState()
      try {
        localStorage.setItem('zeus_session_timeout', String(settings.value.session_timeout))
      } catch {
        /* ignore */
      }
      return true
    } catch (e: unknown) {
      console.error('[settingsStore] PATCH failed, reverting', e)
      settings.value = prev
      applyFromState()
      lastError.value = e instanceof Error ? e.message : 'Error al guardar ajustes'
      return false
    } finally {
      isPatching.value = false
    }
  }

  function reset() {
    clearIdleWatcher()
    settings.value = { ...DEFAULTS }
    hasSynced.value = false
    lastError.value = null
  }

  return {
    settings,
    hasSynced,
    isPatching,
    lastError,
    bootstrapFromBackend,
    patchPartial,
    applyFromState,
    reset,
  }
})
