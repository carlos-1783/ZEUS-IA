import { ref, onMounted, onUnmounted } from 'vue'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

/**
 * Composable para manejar la instalación de la PWA
 * Detecta cuando la app puede ser instalada y proporciona métodos para mostrar el prompt
 */
export function usePWA() {
  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)

  // Detectar si la app ya está instalada
  const checkIfInstalled = () => {
    // Para móviles
    if (window.matchMedia('(display-mode: standalone)').matches) {
      isInstalled.value = true
      return true
    }
    
    // Para escritorio (Windows)
    if ((window.navigator as any).standalone === false) {
      isInstalled.value = false
    }
    
    // Detectar desde localStorage (puede no ser 100% preciso)
    if (localStorage.getItem('zeus-pwa-installed') === 'true') {
      isInstalled.value = true
      return true
    }
    
    return false
  }

  // Manejar el evento beforeinstallprompt
  const handleBeforeInstallPrompt = (e: Event) => {
    console.log('📱 PWA: Evento beforeinstallprompt recibido!')
    e.preventDefault()
    deferredPrompt.value = e as BeforeInstallPromptEvent
    isInstallable.value = true
    console.log('✅ PWA: isInstallable establecido en true')
  }

  // Manejar cuando la app es instalada
  const handleAppInstalled = () => {
    isInstalled.value = true
    isInstallable.value = false
    deferredPrompt.value = null
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
    
    // Escuchar evento beforeinstallprompt (solo Chrome/Edge)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    console.log('🔧 usePWA: Listener de beforeinstallprompt agregado')
    
    // Escuchar cuando la app es instalada
    window.addEventListener('appinstalled', handleAppInstalled)
    
    // Verificar después de un delay para dar tiempo al navegador
    setTimeout(() => {
      console.log('🔧 usePWA: Estado después de 2s - isInstallable:', isInstallable.value, 'isInstalled:', isInstalled.value)
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
