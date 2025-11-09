import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import config from '@/config';
import tokenService from './tokenService';
import type { ApiResponse, AuthTokens, UserProfile, SystemStatus } from './types';

class ApiClient {
  private instance: AxiosInstance;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  constructor() {
    this.instance = axios.create({
      baseURL: config.api.baseUrl,
      timeout: config.api.timeout,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      withCredentials: true,
    });

    this.setupInterceptors();
  }

  private clearQueue() {
    this.refreshSubscribers = [];
  }

  private processRefreshSubscribers(token: string) {
    // Create a copy of the subscribers and clear the original array
    const subscribers = [...this.refreshSubscribers];
    this.clearQueue();
    
    // Process each subscriber with the new token
    subscribers.forEach(callback => {
      try {
        if (typeof callback === 'function') {
          callback(token);
        }
      } catch (error) {
        console.error('Error in refresh subscriber callback:', error);
      }
    });
  }

  private setupInterceptors() {
    // Request interceptor
    this.instance.interceptors.request.use(
      (config) => {
        const token = tokenService.getToken();
        if (token && !config.headers['Authorization']) {
          config.headers['Authorization'] = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error) => {
        const originalRequest = error.config;

        // Skip refresh for login or refresh-token endpoints
        if (originalRequest.url?.includes('/auth/refresh-token') || 
            originalRequest.url?.includes('/auth/login') ||
            originalRequest.skipAuthRefresh) {
          return Promise.reject(error);
        }

        // If error is not 401 or it's a retry request, reject
        if (error.response?.status !== 401 || originalRequest._retry) {
          return Promise.reject(error);
        }

        // Mark request as retried
        originalRequest._retry = true;

        // If already refreshing, add to queue
        if (this.isRefreshing) {
          return new Promise((resolve, reject) => {
            this.refreshSubscribers.push((token: string | null) => {
              if (!token) {
                return reject(new Error('Failed to refresh token'));
              }
              originalRequest.headers['Authorization'] = `Bearer ${token}`;
              resolve(this.instance(originalRequest));
            });
          });
        }

        this.isRefreshing = true;

        try {
          // Get refresh token from storage
          const refreshToken = tokenService.getRefreshToken();
          
          if (!refreshToken) {
            // No refresh token available, redirect to login
            if (typeof window !== 'undefined') {
              window.location.href = '/auth/login';
            }
            return Promise.reject(error);
          }

          // Try to refresh the token
          const response = await this.refreshToken(refreshToken);
          const { access_token, refresh_token } = response.data;
          
          if (!access_token) {
            throw new Error('No access token received');
          }
          
          // Update tokens in storage
          tokenService.setToken(access_token);
          if (refresh_token) {
            tokenService.setRefreshToken(refresh_token);
          }

          // Update the authorization header
          originalRequest.headers = {
            ...originalRequest.headers,
            'Authorization': `Bearer ${access_token}`
          };
          
          // Process all queued requests
          this.processRefreshSubscribers(access_token);
          
          // Retry the original request
          return this.instance(originalRequest);
          
        } catch (refreshError) {
          // If refresh fails, clear tokens and redirect to login
          tokenService.clearTokens();
          
          if (typeof window !== 'undefined') {
            window.location.href = '/auth/login';
          }
          
          return Promise.reject(refreshError);
        } finally {
          this.isRefreshing = false;
          this.clearQueue();
        }
      }
    );
  }

  // Auth methods
  public async login(credentials: { username: string; password: string }): Promise<AuthTokens> {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    formData.append('grant_type', 'password');

    const response = await this.instance.post<ApiResponse<AuthTokens>>(
      'auth/login',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    if (response.data.status === 'success' && response.data.data) {
      const { access_token, refresh_token } = response.data.data;
      tokenService.setToken(access_token);
      tokenService.setRefreshToken(refresh_token);
      return response.data.data;
    }

    throw new Error(response.data.error || 'Login failed');
  }

  public async logout(): Promise<void> {
    try {
      const refreshToken = tokenService.getRefreshToken();
      if (refreshToken) {
        await this.instance.post('auth/logout', { refresh_token: refreshToken });
      }
    } catch (error) {
      console.error('Error during logout:', error);
    } finally {
      tokenService.removeTokens();
      window.location.href = '/login';
    }
  }

  public async refreshToken(refreshToken: string): Promise<{ data: AuthTokens }> {
    console.log('[ApiClient] Attempting to refresh token...');
    if (!refreshToken) {
      console.error('[ApiClient] No refresh token provided');
      throw new Error('No refresh token available');
    }

    try {
      // Create a custom config that extends AxiosRequestConfig
      const requestConfig: AxiosRequestConfig = {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        // @ts-ignore - Custom property to prevent infinite refresh loops
        skipAuthRefresh: true
      };

      const response = await this.instance.post<ApiResponse<AuthTokens>>(
        'auth/refresh-token',
        { refresh_token: refreshToken },
        requestConfig
      );
      
      const responseData = response.data;
      
      if (!responseData || responseData.status !== 'success' || !responseData.data) {
        console.error('[ApiClient] Invalid refresh token response:', responseData);
        throw new Error('Invalid refresh token response');
      }

      if (!responseData.data.access_token) {
        console.error('[ApiClient] No access token in response:', responseData);
        throw new Error('No access token received');
      }
      
      console.log('[ApiClient] Token refresh successful');
      return { data: responseData.data };
      
    } catch (error) {
      console.error('[ApiClient] Error refreshing token:', error);
      tokenService.clearTokens();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw error;
    }
  }

  // User methods
  public async getCurrentUser(): Promise<UserProfile> {
    const response = await this.instance.get<ApiResponse<UserProfile>>('auth/me');
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data;
    }
    
    throw new Error(response.data.error || 'Failed to fetch user profile');
  }

  // System methods
  public async getSystemStatus(): Promise<SystemStatus> {
    const response = await this.instance.get<ApiResponse<SystemStatus>>('system/status');
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data;
    }
    
    throw new Error(response.data.error || 'Failed to fetch system status');
  }

  public async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.instance.get<T>(url, config);
  }

  // Generic request method
  public async request<T = any>(config: AxiosRequestConfig): Promise<T> {
    const response = await this.instance.request<ApiResponse<T>>(config);
    
    if (response.data.status === 'success') {
      return response.data.data as T;
    }
    
    throw new Error(response.data.error || 'API request failed');
  }
}

// Create and export a singleton instance
export const api = new ApiClient();

export default api;
