// Environment configuration
const isDev = import.meta.env.DEV;
const PROD_API_BASE = 'https://zeus-ia-production-16d8.up.railway.app/api/v1';
const PROD_WS_URL = 'wss://zeus-ia-production-16d8.up.railway.app/ws';

const fallbackApiBase = import.meta.env.VITE_API_URL || (isDev ? 'http://localhost:8000/api/v1' : PROD_API_BASE);
const fallbackWsUrl = import.meta.env.VITE_WS_URL || (isDev ? 'ws://localhost:8000/api/v1/ws' : PROD_WS_URL);

export const config = {
  // WebSocket configuration
  ws: {
    url: fallbackWsUrl,
    reconnectInterval: 3000, // 3 seconds
    maxReconnectAttempts: 5,
  },
  
  // API configuration
  api: {
    baseUrl: fallbackApiBase,
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
  },
};


// Export default config for backward compatibility
export default config;
