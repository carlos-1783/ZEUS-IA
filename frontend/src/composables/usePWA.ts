import { ref, onMounted, onUnmounted } from 'vue'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

declare global {
  interface Window {
    __zeusDeferredInstallPrompt?: BeforeInstallPromptEvent | null
  }
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
    ((window.navigator as any).standalone === true)

  // Detectar si la app ya está instalada
  const checkIfInstalled = () => {
    if (isStandaloneMode()) {
      isInstalled.value = true
      localStorage.setItem('zeus-pwa-installed', 'true')
      return true
    }

    // Evitar falso positivo por localStorage residual: si no hay modo standalone, no está instalada.
    isInstalled.value = false
    return false
  }

  // Manejar el evento beforeinstallprompt
  const handleBeforeInstallPrompt = (e: Event) => {
    console.log('📱 PWA: Evento beforeinstallprompt recibido!')
    e.preventDefault()
    deferredPrompt.value = e as BeforeInstallPromptEvent
    window.__zeusDeferredInstallPrompt = deferredPrompt.value
    isInstallable.value = true
    console.log('✅ PWA: isInstallable establecido en true')
  }

  // Manejar cuando la app es instalada
  const handleAppInstalled = () => {
    isInstalled.value = true
    isInstallable.value = false
    deferredPrompt.value = null
    window.__zeusDeferredInstallPrompt = null
    localStorage.setItem('zeus-pwa-installed', 'true')
    console.log('✅ PWA instalada')
  }

  // Mostrar el prompt de instalación
  const promptInstall = async (): Promise<boolean> => {
    if (!deferredPrompt.value) {
      console.warn('⚠️ No hay prompt de instalación disponible')
      return false
    }

    try {
      // Mostrar el prompt
      await deferredPrompt.value.prompt()
      
      // Esperar la respuesta del usuario
      const choiceResult = await deferredPrompt.value.userChoice
      
      if (choiceResult.outcome === 'accepted') {
        console.log('✅ Usuario aceptó la instalación')
        isInstallable.value = false
        deferredPrompt.value = null
        return true
      } else {
        console.log('❌ Usuario rechazó la instalación')
        return false
      }
    } catch (error) {
      console.error('❌ Error mostrando el prompt:', error)
      return false
    }
  }

  // Inicializar
  onMounted(() => {
    console.log('🔧 usePWA: Inicializando...')
    const alreadyInstalled = checkIfInstalled()
    console.log('🔧 usePWA: Ya instalada?', alreadyInstalled, 'isInstalled:', isInstalled.value)
    
    // IMPORTANTE: El evento beforeinstallprompt solo se dispara UNA VEZ
    // Si el usuario ya lo rechazó o el navegador ya lo procesó, no se volverá a disparar
    // hasta que se limpien los datos del sitio o se instale la app
    
    // Recuperar prompt capturado previamente (si el evento llegó antes de montar el componente)
    if (window.__zeusDeferredInstallPrompt) {
      deferredPrompt.value = window.__zeusDeferredInstallPrompt
      isInstallable.value = true
    }

    // Escuchar evento beforeinstallprompt (solo Chrome/Edge)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    console.log('🔧 usePWA: Listener de beforeinstallprompt agregado')
    console.log('⚠️ NOTA: Si el prompt ya se mostró/rechazó antes, no aparecerá hasta limpiar cache')
    
    // Escuchar cuando la app es instalada
    window.addEventListener('appinstalled', handleAppInstalled)
    
    // Verificar después de un delay para dar tiempo al navegador
    setTimeout(() => {
      console.log('🔧 usePWA: Estado después de 2s - isInstallable:', isInstallable.value, 'isInstalled:', isInstalled.value)
      if (!isInstallable.value && !isInstalled.value) {
        console.warn('⚠️ PWA no es instalable. Posibles causas:')
        console.warn('   1. El prompt ya se mostró/rechazó antes (limpiar cache)')
        console.warn('   2. La app ya está instalada')
        console.warn('   3. El navegador no soporta PWA')
        console.warn('   4. Faltan requisitos (manifest, service worker, HTTPS)')
        console.warn('   💡 Abre /clear-pwa-cache.html para limpiar el estado')
      }
    }, 2000)
  })

  // Limpiar listeners
  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.removeEventListener('appinstalled', handleAppInstalled)
  })

  return {
    isInstallable,
    isInstalled,
    promptInstall,
    checkIfInstalled
  }
}
