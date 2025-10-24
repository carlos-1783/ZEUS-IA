/**
 * Performance Optimizer Utility
 * Centraliza la gestión de eventos de performance para evitar handlers pesados
 */

// Performance: Flag global para prevenir múltiples inicializaciones
let isAppInitialized = false;
let visibilityChangeHandlers: (() => void)[] = [];
let lastVisibilityChange = 0;
const MIN_VISIBILITY_INTERVAL = 1000; // Mínimo 1 segundo entre cambios

/**
 * Registrar handler de visibilitychange con debouncing automático
 */
export function onVisibilityChange(handler: () => void): () => void {
  visibilityChangeHandlers.push(handler);
  
  // Retornar función para remover el handler
  return () => {
    const index = visibilityChangeHandlers.indexOf(handler);
    if (index > -1) {
      visibilityChangeHandlers.splice(index, 1);
    }
  };
}

/**
 * Ejecutar handlers de visibilitychange con throttling
 */
function handleVisibilityChange() {
  const now = Date.now();
  
  // Performance: Throttle - mínimo 1 segundo entre cambios
  if (now - lastVisibilityChange < MIN_VISIBILITY_INTERVAL) {
    console.log('⏩ Visibility change throttled');
    return;
  }
  
  lastVisibilityChange = now;
  
  // Performance: Solo ejecutar si la página es visible
  if (document.visibilityState !== 'visible') {
    return;
  }
  
  console.log('👁️ Page became visible - executing handlers');
  
  // Performance: Ejecutar handlers de forma non-blocking
  Promise.resolve().then(() => {
    visibilityChangeHandlers.forEach(handler => {
      try {
        handler();
      } catch (error) {
        console.error('Error in visibility change handler:', error);
      }
    });
  });
}

/**
 * Inicializar el sistema de optimización de performance
 */
export function initPerformanceOptimizer() {
  if (isAppInitialized) {
    console.log('⏩ Performance optimizer already initialized');
    return;
  }
  
  console.log('🚀 Initializing performance optimizer...');
  
  // Registrar listener de visibilitychange con passive: true
  document.addEventListener('visibilitychange', handleVisibilityChange, { 
    passive: true,
    capture: false
  });
  
  isAppInitialized = true;
  console.log('✅ Performance optimizer initialized');
}

/**
 * Cleanup del optimizador
 */
export function cleanupPerformanceOptimizer() {
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  visibilityChangeHandlers = [];
  isAppInitialized = false;
}

/**
 * Throttle function - limita la ejecución de una función
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  return (...args: Parameters<T>) => {
    const now = Date.now();
    const timeSinceLastCall = now - lastCall;
    
    if (timeSinceLastCall >= delay) {
      lastCall = now;
      func(...args);
    } else {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      timeoutId = setTimeout(() => {
        lastCall = Date.now();
        func(...args);
        timeoutId = null;
      }, delay - timeSinceLastCall);
    }
  };
}

/**
 * Debounce function - retrasa la ejecución hasta que dejen de llamar
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    
    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, delay);
  };
}

export default {
  initPerformanceOptimizer,
  cleanupPerformanceOptimizer,
  onVisibilityChange,
  throttle,
  debounce
};

