// Environment configuration
export const config = {
  // WebSocket configuration
  ws: {
    url: import.meta.env.VITE_WS_URL || 
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`,
    reconnectInterval: 3000, // 3 seconds
    maxReconnectAttempts: 5,
  },
  
  // API configuration
  api: {
    baseUrl: import.meta.env.VITE_API_URL || '/api/v1',
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
