import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import {
  MediaUrlError,
  describeMediaUrlError,
  fetchSignedFileUrl,
  openMediaInNewTab,
  protectedFileId,
  resolveWorkspaceMediaUrlAsync,
} from '@/utils/resolveWorkspaceMediaUrl'
import { evidenceMediaUrl, openEvidence } from '@/utils/chatApi'
import {
  MAX_RESIGNS_PER_WINDOW,
  RESIGN_WINDOW_MS,
  useWorkspaceMediaUrl,
} from '@/composables/useWorkspaceMediaUrl'

const ID = '0123456789abcdef0123456789abcdef'

function httpError(status: number, detail?: string) {
  const e = new Error(detail || `HTTP ${status}`) as any
  e.status = status
  e.detail = detail
  return e
}

function fakeWindow() {
  const w: any = { opener: {}, closed: false, document: { title: '', body: { textContent: '' } }, location: { href: '' } }
  w.close = () => {
    w.closed = true
  }
  return w
}

const flush = () => new Promise((r) => setTimeout(r, 0))

/** Getter que firma con una URL distinta en cada llamada (como R2: firma con caducidad). */
function signer(expiresIn = 40) {
  let n = 0
  const calls: string[] = []
  const get = async (endpoint: string) => {
    calls.push(endpoint)
    n += 1
    return { url: `https://r2.test/obj?sig=${n}`, expires_in: expiresIn, content_type: 'video/mp4' }
  }
  return { get, calls, count: () => n }
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
    const out = await resolveWorkspaceMediaUrlAsync(`/api/v1/files/${ID}`, async () => ({ url: 'https://r2.test/s', content_type: 'video/mp4', expires_in: 300 }))
    expect(out).toEqual({ url: 'https://r2.test/s', contentType: 'video/mp4', signed: true, expiresIn: 300 })
  })

  it('no llama a la API para URLs que no son de R2', async () => {
    const out = await resolveWorkspaceMediaUrlAsync('blob:http://x/abc', async () => { throw new Error('no debe llamarse') })
    expect(out).toEqual({ url: 'blob:http://x/abc', contentType: null, signed: false, expiresIn: null })
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

describe('openMediaInNewTab (firma pedida en el clic)', () => {
  it('abre la pestaña de forma síncrona y la navega a una firma NUEVA en cada clic', async () => {
    const w = fakeWindow()
    const s = signer()
    const order: string[] = []
    const p = openMediaInNewTab(`/api/v1/files/${ID}`, async (e) => { order.push('firma'); return s.get(e) }, () => {
      order.push('ventana')
      return w
    })
    // la ventana se abre de forma síncrona, ANTES de pedir la firma: el bloqueador no la impide
    expect(order[0]).toBe('ventana')
    expect(w.opener).toBeNull()
    expect(w.location.href).toBe('')
    await p
    expect(w.location.href).toBe('https://r2.test/obj?sig=1')
    await openMediaInNewTab(`/api/v1/files/${ID}`, s.get, () => w)
    expect(w.location.href).toBe('https://r2.test/obj?sig=2')
    expect(s.calls.every((c) => !c.includes('token'))).toBe(true)
  })

  it('si la firma falla, cierra la pestaña y da el motivo honesto', async () => {
    const w = fakeWindow()
    const err = await openMediaInNewTab(`/api/v1/files/${ID}`, async () => { throw httpError(503) }, () => w).catch((e) => e)
    expect(w.closed).toBe(true)
    expect(err).toBeInstanceOf(MediaUrlError)
    expect(err.message).toBe(describeMediaUrlError(503))
  })

  it('ventana bloqueada -> error explícito, no un falso éxito', async () => {
    const err = await openMediaInNewTab(`/api/v1/files/${ID}`, signer().get, () => null).catch((e) => e)
    expect(err).toBeInstanceOf(MediaUrlError)
    expect(err.message).toContain('bloqueó')
  })
})

describe('useWorkspaceMediaUrl (caducidades)', () => {
  it('se recupera de DOS caducidades seguidas en la misma vista', async () => {
    const s = signer()
    const m = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), { getter: s.get })
    await flush()
    expect(m.src.value).toBe('https://r2.test/obj?sig=1')
    m.onMediaLoaded()
    expect(m.onMediaError()).toBe(true) // 1a caducidad
    await flush()
    expect(m.src.value).toBe('https://r2.test/obj?sig=2')
    m.onMediaLoaded() // la nueva firma cargó
    expect(m.onMediaError()).toBe(true) // 2a caducidad: también se re-firma
    await flush()
    expect(m.src.value).toBe('https://r2.test/obj?sig=3')
    expect(m.error.value).toBeNull()
  })

  it('sin bucle si la firma nueva tampoco carga', async () => {
    const s = signer()
    const m = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), { getter: s.get })
    await flush()
    expect(m.onMediaError()).toBe(true)
    await flush()
    expect(m.onMediaError()).toBe(false) // no hubo loadeddata: no se insiste
    expect(m.onMediaError()).toBe(false)
    expect(s.count()).toBe(2)
  })

  it('tope de re-firmas por ventana de tiempo aunque cargue y falle en bucle', async () => {
    let t = 1_000_000
    const s = signer()
    const m = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), { getter: s.get, now: () => t })
    await flush()
    for (let i = 0; i < MAX_RESIGNS_PER_WINDOW; i += 1) {
      m.onMediaLoaded()
      expect(m.onMediaError()).toBe(true)
      await flush()
    }
    m.onMediaLoaded()
    expect(m.onMediaError()).toBe(false)
    t += RESIGN_WINDOW_MS + 1
    expect(m.onMediaError()).toBe(true) // pasada la ventana vuelve a permitirse
  })

  it('openInNewTab pide firma en cada clic y muestra el error si falla', async () => {
    const s = signer()
    const w = fakeWindow()
    const m = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), { getter: s.get, opener: () => w })
    await flush()
    const before = s.count()
    await m.openInNewTab()
    expect(s.count()).toBe(before + 1)
    expect(w.location.href).toBe(`https://r2.test/obj?sig=${before + 1}`)
    expect(m.linkError.value).toBeNull()
    const failing = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), {
      getter: async () => { throw httpError(404) },
      opener: () => fakeWindow(),
    })
    await flush()
    await failing.openInNewTab()
    expect(failing.linkError.value).toBe('El fichero no existe o no pertenece a tu empresa.')
  })

  it('el href de respaldo se renueva solo cuando está cerca de caducar', async () => {
    let t = 0
    const s = signer(40)
    const m = useWorkspaceMediaUrl(ref(`/api/v1/files/${ID}`), { getter: s.get, now: () => t })
    await flush()
    expect(m.linkHref.value).toBe('https://r2.test/obj?sig=1')
    t = 10_000
    await m.refreshLinkIfStale()
    expect(s.count()).toBe(1) // aún fresca
    t = 31_000 // > 75 % de 40 s
    await m.refreshLinkIfStale()
    expect(m.linkHref.value).toBe('https://r2.test/obj?sig=2')
    expect(m.src.value).toBe('https://r2.test/obj?sig=1') // el reproductor no se recarga
    t = 70_000 // otra vez caducada: hover + focus a la vez -> una sola firma
    await Promise.all([m.refreshLinkIfStale(), m.refreshLinkIfStale()])
    expect(s.count()).toBe(3)
    expect(m.linkHref.value).toBe('https://r2.test/obj?sig=3')
  })
})

