import { API_BASE_URL } from '@/config';

/**
 * URL mínima para comprobar que el backend responde.
 * Preferimos GET /health en la raíz (FastAPI) frente a /api/v1/health: menos routers y suele evitar
 * colas con el arranque en Railway cuando el worker aún está ocupado con migraciones.
 */
export function getBackendLivenessUrl(): string {
  if (import.meta.env.DEV) {
    return '/api/v1/health';
  }
  const base = (API_BASE_URL || '').replace(/\/+$/, '');
  if (!base) {
    return typeof window !== 'undefined' ? `${window.location.origin}/health` : '/health';
  }
  const root = base.replace(/\/api\/v1$/i, '');
  return `${root}/health`;
}
