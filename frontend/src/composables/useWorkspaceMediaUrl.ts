import { ref, watch, type Ref } from 'vue';
import {
  MediaUrlError,
  openMediaInNewTab,
  protectedFileId,
  resolveWorkspaceMediaUrlAsync,
} from '@/utils/resolveWorkspaceMediaUrl';

type JsonGetter = (endpoint: string) => Promise<any>;

export interface WorkspaceMediaOptions {
  /** Inyectable en tests; por defecto, el cliente API con Authorization en cabecera. */
  getter?: JsonGetter;
  /** Inyectable en tests; por defecto, window.open('', '_blank'). */
  opener?: () => Window | null;
  /** Reloj inyectable en tests (ms). */
  now?: () => number;
}

/** Máximo de re-firmas por error de carga dentro de RESIGN_WINDOW_MS (corta bucles). */
export const MAX_RESIGNS_PER_WINDOW = 3;
export const RESIGN_WINDOW_MS = 60_000;
/** El href de respaldo se renueva cuando ha consumido este porcentaje de su vida. */
const LINK_FRESH_FRACTION = 0.75;

/**
 * URL lista para <video>/<img>/enlace a partir de la URL guardada en BD.
 * - Ficheros de R2 (/api/v1/files/{id}): pide la URL firmada con Authorization en cabecera.
 *   Mientras resuelve, `loading`; si falla, `error` con el motivo real (503, 404...).
 * - Las firmas caducan (R2_SIGNED_URL_TTL_SEC):
 *   · `onMediaError` vuelve a firmar si el medio deja de cargar; `onMediaLoaded` (loadeddata /
 *     load) rearma la re-firma, así que cada caducidad posterior también se recupera. Un tope
 *     por tiempo evita bucles si la firma falla siempre.
 *   · `openInNewTab` pide una firma nueva en el clic (no reutiliza la del render).
 *   · `linkHref` es el href de respaldo (teclado, clic central): `refreshLinkIfStale` lo
 *     renueva al pasar el ratón o enfocar el enlace, sin recargar el reproductor.
 */
export function useWorkspaceMediaUrl(raw: Ref<string>, options: WorkspaceMediaOptions = {}) {
  const getter = options.getter;
  const now = options.now ?? (() => Date.now());
  const src = ref('');
  const linkHref = ref('');
  const loading = ref(false);
  const error = ref<string | null>(null);
  const linkError = ref<string | null>(null);
  const contentType = ref<string | null>(null);
  let resignArmed = true;
  let resignTimes: number[] = [];
  let linkExpiresAt = 0;
  let seq = 0;

  const isProtected = () => Boolean(protectedFileId(raw.value));

  function setLinkExpiry(expiresIn: number | null): void {
    linkExpiresAt = expiresIn ? now() + expiresIn * 1000 * LINK_FRESH_FRACTION : 0;
  }

  async function resolve(): Promise<void> {
    const current = ++seq;
    const value = String(raw.value || '').trim();
    error.value = null;
    contentType.value = null;
    if (!value) {
      src.value = '';
      linkHref.value = '';
      loading.value = false;
      return;
    }
    loading.value = isProtected();
    if (loading.value) {
      src.value = '';
    }
    try {
      const out = await resolveWorkspaceMediaUrlAsync(value, getter);
      if (current !== seq) return;
      src.value = out.url;
      linkHref.value = out.url;
      setLinkExpiry(out.expiresIn);
      contentType.value = out.contentType;
    } catch (err: unknown) {
      if (current !== seq) return;
      src.value = '';
      linkHref.value = '';
      error.value =
        err instanceof MediaUrlError ? err.message : 'No se pudo obtener el enlace del fichero.';
    } finally {
      if (current === seq) loading.value = false;
    }
  }

  /** @loadeddata / @load: la firma actual funciona; la próxima caducidad podrá re-firmarse. */
  function onMediaLoaded(): void {
    resignArmed = true;
  }

  /** @error del medio. Devuelve true si se reintenta con una firma nueva. */
  function onMediaError(): boolean {
    if (!isProtected() || !resignArmed) return false;
    const t = now();
    resignTimes = resignTimes.filter((x) => t - x < RESIGN_WINDOW_MS);
    if (resignTimes.length >= MAX_RESIGNS_PER_WINDOW) return false;
    resignTimes.push(t);
    resignArmed = false; // hasta que la nueva firma cargue de verdad
    void resolve();
    return true;
  }

  /** Renueva el href de respaldo si su firma está cerca de caducar (sin tocar el reproductor). */
  let linkRefresh: Promise<void> | null = null;
  function refreshLinkIfStale(): Promise<void> {
    if (!isProtected() || !linkHref.value || now() < linkExpiresAt) return Promise.resolve();
    if (linkRefresh) return linkRefresh; // hover + focus a la vez: una sola petición
    const current = seq;
    linkRefresh = (async () => {
      try {
        const out = await resolveWorkspaceMediaUrlAsync(raw.value, getter);
        if (current !== seq) return; // el entregable cambió mientras se firmaba
        linkHref.value = out.url;
        setLinkExpiry(out.expiresIn);
      } catch {
        /* el clic normal pide su propia firma y muestra el error */
      } finally {
        linkRefresh = null;
      }
    })();
    return linkRefresh;
  }

  /** Clic en "abrir en pestaña": firma fresca en este momento (llamar síncrono desde el clic). */
  function openInNewTab(): Promise<void> {
    linkError.value = null;
    return openMediaInNewTab(raw.value, getter, options.opener).catch((err: unknown) => {
      linkError.value =
        err instanceof MediaUrlError ? err.message : 'No se pudo abrir el fichero.';
    });
  }

  watch(
    raw,
    () => {
      resignArmed = true;
      resignTimes = [];
      linkError.value = null;
      void resolve();
    },
    { immediate: true },
  );

  return {
    src,
    linkHref,
    loading,
    error,
    linkError,
    contentType,
    onMediaError,
    onMediaLoaded,
    openInNewTab,
    refreshLinkIfStale,
    reload: resolve,
  };
}
