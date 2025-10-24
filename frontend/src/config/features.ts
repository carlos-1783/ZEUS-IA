/**
 * Feature Flags para optimización de performance
 * Controla qué funcionalidades están habilitadas
 */

const isProd = import.meta.env.PROD
const isDev = import.meta.env.DEV

export const featureFlags = {
  // Performance: Deshabilitar features pesadas en producción
  enable3DGraphics: isDev,  // Solo en desarrollo
  enableAudio: false,  // Deshabilitado siempre (consume recursos)
  enableWebSocket: isDev,  // Solo en desarrollo
  enableAnimations: !isProd,  // Solo en desarrollo
  enablePeriodicUpdates: false,  // Deshabilitado (causa setInterval pesado)
  
  // Features que sí funcionan en producción
  enableAuth: true,
  enableDashboard: true,
  enableRouting: true,
}

export default featureFlags

