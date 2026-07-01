import api from '@/services/api'

export type JusticiaExecutionMode = 'SIMULATED' | 'READ_ONLY' | 'REAL'
export type JusticiaDataOrigin = 'backend' | 'user_input' | 'mock' | 'mixed' | 'llm'

export interface JusticiaControlMetadata {
  execution_mode: JusticiaExecutionMode
  data_origin: JusticiaDataOrigin
  real_execution: boolean
  module: string
  ui_badge: string
  flags: Record<string, boolean>
}

export interface AuditTraceItem {
  kind: 'endpoint' | 'table' | 'query' | 'flag'
  ref: string
  detail?: string
}

export interface AuditConclusion {
  domain: string
  check: string
  status: 'PASS' | 'FAIL' | 'WARN' | 'GAP'
  evidence_source: 'DB' | 'API' | 'NONE'
  detail?: string
  value?: unknown
}

export interface JusticiaStatusResponse {
  system_default_mode: JusticiaExecutionMode
  JUSTICE_REAL_AUDIT_ENABLED: boolean
  JUSTICE_READ_ONLY_MODE: boolean
  module_badges: Record<string, string>
  audit_api: string
  execution_mode: JusticiaExecutionMode
  real_execution: boolean
  justicia_control?: JusticiaControlMetadata
}

export interface JusticiaSystemAuditResponse extends JusticiaStatusResponse {
  success: boolean
  audit_id: string
  audit_trace: AuditTraceItem[]
  conclusions: AuditConclusion[]
  domain_verdicts: Record<
    string,
    { domain: string; verdict: string; checks_passed: number; checks_failed: number }
  >
  system_status: string
  summary: string
}

export async function fetchJusticiaStatus() {
  return api.get('/api/v1/justicia/v1/status') as Promise<JusticiaStatusResponse>
}

export async function fetchJusticiaSystemAudit() {
  return api.get('/api/v1/justicia/v1/system-audit') as Promise<JusticiaSystemAuditResponse>
}

export async function fetchJusticiaDocuments(status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return api.get(`/api/v1/justicia/v1/documents${q}`) as Promise<{
    documents: Array<Record<string, unknown>>
    pending: Record<string, unknown>
    count: number
    real_execution: boolean
  }>
}

export async function fetchJusticiaDocumentDetail(documentId: string) {
  return api.get(`/api/v1/justice/documents/${encodeURIComponent(documentId)}`) as Promise<
    Record<string, unknown>
  >
}

export async function justiciaSign(payload: {
  document_id?: string
  document_name?: string
  file_hash?: string
  signer?: string
}) {
  return api.post('/api/v1/justice/sign', payload) as Promise<Record<string, unknown>>
}

export async function justiciaGenerateContract(payload: {
  parties: string[]
  scope?: string
  media_buying?: boolean
}) {
  return api.post('/api/v1/justice/contracts/generate', payload) as Promise<Record<string, unknown>>
}

export async function justiciaGdprCheck(systems: string[] = []) {
  return api.post('/api/v1/justice/gdpr', { systems }) as Promise<Record<string, unknown>>
}

export async function fetchJusticiaComplianceEvents(limit = 30) {
  return api.get(`/api/v1/justice/compliance-events?limit=${limit}`) as Promise<{
    events: Array<Record<string, unknown>>
    count: number
  }>
}
