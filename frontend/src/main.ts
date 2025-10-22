import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { library } from '@fortawesome/fontawesome-svg-core'
import { fas } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

// Importar el router
import router from './router/index.js'

// Importar estilos
import './assets/styles/main.scss'

// Importar componente principal
import App from './App.vue'

// Configurar FontAwesome
library.add(fas)

// Crear instancia de Pinia
const pinia = createPinia()

// Crear la aplicación Vue
const app = createApp(App)

// Registrar plugins
app.use(pinia)
app.use(router)

// Registrar componentes globales
app.component('font-awesome-icon', FontAwesomeIcon)

// Montar la aplicación
app.mount('#app')

console.log('✅ ZEUS IA Frontend iniciado correctamente')

