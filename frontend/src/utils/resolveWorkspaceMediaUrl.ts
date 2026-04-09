import { API_BASE_URL } from '@/config';

/**
 * Origen del backend (sin /api/v1) para montar /static/... en <img> y <video>.
 */
export function getApiOrigin(): string {
  const base = (API_BASE_URL || '').replace(/\/+$/, '');
  if (!base) {
    if (typeof window !== 'undefined') {
      return window.location.origin;
    }
    return '';
  }
  const m = base.match(/^(https?:\/\/[^/]+)/i);
  if (m) {
    return m[1];
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return '';
}

/**
 * URLs guardadas en BD pueden ser http://127.0.0.1/... (subida detrás de proxy)
 * o /static/... relativas al frontend. El elemento <video> no envía Authorization.
 */
export function resolveWorkspaceMediaUrl(raw: string): string {
  const s = String(raw || '').trim();
  if (!s) {
    return '';
  }
  if (/^(blob:|data:)/i.test(s)) {
    return s;
  }

  const origin = getApiOrigin();

  if (s.startsWith('/static/')) {
    return origin ? `${origin}${s}` : s;
  }

  try {
    const u = new URL(s);
    const host = u.hostname.toLowerCase();
    if (host === '127.0.0.1' || host === 'localhost' || host === '0.0.0.0') {
      return origin ? `${origin}${u.pathname}${u.search || ''}` : s;
    }
    return s;
  } catch {
    return s;
  }
}
