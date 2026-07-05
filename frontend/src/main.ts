import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { bootstrapPWAInstallCapture } from '@/utils/pwaInstallBootstrap'

bootstrapPWAInstallCapture()

// Importar el router
import router from './router/index.js'

// Performance: Importar estilos de forma asíncrona
import './assets/styles/main.scss'

// Importar componente principal
import App from './App.vue'
import i18n from './i18n'

// Crear instancia de Pinia
const pinia = createPinia()

// Crear la aplicación Vue
const app = createApp(App)

// Registrar plugins
app.use(pinia)
app.use(router)
app.use(i18n)

// Performance: Defer mount con requestAnimationFrame
requestAnimationFrame(() => {
  app.mount('#app')
  console.log('✅ ZEUS IA iniciado')
})

// Redirigir a login cuando refresh falla (401) o sesión expirada
window.addEventListener('unauthorized', async () => {
  const { useAuthStore } = await import('@/stores/auth')
  const authStore = useAuthStore()
  authStore.resetAuthState?.()
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
})

// Registrar Service Worker para PWA (solo producción)
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  let swReloading = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (swReloading) return
    swReloading = true
    console.log('✅ Service Worker actualizado — recargando')
    window.location.reload()
  })

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/service-worker.js', { updateViaCache: 'none' })
      .then((registration) => {
        console.log('✅ Service Worker registrado:', registration.scope)
        if (registration.waiting) {
          registration.waiting.postMessage({ type: 'SKIP_WAITING' })
        }
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) {
              worker.postMessage({ type: 'SKIP_WAITING' })
            }
          })
        })
      })
      .catch((error) => {
        console.warn('⚠️ Error registrando Service Worker:', error.message)
      })
  })
}
