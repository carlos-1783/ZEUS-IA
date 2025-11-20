import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
  isAxiosError
} from 'axios';
import { decodeToken } from '../utils/tokenService';
import { API_BASE_URL } from '@/config';
import type {
  ApiResponse,
  AuthTokens,
  UserProfile,
  SystemStatus,
  RetryConfig,
  ApiErrorResponse,
  ApiClient,
  TokenService,
  TokenPayload
} from './types';

// Constants
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const REFRESH_TIMEOUT_KEY = 'refresh_timeout';
const TOKEN_PREFIX = 'Bearer ';

// Using Window interface from types.ts

// ====================
// Token Service Implementation
// ====================

const tokenService: TokenService = {
  setToken: (token: string | null): void => {
    if (token) {
      try {
        localStorage.setItem(TOKEN_KEY, token);
        axiosInstance.defaults.headers.common['Authorization'] = `${TOKEN_PREFIX}${token}`;
      } catch (error) {
        console.error('[Auth] Error saving access token:', error);
      }
    } else {
      localStorage.removeItem(TOKEN_KEY);
      delete axiosInstance.defaults.headers.common['Authorization'];
    }
  },

  getToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setRefreshToken: (token: string | null): void => {
    if (token) {
      try {
        localStorage.setItem(REFRESH_TOKEN_KEY, token);
      } catch (error) {
        console.error('[Auth] Error saving refresh token:', error);
      }
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  },

  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  removeTokens: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TIMEOUT_KEY);
    delete axiosInstance.defaults.headers.common['Authorization'];

    if (window.tokenRefreshTimeout) {
      clearTimeout(window.tokenRefreshTimeout);
      delete window.tokenRefreshTimeout;
    }
  },

  removeToken: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    delete axiosInstance.defaults.headers.common['Authorization'];
  },

  isTokenExpired: (token: string | null): boolean => {
    if (!token) return true;

    try {
      const decoded = decodeToken(token) as { exp?: number; };
      if (!decoded?.exp) return true;

      const currentTime = Date.now() / 1000;
      return decoded.exp < currentTime;
    } catch (error) {
      console.error('[Auth] Error decoding token:', error);
      return true;
    }
  },

  isValidToken: (token: string | null): boolean => {
    if (!token) return false;
    const tokenParts = token.split('.');
    return tokenParts.length === 3 && !tokenService.isTokenExpired(token);
  },

  clearTokens: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TIMEOUT_KEY);
    delete axiosInstance.defaults.headers.common['Authorization'];

    if (window.tokenRefreshTimeout) {
      clearTimeout(window.tokenRefreshTimeout as any);
      delete window.tokenRefreshTimeout;
    }
  },

  getTokenPayload: (token: string | null): TokenPayload | null => {
    if (!token) return null;

    try {
      const tokenParts = token.split('.');
      if (tokenParts.length !== 3) return null;

      const base64Url = tokenParts[1].replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64Url)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );

      return JSON.parse(jsonPayload) as TokenPayload;
    } catch (error) {
      console.error('[Auth] Error decoding token payload:', error);
      return null;
    }
  },
  refreshToken: function (): Promise<{ access_token: string; refresh_token: string; }> {
    throw new Error('Function not implemented.');
  }
};

// ====================
// Axios Instance Configuration
// ====================

