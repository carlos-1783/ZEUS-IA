console.log('🚀 Iniciando ZEUS-IA frontend ULTRA-MINIMAL...');

// Importar SOLO lo absolutamente esencial
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';

// Router ULTRA-SIMPLE sin auth store
import { createRouter, createWebHistory } from 'vue-router';

// Layouts
import AuthLayout from './layouts/AuthLayout.vue';
import MainLayout from './layouts/MainLayout.vue';

// Views
import Login from './views/auth/Login.vue';
import Dashboard from './views/Dashboard.vue';
import NotFound from './views/errors/NotFound.vue';

// DEBUG: Verificar que los componentes se importan correctamente
console.log('🔍 Login component imported:', Login);
console.log('🔍 AuthLayout component imported:', AuthLayout);
console.log('🔍 MainLayout component imported:', MainLayout);

// Router ULTRA-SIMPLE - CORREGIDO
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/auth/login'
    },
    {
      path: '/auth/login',
      component: Login,
      name: 'Login'
    },
    {
      path: '/dashboard',
      component: MainLayout,
      children: [
        {
          path: '',
          component: Dashboard,
          name: 'Dashboard'
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: NotFound
    }
  ]
});

// DEBUG: Verificar rutas
console.log('🔍 Router configurado con rutas:', router.getRoutes().map(r => ({ path: r.path, name: r.name })));

// Función para inicializar la aplicación ULTRA-MINIMAL
async function initApp() {
  try {
    console.log('🚀 Inicializando aplicación ULTRA-MINIMAL...');
    
    // Crear la aplicación
    const app = createApp(App);
    
    // Configurar Pinia (sin auth store)
    const pinia = createPinia();
    app.use(pinia);
    
    // Configurar el router
    app.use(router);
    
    // Montar la aplicación
    console.log('⚡ Montando aplicación ULTRA-MINIMAL...');
    app.mount('#app');
    
    // NO FORZAR NAVEGACIÓN - DEJAR QUE EL ROUTER MANEJE LA NAVEGACIÓN
    console.log('🔄 Permitiendo que el router maneje la navegación naturalmente...');
    
    // DEBUG: Verificar ruta actual después del mount
    console.log('🔍 Ruta actual después del mount:', router.currentRoute.value.path);
    console.log('🔍 Nombre de ruta actual:', router.currentRoute.value.name);
    
    console.log('✅ Aplicación ULTRA-MINIMAL inicializada correctamente');
    
    return app;
  } catch (error) {
    console.error('❌ Error crítico al inicializar la aplicación ULTRA-MINIMAL:', error);
    
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
    console.log('📄 DOM cargado, inicializando aplicación ULTRA-MINIMAL...');
    initApp().catch(console.error);
  });
} else {
  console.log('⚡ DOM ya está listo, inicializando aplicación ULTRA-MINIMAL...');
  initApp().catch(console.error);
}

console.log('✅ Script ULTRA-MINIMAL cargado correctamente');
