/**
 * Media upload policy — no AI fallback on file-only flows (remove_ai_fallback_from_upload).
 */

export const MEDIA_UPLOAD_STATES = [
  'idle',
  'file_selected',
  'uploading',
  'uploaded',
  'error',
] as const

export type MediaUploadState = (typeof MEDIA_UPLOAD_STATES)[number]

export const FORBIDDEN_AI_FALLBACK_PHRASES = [
  'lo siento por la confusión',
  'no tengo la capacidad de',
  'puedo ayudarte a crear un guion',
] as const

export const MEDIA_UPLOAD_UI = {
  idle: { show: 'No se ha seleccionado ningún archivo', type: 'neutral' as const },
  error: { show: 'Error al subir archivo', type: 'error' as const },
  uploaded: { show: 'Archivo subido correctamente', type: 'success' as const },
} as const

export function isForbiddenAiFallback(text: string | null | undefined): boolean {
  const low = (text || '').toLowerCase()
  if (!low.trim()) return false
  return FORBIDDEN_AI_FALLBACK_PHRASES.some((phrase) => low.includes(phrase))
}

/** Strip LLM apology spam; use when chat was media-adjacent without a real prompt. */
export function sanitizeAgentChatForMediaFlow(
  text: string | null | undefined,
  opts?: { hadMediaOnly?: boolean },
): string {
  const raw = (text || '').trim()
  if (!raw || isForbiddenAiFallback(raw)) {
    if (opts?.hadMediaOnly) {
      return 'Archivo listo. Escribe un mensaje concreto en el chat para analizarlo.'
    }
    return '⚠️ No hay respuesta útil. Escribe un mensaje concreto o usa las herramientas del workspace.'
  }
  return raw
}

export function resolveMediaUploadState(input: {
  isUploading: boolean
  hasError: boolean
  hasUploaded: boolean
  hasFile: boolean
}): MediaUploadState {
  if (input.isUploading) return 'uploading'
  if (input.hasError) return 'error'
  if (input.hasUploaded && !input.hasFile) return 'uploaded'
  if (input.hasFile) return 'file_selected'
  return 'idle'
}
