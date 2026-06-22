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
