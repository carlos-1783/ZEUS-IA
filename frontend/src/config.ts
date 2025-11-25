import { API_BASE_URL, WS_BASE_URL, PERSEO_IMAGES_ENABLED } from './config/index';

export const config = {
  // WebSocket configuration
  ws: {
    url: WS_BASE_URL,
    reconnectInterval: 3000, // 3 seconds
    maxReconnectAttempts: 5,
  },
  
  // API configuration
  api: {
    baseUrl: API_BASE_URL,
    timeout: 30000, // 30 seconds
  },
  
  // Application settings
  app: {
    name: 'ZEUS-IA',
    version: import.meta.env.VITE_APP_VERSION || '1.0.0',
    environment: import.meta.env.MODE || 'development',
  },
  
  // Feature flags
  features: {
    enableWebSocket: true,
    enableAnalytics: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
    perseoImagesEnabled: PERSEO_IMAGES_ENABLED,
  },
};


// Export default config for backward compatibility
export default config;

export { API_BASE_URL, WS_BASE_URL, PERSEO_IMAGES_ENABLED, getWebSocketUrl } from './config/index';
