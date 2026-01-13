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

// Registrar Service Worker para PWA (solo en producción)
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then((registration) => {
        console.log('✅ Service Worker registrado:', registration.scope)
      })
      .catch((error) => {
        console.warn('⚠️ Error registrando Service Worker:', error)
      })
  })
}
