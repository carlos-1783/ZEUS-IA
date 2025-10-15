export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type?: string;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  permissions: string[];
  roles: string[];
  company_id?: string;
  company_name?: string;
}
