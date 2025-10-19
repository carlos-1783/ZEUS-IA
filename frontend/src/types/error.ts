export interface ErrorResponse {
  code?: string;
  message: string;
  originalError?: any;
  isRetryable?: boolean;
  status?: number;
  details?: any;
  validationErrors?: Record<string, string[]>;
  retryAfter?: number;
}

export interface ApiErrorResponse {
  message?: string;
  error?: string;
  errors?: Record<string, string[]>;
  detail?: string | Record<string, any>;
  status_code?: number;
}
