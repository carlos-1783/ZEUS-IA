const isDev = import.meta.env.DEV;
const env = import.meta.env as Record<string, string | undefined>;
const DEFAULT_PROD_ORIGIN = 'https://zeus-ia-production-16d8.up.railway.app';
const DEFAULT_PROD_API = `${DEFAULT_PROD_ORIGIN}/api/v1`;
const DEFAULT_PROD_WS = `wss://${DEFAULT_PROD_ORIGIN.replace(/^https?:\/\//, '')}/api/v1/ws`;
const LOCAL_API = 'http://localhost:8000/api/v1';
const LOCAL_WS = 'ws://localhost:8000/api/v1/ws';

type RuntimeWindow = Window &
  typeof globalThis & {
    __ZEUS_API_BASE?: string;
    __ZEUS_WS_BASE?: string;
    __ZEUS_API_ORIGIN?: string;
  };

const isBrowser = typeof window !== 'undefined';
const runtimeWindow = isBrowser ? (window as RuntimeWindow) : undefined;
export const PERSEO_IMAGES_ENABLED =
  (env.VITE_PERSEO_IMAGES_ENABLED ?? 'true').toLowerCase() !== 'false';

const normalize = (value: string): string => value.trim().replace(/\/+$/, '');

const isLocalOrigin = (origin?: string): boolean => {
  if (!origin) return false;
  return origin.includes('localhost') || origin.includes('127.0.0.1');
};

const getEnvValue = (...keys: string[]): string | undefined => {
  for (const key of keys) {
    const value = env[key];
    if (value && value.trim().length > 0) {
      return value.trim();
    }
  }
  return undefined;
};

const appendApiPath = (origin: string): string => {
  const base = normalize(origin);
  if (/\/api\/v\d$/i.test(base)) {
    return base;
  }
  const suffix = base.endsWith('/api') ? '/v1' : '/api/v1';
  return `${base}${suffix}`;
};

const deriveWsFromHttp = (url: string): string => {
  const normalized = normalize(url);
  const protocol = normalized.startsWith('https') ? 'wss' : 'ws';
  if (/\/api\/v\d+$/i.test(normalized)) {
    return normalized.replace(/^https?/, protocol) + '/ws';
  }
  return `${normalized.replace(/^https?/, protocol)}/api/v1/ws`;
};

const detectRuntimeApiBase = (): string => {
  const envOverride = getEnvValue('VITE_RUNTIME_API_BASE', 'VITE_API_BASE_URL', 'VITE_API_URL');
  if (envOverride) {
    return normalize(envOverride);
  }

  if (runtimeWindow?.__ZEUS_API_BASE) {
    return normalize(runtimeWindow.__ZEUS_API_BASE);
  }

  if (runtimeWindow?.__ZEUS_API_ORIGIN) {
    return appendApiPath(runtimeWindow.__ZEUS_API_ORIGIN);
  }

  if (isBrowser) {
    const origin = window.location.origin;
    if (origin && !isLocalOrigin(origin)) {
      return appendApiPath(origin);
    }
  }

  return isDev ? LOCAL_API : DEFAULT_PROD_API;
};

const detectRuntimeWsBase = (apiBase: string): string => {
  const envOverride = getEnvValue('VITE_RUNTIME_WS_BASE', 'VITE_WS_BASE_URL', 'VITE_WS_URL');
  if (envOverride) {
    return normalize(envOverride);
  }

  if (runtimeWindow?.__ZEUS_WS_BASE) {
    return normalize(runtimeWindow.__ZEUS_WS_BASE);
  }

  if (isBrowser) {
    const origin = window.location.origin;
    if (origin && !isLocalOrigin(origin)) {
      const protocol = origin.startsWith('https') ? 'wss' : 'ws';
      const base = origin.replace(/^https?/, protocol).replace(/\/+$/, '');
      return `${base}/api/v1/ws`;
    }
  }

  if (apiBase.startsWith('http')) {
    return deriveWsFromHttp(apiBase);
  }

  return isDev ? LOCAL_WS : DEFAULT_PROD_WS;
};

// API configuration
export const API_BASE_URL = detectRuntimeApiBase();

// WebSocket configuration
export const WS_BASE_URL = detectRuntimeWsBase(API_BASE_URL);

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
  const baseUrl = WS_BASE_URL.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');
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
