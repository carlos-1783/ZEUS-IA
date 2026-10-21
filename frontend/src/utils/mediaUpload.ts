/**
 * Subida real de imagen / vídeo / PDF (POST /api/v1/upload -> R2 bajo la empresa de la sesión).
 * Única fuente de los tipos, el límite y la llamada: la usan ImageUploader.jsx y el clip del orbe
 * de voz (workspace de PERSEO). Los tipos y el máximo son los mismos que valida el backend
 * (backend/app/api/v1/endpoints/upload.py: ALLOWED_CONTENT_TYPES, MAX_BYTES).
 */
import api from '@/services/api';
import { MEDIA_UPLOAD_UI } from '@/utils/mediaUploadPolicy';

export const MEDIA_ALLOWED_TYPES: readonly string[] = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'application/pdf',
];

export const MEDIA_ACCEPT_ATTR = 'image/*,video/*,application/pdf';

export const MEDIA_MAX_BYTES = 100 * 1024 * 1024; // 100 MB

export interface UploadedMedia {
  url: string;
  content_type?: string;
  category?: string;
  filename?: string;
  file_id?: string | number;
  [key: string]: unknown;
}

export function isAllowedMediaType(file: File | null | undefined): boolean {
  return Boolean(file?.type && MEDIA_ALLOWED_TYPES.includes(file.type));
}

/** Sube el fichero; devuelve la respuesta del servidor o lanza un Error con el motivo real. */
export async function uploadMediaFile(file: File): Promise<UploadedMedia> {
  const formData = new FormData();
  formData.append('file', file);
  const data = await api.postFormData('/api/v1/upload', formData);
  if (!data?.success || !data?.url) {
    throw new Error(data?.detail || data?.error || MEDIA_UPLOAD_UI.error.show);
  }
  return data as UploadedMedia;
}

/**
 * Clave de `context` con la que viaja el medio en el siguiente mensaje del chat
 * (`image_url` | `video_url` | `pdf_url`). Se decide por el content_type que devolvió el servidor;
 * si no lo hay, por la URL (las URL estables /api/v1/files/{id} no llevan extensión).
 */
export function mediaContextKeyFor(url: string, contentType?: string | null): 'pdf_url' | 'video_url' | 'image_url' {
  const ct = String(contentType || '').toLowerCase();
  if (ct === 'application/pdf') return 'pdf_url';
  if (ct.startsWith('video/')) return 'video_url';
  if (ct.startsWith('image/')) return 'image_url';
  const u = url || '';
  if (/\.pdf($|\?)/i.test(u) || u.includes('/documents/')) return 'pdf_url';
  if (/\.(mp4|webm|mov|m4v)($|\?)/i.test(u) || u.includes('/videos/')) return 'video_url';
  return 'image_url';
}
