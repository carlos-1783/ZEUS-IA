export interface User {
  id: string;
  email: string;
  username?: string;
  role?: string;
  [key: string]: any; // Para otros campos que puedan venir en el token
}

export interface ApiResponse<T = any> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
  error?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  username?: string;
  password?: string;
  grant_type?: string;
}