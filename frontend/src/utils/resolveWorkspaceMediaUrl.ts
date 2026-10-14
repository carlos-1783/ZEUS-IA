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

// ---------------------------------------------------------------------------
// Ficheros en R2 (`/api/v1/files/{id}`): la ruta exige cabecera Authorization, así que no
// puede ir tal cual en <video src>, <img src> ni en un enlace. Se pide la URL firmada (vida
// corta) a GET /api/v1/files/{id}/url con el cliente API (token en cabecera, nunca en la URL).
// ---------------------------------------------------------------------------

const PROTECTED_FILE_RE = /^(?:\/api\/v1)?\/files\/([0-9a-f]{32})\/?$/i;

/** id del fichero si `raw` apunta a /api/v1/files/{id} (relativa o absoluta); si no, null. */
export function protectedFileId(raw: string): string | null {
  const s = String(raw || '').trim();
  if (!s || /^(blob:|data:)/i.test(s)) {
    return null;
  }
  const m = pathnameOnly(s).match(PROTECTED_FILE_RE);
  return m ? m[1].toLowerCase() : null;
}

export interface SignedFileUrl {
  url: string;
  expiresIn: number | null;
  contentType: string | null;
  filename: string | null;
}

/** Error al obtener la firma, con el status HTTP real y un motivo legible. */
export class MediaUrlError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = 'MediaUrlError';
    this.status = status;
  }
}

/** Motivo honesto según la respuesta del backend (503 sin R2, 404 inexistente u otra empresa...). */
export function describeMediaUrlError(status: number | null | undefined, detail?: string | null): string {
  switch (status) {
    case 401:
      return 'Tu sesión ha caducado: vuelve a iniciar sesión para ver el fichero.';
    case 403:
    case 404:
      return 'El fichero no existe o no pertenece a tu empresa.';
    case 502:
      return 'No se pudo acceder al almacenamiento de ficheros. Reintenta en unos minutos.';
    case 503:
      return 'El almacenamiento de ficheros no está configurado todavía; el fichero no se puede mostrar.';
    default:
      return detail ? String(detail) : `No se pudo obtener el enlace del fichero${status ? ` (error ${status})` : ''}.`;
  }
}

type JsonGetter = (endpoint: string) => Promise<any>;

async function defaultGetter(endpoint: string): Promise<any> {
  // Import diferido: el cliente API arrastra el store de auth (y este módulo se usa en tests).
  const { default: api } = await import('@/services/api');
  return api.get(endpoint);
}

/** GET /api/v1/files/{id}/url con Authorization en cabecera -> URL firmada de R2. */
export async function fetchSignedFileUrl(fileId: string, getter: JsonGetter = defaultGetter): Promise<SignedFileUrl> {
  let body: any;
  try {
    body = await getter(`/api/v1/files/${encodeURIComponent(fileId)}/url`);
  } catch (err: any) {
    const status = typeof err?.status === 'number' ? err.status : null;
    throw new MediaUrlError(describeMediaUrlError(status, err?.detail || null), status);
  }
  const url = typeof body?.url === 'string' ? body.url.trim() : '';
  if (!url) {
    throw new MediaUrlError('El servidor no devolvió el enlace del fichero.', null);
  }
  return {
    url,
    expiresIn: typeof body.expires_in === 'number' ? body.expires_in : null,
    contentType: typeof body.content_type === 'string' ? body.content_type : null,
    filename: typeof body.filename === 'string' ? body.filename : null,
  };
}

/**
 * URL utilizable directamente por el navegador: firmada si es un fichero de R2, o la de
 * `resolveWorkspaceMediaUrl` para el resto (static/legacy, blob:, data:, externas).
 */
export async function resolveWorkspaceMediaUrlAsync(
  raw: string,
  getter: JsonGetter = defaultGetter,
): Promise<{ url: string; contentType: string | null; signed: boolean; expiresIn: number | null }> {
  const fileId = protectedFileId(raw);
  if (fileId) {
    const signed = await fetchSignedFileUrl(fileId, getter);
    return { url: signed.url, contentType: signed.contentType, signed: true, expiresIn: signed.expiresIn };
  }
  return { url: resolveWorkspaceMediaUrl(raw), contentType: null, signed: false, expiresIn: null };
}

// ---------------------------------------------------------------------------
// Abrir en pestaña nueva con la firma pedida EN EL CLIC (las firmas caducan).
// La ventana se abre de forma síncrona dentro del gesto del usuario (si se abriera tras un
// await, el bloqueador de ventanas emergentes podría impedirlo) y se navega cuando llega la URL.
// ---------------------------------------------------------------------------

export interface PendingTab {
  /** Navega la pestaña ya abierta a `url`. */
  navigate(url: string): void;
  /** Cierra la pestaña (la operación ha fallado). */
  close(): void;
  /** false si el navegador bloqueó la ventana. */
  readonly opened: boolean;
}

type WindowOpener = () => Window | null;

const defaultOpener: WindowOpener = () =>
  typeof window !== 'undefined' ? window.open('', '_blank') : null;

/** Abre YA (llamar de forma síncrona en el manejador del clic) una pestaña en blanco. */
export function openPendingTab(opener: WindowOpener = defaultOpener): PendingTab {
  const win = opener();
  if (win) {
    try {
      win.opener = null; // equivalente a noopener: la pestaña no puede tocar esta página
    } catch {
      /* ignore */
    }
    try {
      win.document.title = 'Preparando fichero…';
      win.document.body.textContent = 'Preparando el fichero…';
    } catch {
      /* ignore */
    }
  }
  return {
    opened: Boolean(win),
    navigate(url: string) {
      if (!win) {
        throw new MediaUrlError(
          'El navegador bloqueó la ventana nueva: permite ventanas emergentes para este sitio.',
          null,
        );
      }
      win.location.href = url;
    },
    close() {
      try {
        win?.close();
      } catch {
        /* ignore */
      }
    },
  };
}

/**
 * Abre `raw` en una pestaña nueva pidiendo una firma fresca en este momento.
 * Síncrono hasta abrir la pestaña; devuelve la promesa de la navegación. Si falla, cierra la
 * pestaña y rechaza con MediaUrlError (motivo honesto: 503, 404/403, ventana bloqueada...).
 */
export function openMediaInNewTab(
  raw: string,
  getter: JsonGetter = defaultGetter,
  opener: WindowOpener = defaultOpener,
): Promise<void> {
  const tab = openPendingTab(opener);
  return (async () => {
    try {
      const { url } = await resolveWorkspaceMediaUrlAsync(raw, getter);
      if (!url) throw new MediaUrlError('No hay fichero que abrir.', null);
      tab.navigate(url);
    } catch (err: unknown) {
      tab.close();
      throw err instanceof MediaUrlError
        ? err
        : new MediaUrlError('No se pudo abrir el fichero.', null);
    }
  })();
}
