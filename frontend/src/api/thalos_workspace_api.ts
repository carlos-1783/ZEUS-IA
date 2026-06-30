import api from '@/services/api'

export type ThalosExecutionMode = 'SIMULATION' | 'REAL_SAFE' | 'REAL_ACTIVE'
export type ThalosDataOrigin = 'backend' | 'user_input' | 'mock' | 'mixed'

export interface ThalosControlMetadata {
  execution_mode: ThalosExecutionMode
  data_origin: ThalosDataOrigin
  real_execution: boolean
  module: string
  ui_badge: string
  flags: Record<string, boolean>
}

export interface ThalosControlResponse {
  execution_mode: ThalosExecutionMode
  data_origin: ThalosDataOrigin
  real_execution: boolean
  thalos_control?: ThalosControlMetadata
}

export interface ThalosWorkspaceItem {
  id: string
  db_id: number
  type: 'audit' | 'alert' | 'backup'
  status: string
  title: string
  company_id?: number
  workspace_document_id?: number
  data_size_kb: number
  source?: string
  created_at?: string
  payload: Record<string, unknown>
}

export interface ThalosStatusResponse extends ThalosControlResponse {
  system_default_mode: ThalosExecutionMode
  THALOS_EXECUTION_ENABLED: boolean
  THALOS_REAL_LOGS_ENABLED: boolean
  THALOS_BACKUP_ENABLED: boolean
  THALOS_REAL_MONITORING: boolean
  THALOS_WORKSPACE_WRITE_ENABLED: boolean
  module_classification: Record<string, string>
  legacy_preserved: boolean
}

function isControlMetadata(value: unknown): value is ThalosControlMetadata {
  if (!value || typeof value !== 'object') return false
  const v = value as ThalosControlMetadata
  return (
    typeof v.execution_mode === 'string' &&
    typeof v.data_origin === 'string' &&
    typeof v.real_execution === 'boolean' &&
    typeof v.module === 'string' &&
    typeof v.ui_badge === 'string' &&
    typeof v.flags === 'object' &&
    v.flags !== null
  )
}

function isControlResponse(value: unknown): value is ThalosControlResponse {
  if (!value || typeof value !== 'object') return false
  const v = value as ThalosControlResponse
  return (
    typeof v.execution_mode === 'string' &&
    typeof v.data_origin === 'string' &&
    typeof v.real_execution === 'boolean'
  )
}

function partialNestedFields(nested: unknown): Pick<ThalosControlMetadata, 'module' | 'ui_badge' | 'flags'> {
  if (!nested || typeof nested !== 'object') {
    return { module: '', ui_badge: '', flags: {} }
  }
  const n = nested as Record<string, unknown>
  return {
    module: typeof n.module === 'string' ? n.module : '',
    ui_badge: typeof n.ui_badge === 'string' ? n.ui_badge : '',
    flags:
      typeof n.flags === 'object' && n.flags !== null
        ? (n.flags as Record<string, boolean>)
        : {},
  }
}

/** Normaliza respuesta API (plana o anidada) a metadata de control. */
export function extractControlMetadata(source?: unknown): ThalosControlMetadata | null {
  if (!source) return null
  if (isControlMetadata(source)) return source
  if (!isControlResponse(source)) return null

  const nested = source.thalos_control
  if (nested && isControlMetadata(nested)) return nested

  const extras = partialNestedFields(nested)
  return {
    execution_mode: source.execution_mode,
    data_origin: source.data_origin,
    real_execution: source.real_execution,
    ...extras,
  }
}

export async function fetchThalosWorkspaceItems(limit = 50) {
  const res = (await api.get(`/api/v1/thalos/v1/workspace/items?limit=${limit}`)) as ThalosControlResponse & {
    success: boolean
    items: ThalosWorkspaceItem[]
    count: number
  }
  return res
}

export async function runThalosMonitor(companyId?: number, autoExecute = false) {
  const res = await api.post('/api/v1/thalos/v1/monitor', {
    company_id: companyId ?? null,
    auto_execute: autoExecute,
  })
  return res as ThalosControlResponse & Record<string, unknown>
}

export async function fetchThalosEvents(limit = 50) {
  const res = await api.get(`/api/v1/thalos/v1/events?limit=${limit}`)
  return res as ThalosControlResponse & { events: Record<string, unknown>[] }
}

export async function fetchThalosStatus() {
  return api.get('/api/v1/thalos/v1/status') as Promise<ThalosStatusResponse>
}

export async function fetchThalosAlerts(limit = 50, unresolvedOnly = false) {
  const res = await api.get(
    `/api/v1/thalos/v1/alerts?limit=${limit}&unresolved_only=${unresolvedOnly}`,
  )
  return res as ThalosControlResponse & { alerts: Record<string, unknown>[]; count: number }
}

export async function fetchThalosAudit() {
  return api.get('/api/v1/thalos/v1/audit') as Promise<ThalosControlResponse & Record<string, unknown>>
}

export async function ingestThalosLogs(logs: string[]) {
  return api.post('/api/v1/thalos/logs/ingest', { logs }) as Promise<ThalosControlResponse & Record<string, unknown>>
}
