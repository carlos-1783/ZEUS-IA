import { ref, onMounted, onUnmounted } from 'vue'

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

declare global {
  interface Window {
    __zeusDeferredInstallPrompt?: BeforeInstallPromptEvent | null
  }
}

const syncFromGlobal = (deferredPrompt: { value: BeforeInstallPromptEvent | null }, isInstallable: { value: boolean }) => {
  if (window.__zeusDeferredInstallPrompt) {
    deferredPrompt.value = window.__zeusDeferredInstallPrompt
    isInstallable.value = true
  }
}

export async function clearPWACache(): Promise<void> {
  if ('caches' in window) {
    const names = await caches.keys()
    await Promise.all(names.map((name) => caches.delete(name)))
  }
  if ('serviceWorker' in navigator) {
    const regs = await navigator.serviceWorker.getRegistrations()
    await Promise.all(regs.map((r) => r.unregister()))
  }
  localStorage.removeItem('zeus-pwa-installed')
  window.__zeusDeferredInstallPrompt = null
  window.location.reload()
}

/**
 * Composable para manejar la instalación de la PWA
 * Detecta cuando la app puede ser instalada y proporciona métodos para mostrar el prompt
 */
export function usePWA() {
  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)

  const isStandaloneMode = () =>
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    ((window.navigator as Navigator & { standalone?: boolean }).standalone === true)

  const checkIfInstalled = () => {
    if (isStandaloneMode()) {
      isInstalled.value = true
      localStorage.setItem('zeus-pwa-installed', 'true')
      return true
    }
    isInstalled.value = false
    return false
  }

  const handleBeforeInstallPrompt = (e: Event) => {
    e.preventDefault()
    deferredPrompt.value = e as BeforeInstallPromptEvent
    window.__zeusDeferredInstallPrompt = deferredPrompt.value
    isInstallable.value = true
  }

  const handleInstallableCustom = (e: Event) => {
    const detail = (e as CustomEvent<BeforeInstallPromptEvent>).detail
    if (detail) {
      deferredPrompt.value = detail
      window.__zeusDeferredInstallPrompt = detail
      isInstallable.value = true
    } else {
      syncFromGlobal(deferredPrompt, isInstallable)
    }
  }

  const handleAppInstalled = () => {
    isInstalled.value = true
    isInstallable.value = false
    deferredPrompt.value = null
    window.__zeusDeferredInstallPrompt = null
    localStorage.setItem('zeus-pwa-installed', 'true')
  }

  const promptInstall = async (): Promise<boolean> => {
    syncFromGlobal(deferredPrompt, isInstallable)
    if (!deferredPrompt.value) {
      console.warn('⚠️ No hay prompt de instalación disponible')
      return false
    }

    try {
      await deferredPrompt.value.prompt()
      const choiceResult = await deferredPrompt.value.userChoice

      if (choiceResult.outcome === 'accepted') {
        isInstallable.value = false
        deferredPrompt.value = null
        window.__zeusDeferredInstallPrompt = null
        return true
      }
      return false
    } catch (error) {
      console.error('❌ Error mostrando el prompt:', error)
      return false
    }
  }

  onMounted(() => {
    checkIfInstalled()
    syncFromGlobal(deferredPrompt, isInstallable)

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('zeus-pwa-installable', handleInstallableCustom as EventListener)
    window.addEventListener('appinstalled', handleAppInstalled)
    window.addEventListener('zeus-pwa-installed', handleAppInstalled)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.removeEventListener('zeus-pwa-installable', handleInstallableCustom as EventListener)
    window.removeEventListener('appinstalled', handleAppInstalled)
    window.removeEventListener('zeus-pwa-installed', handleAppInstalled)
  })

  return {
    isInstallable,
    isInstalled,
    promptInstall,
    checkIfInstalled,
    clearPWACache,
  }
}
