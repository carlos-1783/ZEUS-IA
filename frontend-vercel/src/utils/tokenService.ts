import { ref } from 'vue';

const TOKEN_KEY = 'auth_token';  // Cambiado de 'access_token' a 'auth_token' para mantener consistencia
const REFRESH_TOKEN_KEY = 'refresh_token';

// JWT Payload interface
export interface JwtPayload {
  sub: string;
  email: string;
  name?: string;
  empresa_activada: boolean;
  roles: string[];
  permissions: string[];
  exp: number;
  iat: number;
  [key: string]: any;
}

// Token management
export const getToken = (): string | null => {
  try {
    console.log('[TokenService] getToken: Obteniendo token de localStorage...');
    const token = localStorage.getItem(TOKEN_KEY);
    
    console.log('[TokenService] getToken: Token crudo de localStorage:', token ? `${token.substring(0, 10)}...` : 'null/undefined');
    
    const cleanTokenValue = cleanToken(token);
    console.log('[TokenService] getToken: Token limpio:', cleanTokenValue ? `${cleanTokenValue.substring(0, 10)}...` : 'null/undefined');
    
    // Verificar si el token está expirado
    if (cleanTokenValue) {
      const isExpired = isTokenExpired(cleanTokenValue);
      console.log(`[TokenService] getToken: Token ${isExpired ? 'expirado' : 'válido'}`);
      
      if (isExpired) {
        console.log('[TokenService] getToken: Token expirado, intentando renovar...');
        // Aquí podríamos intentar renovar el token si hay un refresh token
      }
    }
    
    return cleanTokenValue;
  } catch (error) {
    console.error('[TokenService] getToken: Error accediendo a localStorage:', error);
    return null;
  }
};

export const setToken = (token: string): void => {
  console.log('[TokenService] setToken llamado con token:', token ? `${token.substring(0, 10)}...` : 'null/undefined');
  
  const cleanTokenValue = cleanToken(token);
  if (!cleanTokenValue) {
    console.error('[TokenService] Intento de guardar un token inválido');
    return;
  }
  
  try {
    console.log('[TokenService] Guardando token en localStorage...');
    localStorage.setItem(TOKEN_KEY, cleanTokenValue);
    console.log('[TokenService] Token guardado correctamente en localStorage');
    
    // Verificar que el token se guardó correctamente
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (storedToken === cleanTokenValue) {
      console.log('[TokenService] Verificación exitosa: el token se guardó correctamente');
    } else {
      console.error('[TokenService] Error: El token no se guardó correctamente en localStorage');
      console.log('[TokenService] Token esperado:', cleanTokenValue.substring(0, 10) + '...');
      console.log('[TokenService] Token guardado:', storedToken ? storedToken.substring(0, 10) + '...' : 'null');
    }
  } catch (error) {
    console.error('[TokenService] Error al guardar el token en localStorage:', error);
    // Si hay un error de cuota, limpiar espacio
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.error('[TokenService] Se ha excedido la cuota de almacenamiento');
      // Limpiar almacenamiento local
      localStorage.clear();
      console.log('[TokenService] localStorage limpiado. Intenta de nuevo.');
    }
  }
};

export const removeToken = (): void => {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (error) {
    console.error('Error removing token from localStorage:', error);
  }
};

// Refresh token management
export const getRefreshToken = (): string | null => {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch (error) {
    console.error('Error accessing refresh token:', error);
    return null;
  }
};

export const setRefreshToken = (token: string): void => {
  try {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  } catch (error) {
    console.error('Error setting refresh token:', error);
  }
};

