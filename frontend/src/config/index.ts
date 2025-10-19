// API configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// WebSocket configuration
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

// App configuration
export const APP_NAME = 'ZEUS-IA';
export const APP_VERSION = '1.0.0';

// Auth configuration
export const TOKEN_KEY = 'auth_token';
export const REFRESH_TOKEN_KEY = 'refresh_token';
export const TOKEN_PREFIX = 'Bearer ';

// Default timeout for API requests (in milliseconds)
export const DEFAULT_TIMEOUT = 30000;

// Default number of items per page for pagination
export const ITEMS_PER_PAGE = 10;

/**
 * Helper function to get WebSocket URL with path
 * @param path Optional path to append to the WebSocket URL
 * @returns Complete WebSocket URL
 */
export const getWebSocketUrl = (path = ''): string => {
  const baseUrl = WS_BASE_URL.replace(/\/+$/, ''); // Remove trailing slashes
  const normalizedPath = path.replace(/^\/+/, ''); // Remove leading slashes
  return normalizedPath ? `${baseUrl}/${normalizedPath}` : baseUrl;
};

// Default cache time for API responses (in milliseconds)
export const CACHE_TIME = 5 * 60 * 1000; // 5 minutes

// Default retry configuration for failed requests
export const RETRY_CONFIG = {
  maxRetries: 3,
  retryDelay: 1000, // 1 second
  retryOn: [408, 429, 500, 502, 503, 504],
};

// Connection configuration
export const CONNECTION_CONFIG = {
  wsTimeout: 15000, // 15 seconds for WebSocket connection
  maxReconnectAttempts: 3,
  reconnectDelay: 2000, // 2 seconds initial delay
  maxReconnectDelay: 10000, // 10 seconds maximum delay
};
