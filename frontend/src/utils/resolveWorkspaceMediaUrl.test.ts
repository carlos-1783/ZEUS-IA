import { describe, expect, it } from 'vitest'
import {
  MediaUrlError,
  describeMediaUrlError,
  fetchSignedFileUrl,
  protectedFileId,
  resolveWorkspaceMediaUrlAsync,
} from '@/utils/resolveWorkspaceMediaUrl'
import { evidenceMediaUrl } from '@/utils/chatApi'

const ID = '0123456789abcdef0123456789abcdef'

function httpError(status: number, detail?: string) {
  const e = new Error(detail || `HTTP ${status}`) as any
  e.status = status
  e.detail = detail
  return e
}

describe('protectedFileId', () => {
  it('reconoce /api/v1/files/{id} relativo, absoluto y /files/{id}', () => {
    expect(protectedFileId(`/api/v1/files/${ID}`)).toBe(ID)
    expect(protectedFileId(`https://zeus.example/api/v1/files/${ID}`)).toBe(ID)
    expect(protectedFileId(`/files/${ID}`)).toBe(ID)
    expect(protectedFileId(`/api/v1/files/${ID}?x=1`)).toBe(ID)
  })

  it('no confunde otras rutas ni la propia /url', () => {
    expect(protectedFileId(`/api/v1/files/${ID}/url`)).toBeNull()
    expect(protectedFileId('/static/uploads/videos/a.mp4')).toBeNull()
    expect(protectedFileId('/api/v1/files/no-es-un-id')).toBeNull()
    expect(protectedFileId('blob:http://x/abc')).toBeNull()
    expect(protectedFileId('')).toBeNull()
  })
})

describe('fetchSignedFileUrl', () => {
  it('pide /api/v1/files/{id}/url (token en cabecera, nunca en la URL) y devuelve la firma', async () => {
    const calls: string[] = []
    const out = await fetchSignedFileUrl(ID, async (endpoint) => {
      calls.push(endpoint)
      return { url: 'https://r2.test/obj?X-Amz-Signature=abc', expires_in: 300, content_type: 'video/mp4', filename: 'v.mp4' }
    })
    expect(calls).toEqual([`/api/v1/files/${ID}/url`])
    expect(calls[0]).not.toContain('token')
    expect(out).toEqual({ url: 'https://r2.test/obj?X-Amz-Signature=abc', expiresIn: 300, contentType: 'video/mp4', filename: 'v.mp4' })
  })

  it('503 sin R2 -> motivo honesto, no un reproductor roto', async () => {
    await expect(fetchSignedFileUrl(ID, async () => { throw httpError(503) })).rejects.toMatchObject({
      name: 'MediaUrlError',
      status: 503,
      message: describeMediaUrlError(503),
    })
  })

  it('404 (inexistente u otra empresa) y 403 -> mismo mensaje sin revelar existencia', async () => {
    for (const status of [404, 403]) {
      const err = await fetchSignedFileUrl(ID, async () => { throw httpError(status) }).catch((e) => e)
      expect(err).toBeInstanceOf(MediaUrlError)
      expect(err.status).toBe(status)
      expect(err.message).toBe('El fichero no existe o no pertenece a tu empresa.')
    }
  })

  it('respuesta sin url -> error, no cadena vacía', async () => {
    await expect(fetchSignedFileUrl(ID, async () => ({}))).rejects.toBeInstanceOf(MediaUrlError)
  })
})

describe('resolveWorkspaceMediaUrlAsync', () => {
  it('firma las URLs de R2', async () => {
    const out = await resolveWorkspaceMediaUrlAsync(`/api/v1/files/${ID}`, async () => ({ url: 'https://r2.test/s', content_type: 'video/mp4' }))
    expect(out).toEqual({ url: 'https://r2.test/s', contentType: 'video/mp4', signed: true })
  })

  it('no llama a la API para URLs que no son de R2', async () => {
    const out = await resolveWorkspaceMediaUrlAsync('blob:http://x/abc', async () => { throw new Error('no debe llamarse') })
    expect(out).toEqual({ url: 'blob:http://x/abc', contentType: null, signed: false })
  })
})

describe('evidenceMediaUrl', () => {
  it('evidencia de documento PERSEO con vídeo listo -> URL del vídeo', () => {
    const body = { kind: 'document', detail: { payload: { content: { generated_video_status: 'ready', generated_video_url: `/api/v1/files/${ID}` } } } }
    expect(evidenceMediaUrl(body)).toBe(`/api/v1/files/${ID}`)
  })

  it('documento de texto/datos o vídeo aún pendiente -> null (se abre el contenido)', () => {
    expect(evidenceMediaUrl({ kind: 'document', detail: { payload: { content: { copy: 'Texto' } } } })).toBeNull()
    expect(evidenceMediaUrl({ detail: { payload: { content: { generated_video_status: 'pending', generated_video_url: '' } } } })).toBeNull()
    expect(evidenceMediaUrl({ kind: 'invoice', detail: {} })).toBeNull()
  })
})
