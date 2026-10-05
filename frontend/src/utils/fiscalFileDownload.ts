import api from '@/services/api'

const LEGACY_FISCAL_STATIC_RE = /(^|\/)static\/fiscal\//i

/**
 * Los ficheros fiscales ya no se sirven por /static (sin auth). Las URLs nuevas apuntan a
 * /api/v1/rafael-fiscal/fiscal-files/... (endpoint autenticado). Los documentos antiguos con
 * file_url /static/fiscal/... se descargan por el endpoint autenticado por id de documento.
 */
export function resolveFiscalFileEndpoint(raw: string, workspaceDocId?: string | number | null): string {
  if (!raw) return ''
  if (LEGACY_FISCAL_STATIC_RE.test(raw)) {
    const id = String(workspaceDocId ?? '').replace(/^ws:/, '')
    return /^\d+$/.test(id) ? `/api/v1/rafael-fiscal/documents/${id}/download` : ''
  }
  return raw
}

function filenameFromEndpoint(endpoint: string, fallback: string): string {
  const last = endpoint.split('?')[0].split('/').pop() || ''
  return /\.(pdf|xlsx)$/i.test(last) ? last : fallback
}

/** Descarga un fichero protegido con el token del cliente API (un <a href> no enviaría Authorization). */
export async function downloadAuthenticatedFile(endpoint: string, fallbackName = 'documento-fiscal'): Promise<void> {
  const blob = await api.getBlob(endpoint)
  const objectUrl = window.URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filenameFromEndpoint(endpoint, fallbackName)
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 10_000)
  }
}
