import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { jwtDecode } from 'jwt-decode';
import type { User } from '@/types';
import api from '@/api';

// Types
interface JwtPayload {
  sub: string;
  email?: string;
  name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  exp?: number;
  iat?: number;
  [key: string]: any;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
  token_type?: string;
}

interface LoginResponse {
  success: boolean;
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
  detail?: string;  // Added for error details from the API
  message?: string; // Added for success/error messages
}

// Constants
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// API response types
interface LoginSuccessResponse {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  message?: string;
}

interface LoginErrorResponse {
  error?: string;
  detail?: string;
  message?: string;
}

type LoginApiResponse = LoginSuccessResponse | LoginErrorResponse;

// Type guards
const isErrorResponse = (res: any): res is LoginErrorResponse => {
  return 'error' in res || 'detail' in res;
};

const isSuccessResponse = (res: any): res is LoginSuccessResponse => {
  return 'access_token' in res;
};

// Cast the API to include our methods
const typedApi = api as unknown as {
  login: (credentials: { email: string; password: string }) => Promise<LoginApiResponse>;
  logout: () => Promise<void>;
  refreshToken: (refreshToken: string) => Promise<{ 
    access_token: string; 
    refresh_token?: string; 
    expires_in?: number;
    token_type?: string;
  }>;
  setAuthToken?: (token: string) => void;
};

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY));
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_TOKEN_KEY));
  const user = ref<User | null>(null);
  const isLoading = ref<boolean>(false);
  const error = ref<string | null>(null);
  
  // Getters
  const isAuthenticated = computed<boolean>(() => !!token.value);
  const isAdmin = computed<boolean>(() => !!user.value?.is_superuser);

  // Token management
  function getToken(): string | null {
    return token.value || localStorage.getItem(TOKEN_KEY);
  }

  function getRefreshToken(): string | null {
    return refreshToken.value || localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  function setAuthTokens(tokens: AuthTokens): boolean {
    try {
      if (!tokens.access_token || !tokens.refresh_token) {
        throw new Error('Invalid tokens provided');
      }

      // Update state
      token.value = tokens.access_token;
      refreshToken.value = tokens.refresh_token;

      // Update storage
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

      // Set token in API client if available
      if (typedApi.setAuthToken) {
        typedApi.setAuthToken(tokens.access_token);
      }

      return true;
    } catch (err) {
      console.error('[AuthStore] Error setting auth tokens:', err);
      resetAuthState();
      return false;
    }
  }

  function resetAuthState(): void {
    console.log('[AuthStore] Resetting auth state...');
    
    // Clear state
    token.value = null;
    refreshToken.value = null;
    user.value = null;
    error.value = null;
    
    // Clear storage
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    
    console.log('[AuthStore] Auth state reset complete');
  }

  // Update user data from token
  function updateUserFromToken(accessToken: string): boolean {
    try {
      console.log('[AuthStore] Updating user from token...');
      
      if (!accessToken) {
        console.warn('[AuthStore] No token provided to updateUserFromToken');
        return false;
      }

      const decoded = jwtDecode<JwtPayload>(accessToken);
      console.log('[AuthStore] Decoded token data:', {
        sub: decoded.sub,
        email: decoded.email,
        is_active: decoded.is_active,
        is_superuser: decoded.is_superuser,
        exp: decoded.exp ? new Date(decoded.exp * 1000).toISOString() : 'No expiration',
        iat: decoded.iat ? new Date(decoded.iat * 1000).toISOString() : 'No issued at'
      });

      // Update user data
      user.value = {
        id: decoded.sub,
        email: decoded.email || '',
        name: decoded.name || 'User',
        is_active: decoded.is_active || false,
        is_superuser: decoded.is_superuser || false
      };

      console.log('[AuthStore] User data updated from token');
      return true;

    } catch (error) {
      console.error('[AuthStore] Error in updateUserFromToken:', error);
      resetAuthState();
      return false;
    }
  }

  // Login user with email and password
  async function login(userEmail: string, userPassword: string): Promise<LoginResponse> {
    console.log('[AuthStore] ===== Starting login process =====');
    console.log('[AuthStore] Email provided:', userEmail);
    
    isLoading.value = true;
    error.value = null;
    
    // Clear any existing tokens first
    resetAuthState();
    
    // Validate input
    if (!userEmail || !userPassword) {
      isLoading.value = false;
      return { success: false, error: 'Email and password are required' };
    }
    
    try {
      // Verify localStorage is available
      if (typeof localStorage === 'undefined') {
        throw new Error('localStorage is not available');
      }
      
      // Test localStorage
      const testKey = '__auth_test__';
      try {
        localStorage.setItem(testKey, 'test');
        localStorage.removeItem(testKey);
      } catch (e) {
        console.error('[AuthStore] Error accessing localStorage:', e);
        throw new Error('Could not access local storage');
      }

      console.log('[AuthStore] Calling login API...');
      const response = await typedApi.login({
        email: userEmail.trim(),
        password: userPassword
      });
      
      // Primero verificamos si es una respuesta de error
      if (isErrorResponse(response)) {
        const errorMsg = response.error || response.detail || 'Credenciales inválidas';
        console.error('[AuthStore] Error en la respuesta del servidor:', errorMsg);
        throw new Error(errorMsg);
      }

      // Si no es un error, verificamos que sea una respuesta exitosa
      if (!isSuccessResponse(response)) {
        const errorMsg = 'Formato de respuesta inválido';
        console.error('[AuthStore]', errorMsg, response);
        throw new Error(errorMsg);
      }

      // En este punto, TypeScript sabe que response es LoginSuccessResponse
      console.log('[AuthStore] Respuesta de la API recibida:', {
        hasAccessToken: !!response.access_token,
        hasRefreshToken: !!response.refresh_token,
        expiresIn: response.expires_in
      });

      if (!response || typeof response !== 'object') {
        const errorMsg = 'Invalid server response format';
        console.error('[AuthStore]', errorMsg, response);
        throw new Error(errorMsg);
      }

      // Ya verificamos los errores al principio, no necesitamos esta verificación nuevamente

      // Verify success response
      if (!isSuccessResponse(response)) {
        const errorMsg = 'Invalid response format: missing access_token';
        console.error('[AuthStore]', errorMsg, response);
        throw new Error(errorMsg);
      }

      // At this point, TypeScript knows response is LoginSuccessResponse
      const successResponse = response as LoginSuccessResponse;
      
      console.log('[AuthStore] Access token received, length:', successResponse.access_token?.length || 0);
      
      try {
        // Decode token to verify its validity
        const decoded = jwtDecode<JwtPayload>(successResponse.access_token);
        console.log('[AuthStore] Decoded token:', {
          sub: decoded.sub,
          exp: decoded.exp ? new Date(decoded.exp * 1000).toISOString() : 'No exp',
          isAdmin: decoded.is_superuser || false
        });
        
        // Create tokens object with all required fields
        const tokens = {
          access_token: successResponse.access_token,
          refresh_token: successResponse.refresh_token || '',
          expires_in: successResponse.expires_in || 3600,
          token_type: successResponse.token_type || 'Bearer'
        };
        
        // Verify we have a refresh token
        if (!tokens.refresh_token) {
          console.warn('[AuthStore] No refresh_token received in response');
        }

        console.log('[AuthStore] Saving tokens...');
        
        // Save tokens to state and storage
        const tokensSaved = setAuthTokens(tokens);
        
        if (!tokensSaved) {
          throw new Error('Failed to save tokens');
        }
        
        // Update user info from the token
        if (!updateUserFromToken(tokens.access_token)) {
          console.warn('[AuthStore] Could not update user info from token');
        }
        
        // Verify tokens were saved correctly
        const storedToken = localStorage.getItem(TOKEN_KEY);
        if (!storedToken) {
          throw new Error('Could not verify saved token');
        }
        
        console.log('[AuthStore] Authentication successful');
        return {
          success: true,
          message: 'Login successful',
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token,
          expires_in: tokens.expires_in
        };
        
      } catch (tokenError) {
        console.error('[AuthStore] Error processing token:', tokenError);
        resetAuthState();
        throw new Error('Invalid or corrupted token');
      }

    } catch (err: any) {
      const errorMessage = err.message || 'Login failed';
      console.error('[AuthStore] Login error:', errorMessage, err);
      error.value = errorMessage;
      resetAuthState();
      
      return {
        success: false,
        error: errorMessage
      };
    } finally {
      isLoading.value = false;
    }
  }

  // Logout function
  async function logout(): Promise<void> {
    console.log('[AuthStore] Logging out...');

    try {
      // Call logout API if we have a valid token
      if (token.value) {
        try {
          await typedApi.logout();
        } catch (err) {
          console.warn('[AuthStore] Error during API logout (continuing with local logout):', err);
          // Continue with local logout even if API call fails
        }
      }

      // Reset auth state (this will also clear tokens and user data)
      resetAuthState();

      console.log('[AuthStore] Logout completed');

    } catch (err) {
      console.error('[AuthStore] Error during logout:', err);
      // Ensure we still reset state even if something goes wrong
      resetAuthState();
      throw err;
    }
  }

  // Refresh access token using refresh token
  async function refreshAccessToken(): Promise<boolean> {
    console.log('[AuthStore] Attempting to refresh access token...');

    const currentRefreshToken = getRefreshToken();
    if (!currentRefreshToken) {
      console.warn('[AuthStore] No refresh token available');
      return false;
    }

    // Prevent multiple refresh attempts
    if (isLoading.value) {
      console.log('[AuthStore] Token refresh already in progress');
      return false;
    }

    isLoading.value = true;

    try {
      const response = await typedApi.refreshToken(currentRefreshToken);

      if (response.access_token) {
        console.log('[AuthStore] Token refresh successful');

        // Update tokens
        const success = setAuthTokens({
          access_token: response.access_token,
          refresh_token: response.refresh_token || currentRefreshToken,
          expires_in: response.expires_in,
          token_type: response.token_type || 'Bearer'
        });

        if (!success) {
          throw new Error('Failed to update tokens after refresh');
        }

        // Update user data from new token
        updateUserFromToken(response.access_token);

        return true;
      } else {
        throw new Error('Invalid token refresh response');
      }

    } catch (err) {
      console.error('[AuthStore] Token refresh failed:', err);

      // If refresh fails, log the user out
      if (err instanceof Error && 
          (err.message.includes('401') || 
           err.message.includes('invalid_grant') || 
           err.message.includes('invalid_token') ||
           err.message.includes('Network error'))) {
        console.log('[AuthStore] Refresh token invalid or expired, logging out...');
        await logout();
      }

      return false;
    } finally {
      isLoading.value = false;
    }
  }

  // Initialize the store
  async function initialize(): Promise<boolean> {
    console.log('[AuthStore] Initializing...');
    
    try {
      const currentToken = getToken();
      const currentRefreshToken = getRefreshToken();
      
      // If no token is available, do nothing
      if (!currentToken || !currentRefreshToken) {
        console.log('[AuthStore] No stored tokens found');
        return false;
      }

      // First, set the current token in the API client
      if (typedApi.setAuthToken) {
        typedApi.setAuthToken(currentToken);
      }

      // Check if token is expired
      const decoded = jwtDecode<JwtPayload>(currentToken);
      const now = Math.floor(Date.now() / 1000);
      const isTokenExpired = decoded.exp ? decoded.exp < now : true;
      
      console.log('[AuthStore] Token info:', {
        exp: decoded.exp ? new Date(decoded.exp * 1000).toISOString() : 'No expiration',
        now: new Date(now * 1000).toISOString(),
        isExpired: isTokenExpired
      });

      // If token is expired, clear it but don't try to refresh during init
      if (isTokenExpired) {
        console.log('[AuthStore] Token expired, clearing tokens');
        resetAuthState();
        return false;
      }

      // Update state with current tokens
      token.value = currentToken;
      refreshToken.value = currentRefreshToken;
      
      // Update user data from token (non-blocking)
      try {
        updateUserFromToken(currentToken);
        console.log('[AuthStore] Initialization successful');
        return true;
      } catch (userError) {
        console.warn('[AuthStore] Could not update user from token:', userError);
        // Don't reset auth state, just continue
        return true;
      }
    } catch (error) {
      console.error('[AuthStore] Error during initialization:', error);
      // Don't reset auth state during init, just log and continue
      return false;
    }
  }

  // Return store methods and state
  return {
    // State
    token,
    refreshToken,
    user,
    isLoading,
    error,
    
    // Getters
    isAuthenticated,
    isAdmin,
    
    // Actions
    login,
    logout,
    initialize,
    refreshAccessToken,
    resetAuthState,
    getToken,
    getRefreshToken,
    updateUserFromToken,
    setAuthTokens
  };
});

export type AuthStore = ReturnType<typeof useAuthStore>;
