/**
 * Servicio API Centralizado
 * Usa VITE_API_BASE_URL para compatibilidad LOCAL + Railway
 */

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
  // Si ya es URL completa, usar directamente
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  
  // Asegurar que endpoint empiece con /
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  // Si hay API_BASE_URL, concatenar
  if (API_BASE_URL) {
    return `${API_BASE_URL}${normalizedEndpoint}`;
  }
  
  // Sin API_BASE_URL: ruta relativa (funciona cuando backend sirve frontend)
  return normalizedEndpoint;
};

/**
 * Realizar petición HTTP
 */
const request = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<any> => {
  const url = buildUrl(endpoint);
  
  // Si el body es FormData, NO añadir Content-Type (el navegador lo hace automáticamente)
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = isFormData
    ? { ...(options.headers || {}) }
    : {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      };
  
  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });
    
    // Si no hay respuesta, lanzar error
    if (!response.ok) {
      // Si es 401, es problema de autenticación
      if (response.status === 401) {
        const error = new Error('Unauthorized') as any;
        error.status = 401;
        error.response = response;
        throw error;
      }
      
      // Intentar parsear error del servidor
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        // Si no se puede parsear, usar mensaje por defecto
      }
      
      const error = new Error(errorMessage) as any;
      error.status = response.status;
      error.response = response;
      throw error;
    }
    
    // Parsear respuesta JSON
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }
    
    // Si no es JSON, devolver texto
    return await response.text();
  } catch (error: any) {
    // Si es error de red (CORS, conexión, etc.)
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      const apiBase = API_BASE_URL || 'mismo origen';
      const errorMsg = new Error(`No se pudo conectar con el servidor (${apiBase}). Verifica que el backend esté ejecutándose y que VITE_API_BASE_URL esté configurada correctamente.`) as any;
      errorMsg.isConnectionError = true;
      errorMsg.url = url;
      throw errorMsg;
    }
    
    throw error;
  }
};

/**
 * API Service
 */
export const api = {
  baseURL: API_BASE_URL,
  
  /**
   * GET request
   */
  async get(endpoint: string, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * POST request
   */
  async post(endpoint: string, data?: any, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * PUT request
   */
  async put(endpoint: string, data?: any, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * DELETE request
   */
  async delete(endpoint: string, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * PATCH request
   */
  async patch(endpoint: string, data?: any, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * POST con FormData (para upload de archivos)
   */
  async postFormData(endpoint: string, formData: FormData, token?: string): Promise<any> {
    return request(endpoint, {
      method: 'POST',
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },
  
  /**
   * GET que devuelve Blob (para descargas)
   */
  async getBlob(endpoint: string, token?: string): Promise<Blob> {
    const url = buildUrl(endpoint);
    const response = await fetch(url, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as any;
      error.status = response.status;
      throw error;
    }
    
    return await response.blob();
  },
  
  /**
   * Request genérico
   */
  request,
};

export default api;
