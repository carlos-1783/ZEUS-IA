import { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

export interface UserProfile {
  id: string;
  username?: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified?: boolean;
  created_at?: string;
  updated_at?: string;
  /** owner | employee - employee solo TPV + control horario */
  role?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type?: string;
}

export interface SystemStatus {
  cpu_usage: number;
  memory_usage: number;
  storage_usage: number;
  network_usage: number;
  active_users: number;
  last_updated: string;
  services: Record<string, 'online' | 'offline' | 'degraded'>;
  empresa_actual?: string | null;
  empresa_activada?: boolean;
  modulos_activos?: {
    ventas: boolean;
    inventario: boolean;
    facturacion: boolean;
    marketing: boolean;
  };
  ultima_actualizacion?: string;
}

export interface ApiResponse<T = any> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
  error?: string;
  errors?: Record<string, string[]>;
  detail?: string | Record<string, any>;
  status_code?: number;
}

export interface ApiErrorResponse {
  message?: string;
  error?: string;
  errors?: Record<string, string[]>;
  detail?: string | Record<string, any>;
  status_code?: number;
  code?: string;
}

export interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
  skipAuthRefresh?: boolean;
}

export type RegisterBusinessType = 'restaurant' | 'retail' | 'services';

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
  phone: string;
  company_name: string;
  business_type: RegisterBusinessType;
}

export interface ApiClient {
  login: (credentials: { username: string; password: string }) => Promise<AuthTokens>;
  register: (payload: RegisterPayload) => Promise<{ id: number; email: string; full_name?: string; phone?: string }>;
  logout: () => Promise<void>;
  refreshToken: (refreshToken: string) => Promise<AuthTokens>;
  getCurrentUser: () => Promise<UserProfile>;
  getSystemStatus: () => Promise<SystemStatus>;
  forgotPassword: (email: string) => Promise<{ msg: string; reset_link?: string }>;
  setNewPassword: (payload: { token: string; new_password: string }) => Promise<{ msg: string }>;
  request: <T = any>(config: AxiosRequestConfig) => Promise<T>;
}

// Token payload interface
export interface TokenPayload {
  sub: string;
  email?: string;
  exp?: number;
  iat?: number;
  is_active?: boolean;
  is_superuser?: boolean;
  [key: string]: unknown;
}

export interface TokenService {
  setToken: (token: string | null) => void;
  getToken: () => string | null;
  setRefreshToken: (token: string | null) => void;
  getRefreshToken: () => string | null;
  removeTokens: () => void;
  removeToken: () => void;
  isTokenExpired: (token: string | null) => boolean;
  isValidToken: (token: string | null) => boolean;
  clearTokens: () => void;
  getTokenPayload: (token: string | null) => TokenPayload | null;
  refreshToken: () => Promise<{ access_token: string; refresh_token: string }>;
}

// Extend Window interface to handle both browser and Node.js environments
declare global {
  interface Window {
    // In browsers, setTimeout returns a number, in Node.js it returns a Timeout object
    tokenRefreshTimeout?: number | NodeJS.Timeout;
  }
}