describe('openEvidence', () => {
  it('abre la pestaña antes del fetch y muestra el JSON de un documento', async () => {
    const w = fakeWindow()
    const order: string[] = []
    const g: any = globalThis
    const prev = g.fetch
    g.fetch = async () => {
      order.push('fetch')
      return { ok: true, status: 200, json: async () => ({ kind: 'document', detail: { payload: { content: { copy: 'x' } } } }) }
    }
    try {
      const p = openEvidence({ kind: 'document', id: 2, agent: 'PERSEO', title: 'Doc', url: '/api/v1/jarvis/evidence/document/2', status: 'draft' }, 't', () => {
        order.push('ventana')
        return w
      })
      expect(w.opener).toBeNull()
      expect(order[0]).toBe('ventana') // la ventana se abre antes de pedir el recurso
      await p
      expect(w.location.href.startsWith('blob:')).toBe(true)
    } finally {
      g.fetch = prev
    }
  })

  it('si el recurso falla, cierra la pestaña y propaga el error', async () => {
    const w = fakeWindow()
    const g: any = globalThis
    const prev = g.fetch
    g.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) })
    try {
      const err = await openEvidence({ kind: 'document', id: 9, agent: 'PERSEO', title: 'X', url: '/api/v1/jarvis/evidence/document/9', status: 'draft' }, 't', () => w).catch((e) => e)
      expect(w.closed).toBe(true)
      expect(err.message).toBe('El recurso ya no está disponible.')
    } finally {
      g.fetch = prev
    }
  })
})