export const removeRefreshToken = (): void => {
  try {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch (error) {
    console.error('Error removing refresh token:', error);
  }
};

// Token decoding
export const decodeToken = <T = JwtPayload>(token: string): T | null => {
  // Validación básica del token
  if (!token || typeof token !== 'string' || token.trim() === '') {
    console.error('Token no proporcionado o inválido');
    return null;
  }
  
  // Limpiar el token de espacios y prefijos
  const cleanTokenValue = cleanToken(token);
  if (!cleanTokenValue) return null;
  
  try {
    // Verificar el formato del token (debe tener 3 partes)
    const parts = cleanTokenValue.split('.');
    if (parts.length !== 3) {
      console.error(`Formato de token inválido: se esperaban 3 partes, se encontraron ${parts.length}`);
      return null;
    }
    
    // Decodificar el payload (segunda parte)
    const base64Url = parts[1];
    // Añadir padding si es necesario
    const padded = base64Url.padEnd(base64Url.length + (4 - base64Url.length % 4) % 4, '=');
    // Reemplazar caracteres especiales
    const base64 = padded.replace(/\-/g, '+').replace(/_/g, '/');
    
    try {
      // Decodificar base64
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      
      // Parsear el payload JSON
      const payload = JSON.parse(jsonPayload) as T;
      
      // Verificar que el token tenga una expiración
      if (payload && typeof payload === 'object' && 'exp' in payload) {
        const expiration = (payload as any).exp;
        if (expiration && typeof expiration === 'number') {
          console.log(`Token válido hasta: ${new Date(expiration * 1000).toISOString()}`);
        }
      }
      
      return payload;
    } catch (e) {
      console.error('Error al decodificar el payload del token:', e);
      return null;
    }
  } catch (error) {
    console.error('Error al decodificar el token:', error);
    return null;
  }
};

// Token validation
export const isTokenExpired = (token: string | null): boolean => {
  if (!token) {
    console.log('[TokenService] No se proporcionó token para validar');
    return true;
  }

  // Para desarrollo: Si el token comienza con 'test_', considerarlo siempre válido
  if (token.startsWith('test_')) {
    console.log('[TokenService] Token de prueba detectado, se considera válido');
    return false;
  }
  
  try {
    const decoded = decodeToken<JwtPayload>(token);
    if (!decoded) {
      console.log('[TokenService] No se pudo decodificar el token');
      return true;
    }
    
    // Asegurarse de que el token tenga una expiración
    if (typeof decoded.exp !== 'number') {
      console.log('[TokenService] El token no tiene fecha de expiración');
      return true;
    }
    
    const isExpired = decoded.exp * 1000 < Date.now();
    if (isExpired) {
      console.log(`[TokenService] Token expirado el: ${new Date(decoded.exp * 1000).toISOString()}`);
    } else {
      const expiresIn = Math.floor((decoded.exp * 1000 - Date.now()) / 1000);
      console.log(`[TokenService] Token válido. Expira en: ${expiresIn} segundos`);
    }
    
    return isExpired;
  } catch (error) {
    console.error('[TokenService] Error al validar el token:', error);
    // En desarrollo, consideramos el token como no expirado para permitir continuar
    if (process.env.NODE_ENV === 'development') {
      console.log('[TokenService] Modo desarrollo: Continuando con token inválido');
      return false;
    }
    return true;
  }
};

export const getTokenExpiration = (token: string | null): number | null => {
  if (!token) return null;
  try {
    const decoded = decodeToken<JwtPayload>(token);
    return decoded ? decoded.exp * 1000 : null;
  } catch (error) {
    console.error('Error getting token expiration:', error);
    return null;
  }
};

// Token refresh management
const isRefreshing = ref(false);
let refreshSubscribers: ((token: string) => void)[] = [];

export const onTokenRefreshed = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

export const clearRefreshSubscribers = () => {
  refreshSubscribers = [];
};

export const notifyRefreshSubscribers = (token: string) => {
  refreshSubscribers.forEach(callback => callback(token));
  clearRefreshSubscribers();
};

export const getIsRefreshing = (): boolean => {
  return isRefreshing.value;
};

export const setIsRefreshing = (value: boolean) => {
  isRefreshing.value = value;
};

// Token auto-refresh management
let refreshTimeout: number | null = null;

export const scheduleTokenRefresh = (expirationTime: number): void => {
  if (refreshTimeout) {
    clearTimeout(refreshTimeout);
  }

  // Refresh 1 minute before expiration
  const refreshTime = expirationTime - Date.now() - 60000;
  
  if (refreshTime > 0) {
    refreshTimeout = window.setTimeout(() => {
      // This would be handled by the API interceptor
      console.log('Token refresh needed');
    }, refreshTime);
  }
};

/**
 * Clean and validate JWT token
 * - Removes 'Bearer' prefix (case insensitive)
 * - Trims whitespace and special characters
 * - Validates basic JWT format (3 parts separated by dots)
 * - Handles encoding issues and invalid characters
 */
export const cleanToken = (token: string | null | undefined): string | null => {
  if (!token) {
    console.warn('Token is null or undefined');
    return null;
  }
  
  try {
    // Convert to string and remove any non-printable characters
    let cleaned = String(token)
      .replace(/[\u0000-\u001F\u007F-\u009F\u2000-\u200F\u2028-\u202F\u205F-\u206F\u3000\uFEFF]/g, '') // Remove control characters
      .trim();
      
    console.log('Token after initial cleaning:', cleaned);
    
    // Remove 'Bearer' prefix (case insensitive) and any non-alphanumeric characters after it
    cleaned = cleaned
      .replace(/^[^a-zA-Z0-9]*bearer[^a-zA-Z0-9]*(.*)/i, (_, token) => token || '')
      .trim();
      
    console.log('Token after Bearer removal:', cleaned);
    
    // Check if the token is empty after cleaning
    if (!cleaned) {
      console.warn('Token is empty after cleaning');
      return null;
    }
    
    // Check if it looks like a JWT (3 parts separated by dots)
    const parts = cleaned.split('.');
    console.log('Token parts:', parts.length);
    
    // A valid JWT has exactly 3 parts
    if (parts.length !== 3) {
      console.warn('Formato de token JWT inválido - se esperaban 3 partes');
      return null;
    }
    
    // Try to decode each part to ensure they're valid base64
    try {
      parts.forEach(part => {
        // Add padding if needed before decoding
        const padded = part.padEnd(part.length + (4 - (part.length % 4)) % 4, '=');
        atob(padded);
      });
    } catch (e) {
      console.warn('Token contiene partes que no son Base64 válido');
      return null;
    }
    
    return cleaned;
    
  } catch (error) {
    console.error('Error al limpiar el token:', error);
    return null;
  }
};
