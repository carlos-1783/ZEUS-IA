import { API_BASE_URL } from '@/config';
import tokenService from '@/api/tokenService';

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

function pathnameOnly(urlOrPath: string): string {
  try {
    if (urlOrPath.startsWith('http://') || urlOrPath.startsWith('https://')) {
      return new URL(urlOrPath).pathname;
    }
  } catch {
    /* ignore */
  }
  return urlOrPath.split('?')[0];
}

/**
 * URLs guardadas en BD pueden ser http://127.0.0.1/... (subida detrás de proxy)
 * o /static/... relativas al frontend.
 * Para adjuntos de chat, preferimos GET /api/v1/upload/file/...?token= porque <video>
 * no manda cabecera Authorization y /static suele fallar si el fichero no está en disco.
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
  let work = s;

  try {
    if (work.startsWith('http://') || work.startsWith('https://')) {
      const u = new URL(work);
      const host = u.hostname.toLowerCase();
      if (host === '127.0.0.1' || host === 'localhost' || host === '0.0.0.0') {
        work = `${origin}${u.pathname}${u.search || ''}`;
      }
    } else if (work.startsWith('/static/')) {
      work = origin ? `${origin}${work}` : work;
    }
  } catch {
    return s;
  }

  const path = pathnameOnly(work);
  const m = path.match(/\/static\/uploads\/(images|videos|documents|media)\/([^/?#]+)$/);
  const token = tokenService.getToken();
  const rawBase = (API_BASE_URL || '').replace(/\/+$/, '');
  const base =
    rawBase ||
    (typeof window !== 'undefined' ? `${window.location.origin}/api/v1` : '');
  if (m && token && base) {
    const category = m[1];
    const filename = decodeURIComponent(m[2]);
    return `${base}/upload/file/${category}/${encodeURIComponent(filename)}?token=${encodeURIComponent(token)}`;
  }

  return work;
}