const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
  withCredentials: true, // Important for cookies, authorization headers with HTTPS
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Request interceptor to add auth token and handle CORS
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenService.getToken();
    
    // Add auth header if token exists
    if (token) {
      config.headers.Authorization = `${TOKEN_PREFIX}${token}`;
    }
    
    // Add CORS headers for all requests
    config.headers['Access-Control-Allow-Origin'] = window.location.origin;
    config.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS';
    config.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With';
    
    // For preflight requests
    if (config.method?.toLowerCase() === 'options') {
      config.headers['Access-Control-Max-Age'] = '86400';
    }
    
    return config;
  },
  (error) => {
    console.error('[API] Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Request interceptor to add auth token to requests
axiosInstance.interceptors.request.use(
  (config) => {
    // Skip adding auth header for login/refresh token endpoints
    const isAuthRequest = config.url?.includes('auth/login') || 
                         config.url?.includes('auth/refresh');
    
    // Get token from storage
    const token = tokenService.getToken();
    
    // If token exists and it's not an auth request, add it to headers
    if (token && !isAuthRequest) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Log the request
    console.log(`[API] Sending ${config.method?.toUpperCase()} to ${config.url}`, {
      baseURL: config.baseURL,
      headers: config.headers,
      params: config.params,
      data: config.data ? JSON.parse(JSON.stringify(config.data)) : undefined
    });
    
    // Add cache busting for GET requests
    if (config.method?.toLowerCase() === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now()
      };
    }
    
    return config;
  },
  (error) => {
    console.error('[API] Request error:', error);
    return Promise.reject(error);
  }
);

// Helper function to handle token refresh
const handleTokenRefresh = async (): Promise<boolean> => {
  const refreshToken = tokenService.getRefreshToken();
  if (!refreshToken) {
    tokenService.clearTokens();
    return false;
  }

  try {
    const response = await axiosInstance.post(
      'auth/refresh',
      { refresh_token: refreshToken },
      { skipAuthRefresh: true } as any
    );

    const payload: any = response.data;
    const tokens: AuthTokens | undefined = payload?.access_token
      ? payload
      : payload?.status === 'success'
        ? payload.data
        : undefined;

    if (tokens?.access_token) {
      tokenService.setToken(tokens.access_token);
      if (tokens.refresh_token) {
        tokenService.setRefreshToken(tokens.refresh_token);
      }
      if (tokens.expires_in) {
        scheduleTokenRefresh(tokens.expires_in);
      }
      return true;
    }
    return false;
  } catch (error) {
    console.error('Token refresh failed:', error);
    tokenService.clearTokens();
    return false;
  }
};

// Response interceptor to handle 401 errors and token refresh
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle network errors
    if (!error.response) {
      console.error('[API] Network error:', error.message);
      return Promise.reject(createErrorResponse('network_error', 'Error de red', error));
    }
    
    // If error is not 401 or it's a retry request, reject
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    
    // Mark request as retried
    originalRequest._retry = true;

    // Try to refresh token
    const refreshSuccess = await handleTokenRefresh();
    
    if (refreshSuccess) {
      // Update the authorization header
      const token = tokenService.getToken();
      if (token) {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return axiosInstance(originalRequest);
      }
    }
    
    // If we get here, refresh failed or no token
    return Promise.reject(error);
  }
);

// ====================
// Token Refresh Logic
// ====================

const scheduleTokenRefresh = (expiresIn: number): void => {
  // Clear any existing timeout
  if (window.tokenRefreshTimeout !== undefined) {
    // Use type assertion to handle both browser and Node.js types
    const timeoutId = window.tokenRefreshTimeout as any;
    clearTimeout(timeoutId);
    window.tokenRefreshTimeout = undefined;
  }

  // Calculate refresh time (5 minutes before expiration, minimum 60 seconds)
  const refreshTime = Math.max(expiresIn - 300, 60) * 1000; // Convert to milliseconds
  
  console.log(`[Auth] Scheduling token refresh in ${refreshTime / 1000} seconds`);
  
  // Set the timeout for token refresh - use type assertion to handle browser vs Node.js types
  window.tokenRefreshTimeout = window.setTimeout(async () => {
    try {
      const refreshToken = tokenService.getRefreshToken();
      if (refreshToken) {
        console.log('[Auth] Starting automatic token refresh...');
        await api.refreshToken(refreshToken);
        console.log('[Auth] Token refreshed successfully (automatic)');
      } else {
        console.warn('[Auth] No refresh token available for automatic refresh');
        tokenService.removeTokens();
      }
    } catch (error) {
      console.error('[Auth] Error during automatic token refresh:', error);
      tokenService.removeTokens();
      window.dispatchEvent(new Event('unauthorized'));
    }
  }, refreshTime);
};

