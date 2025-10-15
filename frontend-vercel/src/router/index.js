import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Custom encoding/decoding functions for URL parameters
const encodeParam = (param) => {
  if (param === undefined || param === null) return '';
  return encodeURIComponent(String(param))
    .replace(/%2F/g, '/')  // Preserve forward slashes
    .replace(/%20/g, '+')  // Convert spaces to + for query parameters
    .replace(/_/g, '%20'); // Convert underscores back to %20 for path segments
};

const decodeParam = (param) => {
  if (param === undefined || param === null) return '';
  return decodeURIComponent(String(param).replace(/\+/g, ' '));
};

// Layouts
import AuthLayout from '../layouts/AuthLayout.vue'
import MainLayout from '../layouts/MainLayout.vue'

// Views
import Dashboard from '../views/Dashboard.vue'
import Login from '../views/auth/Login.vue'
import Register from '../views/auth/Register.vue'
import ForgotPassword from '../views/auth/ForgotPassword.vue'
import ResetPassword from '../views/auth/ResetPassword.vue'
import NotFound from '../views/errors/NotFound.vue'
import AuthTest from '../views/AuthTest.vue'
import TestRoute from '../views/TestRoute.vue'

// Routes that don't require authentication
const publicRoutes = [
  'Login',
  'Register',
  'ForgotPassword',
  'ResetPassword',
  'NotFound',
  'AuthTest',  // Temporarily public for testing
  'WebSocketTest'  // Temporarily public for testing
]

// Navigation guard to check authentication
const setupNavigationGuards = (router) => {
  router.beforeEach(async (to, from, next) => {
    const authStore = useAuthStore()
    
    // Check if the route requires authentication
    const isPublicRoute = publicRoutes.includes(to.name)
    const isAuthenticated = authStore.isAuthenticated

    // If trying to access a protected route without being authenticated
    if (!isPublicRoute && !isAuthenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }

    // If already authenticated and trying to access auth pages
    if ((to.name === 'Login' || to.name === 'Register') && isAuthenticated) {
      return next({ name: 'Dashboard' })
    }

    next()
  })
}

// Configuración del router
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  // Configuración para manejar el scroll al cambiar de ruta
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else if (to.hash) {
      return {
        el: to.hash,
        behavior: 'smooth',
      };
    } else {
      return { top: 0, behavior: 'smooth' };
    }
  },
  // Custom query string handling
  stringifyQuery(query) {
    const result = Object.keys(query)
      .sort()
      .map((key) => {
        const value = query[key];
        if (value === undefined || value === null) return '';
        return `${encodeParam(key)}=${encodeParam(String(value))}`;
      })
      .filter(Boolean)
      .join('&');
    return result ? `?${result}` : '';
  },
  parseQuery: (query) => {
    const result = {};
    query = query.replace(/^\?/, '');
    if (!query) return result;
    for (const param of query.split('&')) {
      const [key, value] = param.split('=');
      if (key) {
        result[decodeParam(key)] = value ? decodeParam(value) : '';
      }
    }
    return result;
  },
  routes: [
    // Ruta raíz - Landing Page
    {
      path: '/',
      name: 'LandingPage',
      component: () => import('../views/LandingPage.vue'),
      meta: { 
        title: 'ZEUS IA - Tu Negocio Autónomo Inteligente',
        requiresAuth: false,
        isLanding: true
      }
    },
    
    // Direct login route (redirect to auth/login)
    {
      path: '/login',
      redirect: { name: 'Login' }
    },
    
    // Auth routes
    {
      path: '/auth',
      component: AuthLayout,
      children: [
        {
          path: 'login',
          name: 'Login',
          component: Login,
          meta: { title: 'Iniciar sesión' }
        },
        {
          path: 'register',
          name: 'Register',
          component: Register,
          meta: { title: 'Crear cuenta' }
        },
        {
          path: 'forgot-password',
          name: 'ForgotPassword',
          component: ForgotPassword,
          meta: { title: 'Recuperar contraseña' }
        },
        {
          path: 'reset-password/:token',
          name: 'ResetPassword',
          component: ResetPassword,
          meta: { title: 'Restablecer contraseña' },
          props: true
        },
        {
          path: '',
          redirect: { name: 'Login' }
        }
      ]
    },
    
    // Protected routes
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: Dashboard,
          meta: { 
            title: 'Panel de control',
            icon: 'fa-tachometer-alt',
            requiresAuth: true
          }
        },
        {
          path: '',
          redirect: { name: 'Dashboard' }
        },
        // Add more protected routes here
      ]
    },
    
        // Test routes (temporarily public)
    {
      path: '/auth-test',
      name: 'AuthTest',
      component: AuthTest,
      meta: { 
        title: 'Prueba de Autenticación',
        requiresAuth: false  // Temporarily public for testing
      }
    },
    {
      path: '/websocket-test',
      name: 'WebSocketTest',
      component: () => import('@/views/WebSocketTest.vue'),
      meta: { 
        title: 'Prueba de WebSocket',
        requiresAuth: true  // Requires authentication to test WebSocket
      }
    },
    
    // 404 catch-all route
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: NotFound,
      meta: { title: 'Página no encontrada' }
    }
  ]
})

// Global navigation guard to handle parameter decoding
router.beforeEach((to, from, next) => {
  // Decode any encoded parameters
  const decodedParams = {};
  for (const [key, value] of Object.entries(to.params)) {
    if (typeof value === 'string') {
      decodedParams[key] = decodeURIComponent(value);
    } else if (Array.isArray(value)) {
      decodedParams[key] = value.map(v => typeof v === 'string' ? decodeURIComponent(v) : v);
    } else {
      decodedParams[key] = value;
    }
  }
  
  // If parameters needed decoding, replace the navigation
  if (JSON.stringify(decodedParams) !== JSON.stringify(to.params)) {
    return next({
      ...to,
      params: decodedParams,
      // Preserve the hash and query
      hash: to.hash,
      query: to.query
    });
  }
  
  // Continue with the regular authentication check
  const authStore = useAuthStore()
  const isAuthenticated = authStore.isAuthenticated
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  // Set page title
  document.title = to.meta.title 
    ? `${to.meta.title} | ${import.meta.env.VITE_APP_NAME || 'ZEUS-IA'}`
    : import.meta.env.VITE_APP_NAME || 'ZEUS-IA'
  
  // Redirect to login if route requires authentication and user is not authenticated
  if (requiresAuth && !isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } 
  // Redirect to dashboard if user is authenticated and trying to access auth pages
  else if (isAuthenticated && publicRoutes.includes(to.name)) {
    next({ name: 'Dashboard' })
  } 
  // Proceed to the route
  else {
    next()
  }
})

// Handle navigation errors
router.onError((error) => {
  console.error('Router error:', error)
  // You can add more sophisticated error handling here
})

export default router
