console.log('🚀 Iniciando ZEUS-IA frontend...');

// Importa primero los estilos
import './style.css';
import './assets/styles/main.scss';

// Luego las dependencias de Vue
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { useAuthStore } from './stores/auth';

// Importar FontAwesome
import { library } from '@fortawesome/fontawesome-svg-core';
import { fas } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';

// Configurar FontAwesome
library.add(fas);

// Función para inicializar la aplicación
async function initApp() {
  try {
    console.log('🚀 Inicializando aplicación...');
    
    // Crear la aplicación
    const app = createApp(App);
    
    // Configurar Pinia
    const pinia = createPinia();
    app.use(pinia);
    
    // Configurar el router
    app.use(router);
    
    // Registrar componentes globales
    app.component('font-awesome-icon', FontAwesomeIcon);
    
    // Inicializar el store de autenticación antes de montar la aplicación
    console.log('🔄 Inicializando store de autenticación...');
    const authStore = useAuthStore();
    await authStore.initialize();
    
    // Montar la aplicación
    console.log('⚡ Montando aplicación...');
    app.mount('#app');
    
    console.log('✅ Aplicación inicializada correctamente');
    
    return app;
  } catch (error) {
    console.error('❌ Error crítico al inicializar la aplicación:', error);
    
    // Mostrar un mensaje de error en la interfaz
    const errorContainer = document.createElement('div');
    errorContainer.style.position = 'fixed';
    errorContainer.style.top = '0';
    errorContainer.style.left = '0';
    errorContainer.style.right = '0';
    errorContainer.style.padding = '1rem';
    errorContainer.style.backgroundColor = '#fef2f2';
    errorContainer.style.color = '#dc2626';
    errorContainer.style.borderBottom = '1px solid #fecaca';
    errorContainer.style.zIndex = '9999';
    errorContainer.textContent = 'Error al cargar la aplicación. Por favor, recarga la página.';
    document.body.prepend(errorContainer);
    
    throw error;
  }
}

// Inicializar la aplicación cuando el DOM esté listo
if (document.readyState === 'loading') {
  // El documento aún está cargando, esperar al evento DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM cargado, inicializando aplicación...');
    initApp().catch(console.error);
  });
} else {
  // El documento ya está listo, inicializar la aplicación
  console.log('⚡ DOM ya está listo, inicializando aplicación...');
  initApp().catch(console.error);
}

// Manejar errores globales no capturados
window.addEventListener('error', (event) => {
  // Filtrar errores de extensiones de Chrome
  if (event.message && event.message.includes('runtime.lastError')) {
    console.warn('⚠️ Error de extensión de Chrome ignorado:', event.message);
    return;
  }
  
  // Filtrar errores de conexión de extensiones
  if (event.message && event.message.includes('Could not establish connection')) {
    console.warn('⚠️ Error de conexión de extensión ignorado:', event.message);
    return;
  }
  
  console.error('⚠️ Error no capturado:', event.error || event);
  
  // Opcional: Mostrar notificación al usuario
  if (event instanceof Error) {
    console.error('Mensaje de error:', event.message);
    console.error('Stack trace:', event.stack);
  }
});

// Manejar promesas rechazadas no manejadas
window.addEventListener('unhandledrejection', (event) => {
  // Filtrar errores de extensiones de Chrome
  if (event.reason && typeof event.reason === 'string' && event.reason.includes('runtime.lastError')) {
    console.warn('⚠️ Promesa rechazada de extensión ignorada:', event.reason);
    return;
  }
  
  if (event.reason && event.reason.message && event.reason.message.includes('Could not establish connection')) {
    console.warn('⚠️ Promesa rechazada de conexión de extensión ignorada:', event.reason.message);
    return;
  }
  
  console.error('⚠️ Promesa rechazada no manejada:', event.reason);
  
  // Opcional: Mostrar notificación al usuario
  if (event.reason instanceof Error) {
    console.error('Razón del rechazo:', event.reason.message);
    console.error('Stack trace:', event.reason.stack);
  }
});

// La aplicación se inicializa automáticamente arriba