const refreshToken = async (refreshTokenValue: string): Promise<AuthTokens> => {
  if (!refreshTokenValue) {
    throw new Error('No refresh token provided');
  }

  try {
    const response = await axiosInstance.post(
      'auth/refresh',
      { refresh_token: refreshTokenValue },
      { skipAuthRefresh: true } as any
    );

    const payload: any = response.data;
    const tokens: AuthTokens | undefined = payload?.access_token
      ? payload
      : payload?.status === 'success'
        ? payload.data
        : undefined;

    if (tokens?.access_token) {
      tokenService.setToken(tokens.access_token);
      if (tokens.refresh_token) {
        tokenService.setRefreshToken(tokens.refresh_token);
      }

      if (tokens.expires_in) {
        const refreshTime = Math.max(tokens.expires_in - 300, 60);
        scheduleTokenRefresh(refreshTime);
      }

      return tokens;
    }

    throw new Error(payload?.error || 'Failed to refresh token');
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 401) {
      tokenService.removeTokens();
      window.dispatchEvent(new Event('unauthorized'));
    }
    throw error;
  }
};

// ====================
// Request/Response Interceptors
// ====================

// Request interceptor
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    // Skip token handling for auth endpoints
    if (config.url?.includes('auth/')) {
      return config;
    }

    // Add auth token if available
    const token = tokenService.getToken();
    if (token) {
      config.headers.Authorization = `${TOKEN_PREFIX}${token}`;
    }
    
    // Add cache busting for GET requests
    if (config.method?.toLowerCase() === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now()
      };
    }
    
    return config;
  },
  (error: AxiosError) => {
    console.error('[API] Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log successful responses (except auth endpoints)
    if (!response.config.url?.includes('auth/')) {
      console.log(`[API] ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status}`);
    }
    return response;
  },
  async (error: AxiosError<ApiErrorResponse>) => {
    const originalRequest = error.config as RetryConfig;
    
    // Handle network errors
    if (!error.response) {
      console.error('[API] Network error:', error.message);
      return Promise.reject(createErrorResponse('network_error', 'Network error', error));
    }
    
    const { status, data } = error.response;
    
    // Log error details
    console.error(`[API] Error ${status}:`, {
      url: originalRequest.url,
      method: originalRequest.method,
      status,
      error: data?.error || 'Unknown error',
      message: data?.message || error.message,
      details: data?.detail || data
    });
    
    // Handle 401 Unauthorized (token expired or invalid)
    if (status === 401 && !originalRequest._retry) {
      // If this is a login/refresh request, just reject with the error
      if (originalRequest.url?.includes('auth/login') || 
          originalRequest.url?.includes('auth/refresh')) {
        return Promise.reject(createErrorResponse('auth_error', 'Invalid credentials', error, data));
      }
      
      // Mark request as retried to prevent infinite loops
      originalRequest._retry = true;
      
      try {
        // Try to refresh the token
        const refreshTokenValue = tokenService.getRefreshToken();
        if (!refreshTokenValue) {
          console.error('[API] No refresh token available');
          tokenService.removeTokens();
          window.dispatchEvent(new Event('unauthorized'));
          return Promise.reject(createErrorResponse('no_refresh_token', 'Session expired', error));
        }
        
        console.log('[API] Attempting to refresh token...');
        try {
          const newTokens = await refreshToken(refreshTokenValue);
          
          // Update the auth header with the new token
          if (newTokens.access_token) {
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `${TOKEN_PREFIX}${newTokens.access_token}`;
            return axiosInstance(originalRequest);
          }
        } catch (refreshError) {
          console.error('[API] Token refresh failed:', refreshError);
          tokenService.removeTokens();
          window.dispatchEvent(new Event('unauthorized'));
          return Promise.reject(createErrorResponse('token_refresh_failed', 'Session refresh failed', refreshError));
        }
      } catch (refreshError) {
        console.error('[API] Token refresh failed:', refreshError);
        tokenService.removeTokens();
        window.dispatchEvent(new Event('unauthorized'));
        return Promise.reject(createErrorResponse('token_refresh_failed', 'Session refresh failed', refreshError));
      }
    }
    
    // Handle other error statuses
    switch (status) {
      case 400:
        return Promise.reject(createErrorResponse('bad_request', 'Bad request', error, data));
      case 403:
        tokenService.removeTokens();
        window.dispatchEvent(new Event('unauthorized'));
        return Promise.reject(createErrorResponse('forbidden', 'Forbidden', error, data));
      case 404:
        return Promise.reject(createErrorResponse('not_found', 'Resource not found', error, data));
      case 422:
        return Promise.reject(createErrorResponse('validation_error', 'Validation error', error, data));
      case 429:
        return Promise.reject(createErrorResponse('too_many_requests', 'Too many requests', error, data));
      case 500:
        return Promise.reject(createErrorResponse('server_error', 'Internal server error', error, data));
      case 503:
        return Promise.reject(createErrorResponse('service_unavailable', 'Service unavailable', error, data));
      default:
        return Promise.reject(createErrorResponse('api_error', 'API request failed', error, data));
    }
  }
);

