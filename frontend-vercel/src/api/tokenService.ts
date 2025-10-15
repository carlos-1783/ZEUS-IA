import type { TokenService, TokenPayload } from './types';
import { jwtDecode } from 'jwt-decode';

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export const tokenService: TokenService = {
  setToken: (token: string | null) => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  },

  getToken: (): string | null => {
    return localStorage.getItem(TOKEN_KEY);
  },

  setRefreshToken: (token: string | null) => {
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  },

  getRefreshToken: (): string | null => {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  removeTokens: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);  
  },

  removeToken: () => {
    localStorage.removeItem(TOKEN_KEY);
  },

  isTokenExpired: (token: string | null): boolean => {
    if (!token) return true;
    
    // Para pruebas con tokens de prueba
    if (process.env.NODE_ENV === 'development' && token.startsWith('test_')) {
      return false;
    }
    
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      if (!decoded.exp) return true;
      if (!decoded) {
        console.error('Failed to decode token');
        return true; // Consider invalid if decoding fails
      }
      const currentTime = Date.now() / 1000;
      return (decoded.exp ?? 0) < currentTime;
    } catch (error) {
      console.error('Error decoding token:', error);
      return true;
    }
  },

  isValidToken: function(token: string | null): boolean {
    if (!token) return false;
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      return !!decoded && !this.isTokenExpired(token);
    } catch (error) {
      console.error('Error al validar el token:', error);
      return false;
    }
  },
  
  clearTokens: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
  
  getTokenPayload: function(token: string | null): TokenPayload | null {
    if (!token) return null;
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      return decoded || null;
    } catch (error) {
      console.error('Error al decodificar el token:', error);
      return null;
    }
  },
  
  refreshToken: async function(): Promise<{ access_token: string; refresh_token: string }> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || '/api/v1'}/auth/refresh-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        throw new Error('Failed to refresh token');
      }

      const data = await response.json();
      
      if (data.access_token) {
        this.setToken(data.access_token);
        if (data.refresh_token) {
          this.setRefreshToken(data.refresh_token);
        }
        return data;
      }
      
      throw new Error('Invalid token refresh response');
    } catch (error) {
      console.error('Error refreshing token:', error);
      this.removeTokens();
      throw error;
    }
  }
};

export default tokenService;
