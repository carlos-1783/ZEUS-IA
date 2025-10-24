import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Importar el router
import router from './router/index.js'

// Performance: Importar estilos de forma asíncrona
import './assets/styles/main.scss'

// Importar componente principal
import App from './App.vue'

// Crear instancia de Pinia
const pinia = createPinia()

// Crear la aplicación Vue
const app = createApp(App)

// Registrar plugins
app.use(pinia)
app.use(router)

// Performance: Montar inmediatamente (sin delay)
app.mount('#app')
console.log('✅ ZEUS IA Frontend iniciado')

