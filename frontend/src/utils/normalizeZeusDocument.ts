import { deduplicateDoc } from './deduplicateDoc'

export interface ZeusDocument {
  agent_source: string
  type: string
  title?: string
  created_at?: string
  client?: string
  items?: { description: string; price: number }[]
  total?: number
  data?: Record<string, unknown>
  content?: unknown
}

const parseJson = (input: unknown): unknown => {
  if (typeof input !== 'string') return input
  const s = input.trim()
  if (!s.startsWith('{') && !s.startsWith('[')) return input
  try {
    return JSON.parse(s)
  } catch {
    return input
  }
}

const asRecord = (input: unknown): Record<string, unknown> => {
  const parsed = parseJson(input)
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : {}
}

const num = (v: unknown) => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

/** Normalize Afrodita / Rafael / Justicia / approval payloads into one viewer shape. */
export function normalizeZeusDocument(raw: unknown): ZeusDocument | null {
  if (!raw) return null

  const root = deduplicateDoc(asRecord(raw))
  const payload = deduplicateDoc(
    asRecord(root.document_payload ?? root.document_payload_json ?? root.payload ?? root),
  )

  if (root.agent_source && typeof root.agent_source === 'string') {
    return {
      agent_source: String(root.agent_source).toUpperCase(),
      type: String(root.type || 'document'),
      title: root.title ? String(root.title) : undefined,
      created_at: root.created_at ? String(root.created_at) : undefined,
      client: root.client ? String(root.client) : undefined,
      items: Array.isArray(root.items) ? (root.items as ZeusDocument['items']) : undefined,
      total: root.total != null ? num(root.total) : undefined,
      data: asRecord(root.data),
      content: root.content,
    }
  }

  const agentName = String(
    root.agent_name ?? root.owner_agent ?? payload.owner_agent ?? 'UNKNOWN',
  ).toUpperCase()
  const docType = String(
    root.document_type ?? root.type ?? payload.type ?? payload.doc_type ?? 'document',
  ).toLowerCase()

  if (root.legal_document || root.employee) {
    const legal = asRecord(root.legal_document)
    const employee = asRecord(root.employee)
    return {
      agent_source: 'AFRODITA',
      type: 'contract_rrhh',
      title: `Contrato ${employee.full_name || root.employee_name || ''}`.trim(),
      created_at: root.created_at ? String(root.created_at) : undefined,
      data: {
        employee: employee.full_name || root.employee_name || '',
        position: root.role || payload.role || employee.role_title || '',
        salary: num(root.salary ?? payload.salary),
        contract_id: root.contract_id ?? legal.document_id,
        content_preview: legal.content_preview ?? legal.content,
      },
    }
  }

  if (agentName === 'RAFAEL' || docType.includes('invoice') || docType.includes('tpv')) {
    const inner = asRecord(payload.content ?? payload)
    const fiscal = asRecord(inner.fiscal_data ?? inner.content)
    const products = Array.isArray(fiscal.productos) ? fiscal.productos : []
    const items =
      products.length > 0
        ? products.map((p) => {
            const row = asRecord(p)
            return {
              description: String(row.nombre || row.description || 'Concepto'),
              price: num(row.subtotal ?? row.precio_unitario ?? row.price),
            }
          })
        : Array.isArray(payload.items)
          ? (payload.items as ZeusDocument['items'])
          : []

    const total =
      num(payload.total) ||
      num(fiscal.total) ||
      num(inner.total) ||
      items.reduce((s, i) => s + num(i.price), 0)

    return {
      agent_source: 'RAFAEL',
      type: 'invoice',
      title: String(payload.title || root.title || 'Factura'),
      client: String(payload.client ?? fiscal.cliente ?? inner.client ?? 'Cliente'),
      items,
      total,
      content: payload.content ?? inner,
    }
  }

  if (agentName === 'JUSTICIA' || docType.includes('contract') || docType.includes('legal')) {
    const content =
      payload.content ??
      payload.body ??
      root.content ??
      (typeof payload === 'string' ? payload : undefined)
    return {
      agent_source: 'JUSTICIA',
      type: docType.includes('contract') ? 'contract' : 'legal_document',
      title: String(payload.title || root.title || 'Documento legal'),
      content,
      data: payload,
    }
  }

  if (agentName === 'AFRODITA' || docType.includes('contract') || docType.includes('rrhh')) {
    return {
      agent_source: 'AFRODITA',
      type: 'contract_rrhh',
      title: String(payload.title || 'Contrato laboral'),
      data: {
        employee: payload.employee_name ?? payload.employee ?? '',
        position: payload.role ?? payload.position ?? '',
        salary: num(payload.salary),
        content_preview: payload.content_preview ?? payload.content,
      },
    }
  }

  return {
    agent_source: agentName,
    type: docType,
    title: String(payload.title || root.title || 'Documento'),
    content: payload.content ?? payload,
    data: payload,
  }
}
