import { ref, watch, type Ref } from 'vue';
import {
  MediaUrlError,
  protectedFileId,
  resolveWorkspaceMediaUrlAsync,
} from '@/utils/resolveWorkspaceMediaUrl';

/**
 * URL lista para <video>/<img>/enlace a partir de la URL guardada en BD.
 * - Ficheros de R2 (/api/v1/files/{id}): pide la URL firmada con Authorization en cabecera.
 *   Mientras resuelve, `loading`; si falla, `error` con el motivo real (503, 404...).
 * - Las firmas caducan (R2_SIGNED_URL_TTL_SEC): `onMediaError` vuelve a firmar UNA vez antes
 *   de dar el medio por roto.
 */
export function useWorkspaceMediaUrl(raw: Ref<string>) {
  const src = ref('');
  const loading = ref(false);
  const error = ref<string | null>(null);
  const contentType = ref<string | null>(null);
  let resigned = false;
  let seq = 0;

  async function resolve(): Promise<void> {
    const current = ++seq;
    const value = String(raw.value || '').trim();
    error.value = null;
    contentType.value = null;
    if (!value) {
      src.value = '';
      loading.value = false;
      return;
    }
    loading.value = Boolean(protectedFileId(value));
    if (loading.value) {
      src.value = '';
    }
    try {
      const out = await resolveWorkspaceMediaUrlAsync(value);
      if (current !== seq) return;
      src.value = out.url;
      contentType.value = out.contentType;
    } catch (err: unknown) {
      if (current !== seq) return;
      src.value = '';
      error.value =
        err instanceof MediaUrlError ? err.message : 'No se pudo obtener el enlace del fichero.';
    } finally {
      if (current === seq) loading.value = false;
    }
  }

  /** Llamar desde @error del medio. Devuelve true si se reintenta con una firma nueva. */
  function onMediaError(): boolean {
    if (!resigned && protectedFileId(raw.value)) {
      resigned = true;
      void resolve();
      return true;
    }
    return false;
  }

  watch(
    raw,
    () => {
      resigned = false;
      void resolve();
    },
    { immediate: true },
  );

  return { src, loading, error, contentType, onMediaError, reload: resolve };
}
