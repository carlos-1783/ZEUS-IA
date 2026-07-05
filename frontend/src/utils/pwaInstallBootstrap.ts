/** Capture beforeinstallprompt before Vue mounts (event fires only once). */

import type { BeforeInstallPromptEvent } from '@/composables/usePWA'

declare global {
  interface Window {
    __zeusDeferredInstallPrompt?: BeforeInstallPromptEvent | null
    __zeusPwaBootstrapReady?: boolean
  }
}

export function bootstrapPWAInstallCapture(): void {
  if (typeof window === 'undefined' || window.__zeusPwaBootstrapReady) return
  window.__zeusPwaBootstrapReady = true

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    const prompt = e as BeforeInstallPromptEvent
    window.__zeusDeferredInstallPrompt = prompt
    window.dispatchEvent(new CustomEvent('zeus-pwa-installable', { detail: prompt }))
    console.log('📱 PWA bootstrap: beforeinstallprompt captured')
  })

  window.addEventListener('appinstalled', () => {
    window.__zeusDeferredInstallPrompt = null
    localStorage.setItem('zeus-pwa-installed', 'true')
    window.dispatchEvent(new CustomEvent('zeus-pwa-installed'))
    console.log('✅ PWA bootstrap: app installed')
  })
}
