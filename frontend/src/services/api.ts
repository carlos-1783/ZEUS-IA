/**
 * Servicio API Centralizado
 * Usa VITE_API_BASE_URL para compatibilidad LOCAL + Railway
 * Incluye refresh de token en 401: reintento automático tras refresh.
 */

import { useAuthStore } from '@/stores/auth';

// Obtener URL base del backend desde variable de entorno
// En desarrollo: usa proxy de Vite o localhost:8000
// En producción Railway: usa VITE_API_BASE_URL configurada
const getApiBaseUrl = (): string => {
  // Si hay variable de entorno, usarla
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    return envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
  }
  
  // En desarrollo, Vite proxy maneja /api -> localhost:8000
  // En producción sin variable, asumir mismo origen (backend sirve frontend)
  if (import.meta.env.DEV) {
    return ''; // Proxy de Vite maneja esto
  }
  
  // Producción sin VITE_API_BASE_URL: mismo origen
  return '';
};

const API_BASE_URL = getApiBaseUrl();

/**
 * Construir URL completa del endpoint
 */
const buildUrl = (endpoint: string): string => {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (API_BASE_URL) {
    return `${API_BASE_URL}${normalizedEndpoint}`;
  }
  return normalizedEndpoint;
};

/** Endpoints donde no se debe intentar refresh en 401 (login, refresh, etc.) */
const SKIP_REFRESH_PATHS = ['/auth/login', '/auth/refresh', '/auth/register', '/health'];

function shouldSkipRefresh(endpoint: string): boolean {
  return SKIP_REFRESH_PATHS.some((p) => endpoint.includes(p));
}

function hadAuthHeader(headers?: HeadersInit): boolean {
  if (!headers || typeof headers !== 'object') return false;
  const h = headers as Record<string, string>;
  return !!(h.Authorization ?? h.authorization);
}

type RequestOptions = RequestInit & { _retry?: boolean };

/**
 * Realizar petición HTTP. En 401 con token enviado: intenta refresh y reintenta una vez.
 */
const request = async (endpoint: string, options: RequestOptions = {}): Promise<any> => {
  const url = buildUrl(endpoint);
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = isFormData
    ? { ...(options.headers || {}) }
    : { 'Content-Type': 'application/json', ...(options.headers || {}) };

  let response: Response;
  try {
    const { _retry, ...fetchInit } = options;
    response = await fetch(url, { ...fetchInit, headers });
  } catch (err: any) {
    if (err?.name === 'TypeError' && err?.message?.includes('fetch')) {
      const apiBase = API_BASE_URL || 'mismo origen';
      const e = new Error(`No se pudo conectar con el servidor (${apiBase}). Verifica que el backend esté ejecutándose y que VITE_API_BASE_URL esté configurada correctamente.`) as any;
      e.isConnectionError = true;
      e.url = url;
      throw e;
    }
    throw err;
  }

  if (!response.ok && response.status === 401) {
    const canRetry =
      hadAuthHeader(options.headers) &&
      !shouldSkipRefresh(endpoint) &&
      !options._retry;

    if (canRetry) {
      try {
        const authStore = useAuthStore();
        const ok = await authStore.refreshAccessToken();
        if (ok) {
          const newToken = authStore.getToken?.() ?? authStore.token;
          if (newToken) {
            const newHeaders = { ...(headers as Record<string, string>), Authorization: `Bearer ${newToken}` };
            return request(endpoint, { ...options, headers: newHeaders, _retry: true });
          }
        }
      } catch (e) {
        console.warn('[api] Refresh en 401 falló:', e);
      }
    }

    const err = new Error('Unauthorized') as any;
    err.status = 401;
    err.response = response;
    throw err;
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail ?? errorData.message ?? errorMessage;
    } catch {
      /* ignore */
    }
    const error = new Error(errorMessage) as any;
    error.status = response.status;
    error.response = response;
    throw error;
  }

  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }
  return response.text();
};

async function getBlobInternal(endpoint: string, token?: string, _retry = false): Promise<Blob> {
  const url = buildUrl(endpoint);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  let response = await fetch(url, { method: 'GET', headers });

  if (!response.ok && response.status === 401 && token && !shouldSkipRefresh(endpoint) && !_retry) {
    try {
      const authStore = useAuthStore();
      const ok = await authStore.refreshAccessToken();
      if (ok) {
        const newToken = authStore.getToken?.() ?? authStore.token;
        if (newToken) return getBlobInternal(endpoint, newToken, true);
      }
    } catch (e) {
      console.warn('[api] Refresh en 401 (getBlob) falló:', e);
    }
  }

  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as any;
    error.status = response.status;
    error.response = response;
    throw error;
  }
  return response.blob();
}

/** Obtener token actual. Siempre prioriza el store (fresco) para evitar 401 por token obsoleto. */
function authToken(passed?: string | null): string | null {
  const store = useAuthStore();
  const storeToken = store.getToken?.() ?? store.token ?? null;
  return storeToken ?? passed ?? null;
}

/**
 * API Service
 */
export const api = {
  baseURL: API_BASE_URL,

  /**
   * GET request. Si no se pasa token, se usa el del auth store (evita 401 en /metrics/summary etc).
   */
  async get(endpoint: string, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'GET',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * POST request
   */
  async post(endpoint: string, data?: any, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * PUT request
   */
  async put(endpoint: string, data?: any, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * DELETE request
   */
  async delete(endpoint: string, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'DELETE',
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * PATCH request
   */
  async patch(endpoint: string, data?: any, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * POST con FormData (para upload de archivos)
   */
  async postFormData(endpoint: string, formData: FormData, token?: string | null): Promise<any> {
    const t = authToken(token);
    return request(endpoint, {
      method: 'POST',
      body: formData,
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
  },

  /**
   * GET que devuelve Blob (para descargas). Refresh en 401 y reintento único.
   */
  async getBlob(endpoint: string, token?: string | null): Promise<Blob> {
    return getBlobInternal(endpoint, authToken(token) ?? undefined);
  },
  
  /**
   * Request genérico
   */
  request,
};

export default api;
