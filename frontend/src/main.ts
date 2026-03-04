import { createApp } from 'vue'
import { createPinia } from 'pinia'

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

// Registrar Service Worker para PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const isProd = import.meta.env.PROD
    console.log('🔧 Service Worker: Intentando registrar... (PROD:', isProd, ')')
    
    navigator.serviceWorker.register('/service-worker.js')
      .then((registration) => {
        console.log('✅ Service Worker registrado:', registration.scope)
        console.log('✅ Service Worker activo:', registration.active)
        console.log('✅ Service Worker esperando:', registration.waiting)
      })
      .catch((error) => {
        console.warn('⚠️ Error registrando Service Worker:', error)
        console.warn('⚠️ Detalles:', error.message)
      })
  })
} else {
  console.warn('⚠️ Service Workers no están soportados en este navegador')
}
