console.log('🚀 Iniciando ZEUS-IA frontend SIMPLIFICADO...');

// Importar solo lo esencial
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';

// Función para inicializar la aplicación
async function initApp() {
  try {
    console.log('🚀 Inicializando aplicación SIMPLIFICADA...');
    
    // Crear la aplicación
    const app = createApp(App);
    
    // Configurar Pinia
    const pinia = createPinia();
    app.use(pinia);
    
    // Configurar el router
    app.use(router);
    
    // Montar la aplicación
    console.log('⚡ Montando aplicación SIMPLIFICADA...');
    app.mount('#app');
    
    console.log('✅ Aplicación SIMPLIFICADA inicializada correctamente');
    
    return app;
  } catch (error) {
    console.error('❌ Error crítico al inicializar la aplicación SIMPLIFICADA:', error);
    
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
  document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM cargado, inicializando aplicación SIMPLIFICADA...');
    initApp().catch(console.error);
  });
} else {
  console.log('⚡ DOM ya está listo, inicializando aplicación SIMPLIFICADA...');
  initApp().catch(console.error);
}
