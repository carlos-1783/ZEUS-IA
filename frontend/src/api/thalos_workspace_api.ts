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

/** Normaliza respuesta API (plana o anidada) a metadata de control. */
export function extractControlMetadata(
  source?: ThalosControlResponse | ThalosControlMetadata | null
): ThalosControlMetadata | null {
  if (!source) return null
  if ('module' in source && 'ui_badge' in source && 'flags' in source) {
    return source
  }
  const nested = source.thalos_control
  if (nested) return nested
  if (source.execution_mode && source.data_origin !== undefined) {
    return {
      execution_mode: source.execution_mode,
      data_origin: source.data_origin,
      real_execution: source.real_execution,
      module: '',
      ui_badge: '',
      flags: {},
    }
  }
  return null
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

export const MODULE_UI_BADGES: Record<string, string> = {
  auditoria_real: 'REAL',
  backup_system: 'PARCIAL',
  log_monitor: 'SIMULADO',
  text_analysis: 'SIMULADO',
  workspace: 'REAL',
}