// ====================
// API Client Implementation
// ====================

const api: ApiClient = {
  // Auth methods
  login: async (credentials: { username: string; password: string }): Promise<AuthTokens> => {
    // Crear FormData para el login
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    formData.append('grant_type', 'password');

    const response = await axiosInstance.post('auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    // El backend devuelve directamente el token, no en un wrapper de ApiResponse
    if (response.data && response.data.access_token) {
      const { access_token, refresh_token, expires_in } = response.data;
      
      // Save tokens
      tokenService.setToken(access_token);
      if (refresh_token) {
        tokenService.setRefreshToken(refresh_token);
      }
      
      // Schedule token refresh
      if (expires_in) {
        const refreshTime = Math.max(expires_in - 300, 60);
        scheduleTokenRefresh(refreshTime);
      }
      
      return response.data;
    }
    
    throw new Error(response.data?.detail || 'Login failed');
  },
  
  logout: async (): Promise<void> => {
    try {
      // Try to revoke the refresh token
      const refreshToken = tokenService.getRefreshToken();
      if (refreshToken) {
        await axiosInstance.post('auth/logout', { refresh_token: refreshToken });
      }
    } catch (error) {
      console.error('Error during logout:', error);
    } finally {
      // Clear tokens and redirect to login
      tokenService.removeTokens();
      window.location.href = '/login';
    }
  },
  
  refreshToken,
  
  // User methods
  getCurrentUser: async (): Promise<UserProfile> => {
    const response = await axiosInstance.get('auth/me');
    
    // El backend devuelve directamente los datos del usuario, no en un wrapper de ApiResponse
    if (response.data && response.data.data) {
      return response.data.data;
    }
    
    throw new Error(response.data?.detail || 'Failed to fetch user profile');
  },
  
  // System status
  getSystemStatus: async (): Promise<SystemStatus> => {
    const response = await axiosInstance.get<ApiResponse<SystemStatus>>('/system/status');
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data;
    }
    
    throw new Error(response.data.error || 'Failed to fetch system status');
  },
  
  // Generic API call
  request: async <T = any>(config: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.request<ApiResponse<T>>(config);
    
    if (response.data.status === 'success') {
      return response.data.data as T;
    }
    
    throw new Error(response.data.error || 'API request failed');
  }
};

// ====================
// Helper Functions
// ====================

function createErrorResponse(
  code: string,
  message: string,
  originalError?: any,
  details?: any
): Error {
  const error = new Error(message) as any;
  error.code = code;
  error.originalError = originalError;
  error.details = details;
  
  // Add additional Axios error details if available
  if (isAxiosError(originalError)) {
    error.status = originalError.response?.status;
    error.statusText = originalError.response?.statusText;
  }
  
  return error;
}

// ====================
// Exports
// ====================

export { tokenService, createErrorResponse };
export default api;

// Re-export types for convenience
export type {
  ApiResponse,
  AuthTokens,
  UserProfile,
  SystemStatus,
  ApiErrorResponse,
  RetryConfig
} from './types';
