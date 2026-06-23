import api from '@/services/api'

export type AfroditaExecutionMode = 'SIMULATION' | 'READ_ONLY' | 'REAL_ACTIVE'
export type AfroditaDataOrigin = 'backend' | 'user_input' | 'mock' | 'mixed'

export interface AfroditaControlMetadata {
  execution_mode: AfroditaExecutionMode
  data_origin: AfroditaDataOrigin
  real_execution: boolean
  module: string
  ui_badge: string
  flags: Record<string, boolean>
}

export interface AfroditaControlResponse {
  execution_mode: AfroditaExecutionMode
  data_origin?: AfroditaDataOrigin
  real_execution: boolean
  afrodita_control?: AfroditaControlMetadata
}

export interface AfroditaEmployee {
  id: number
  employee_code: string
  full_name: string
  role_title: string
  company_id: number
  phone?: string
  source?: string
}

export interface AfroditaScheduleRow {
  employee_id: string
  day_of_week: number
  day_name: string
  start_time: string
  end_time: string
  shift_type?: string
  location?: string
}

export interface AfroditaStatusResponse extends AfroditaControlResponse {
  system_default_mode: AfroditaExecutionMode
  AFRODITA_EXECUTION_ENABLED: boolean
  AFRODITA_READ_ONLY_MODE: boolean
  AFRODITA_USE_REAL_EMPLOYEES: boolean
  AFRODITA_USE_REAL_CHECKINS: boolean
  AFRODITA_USE_REAL_SCHEDULES: boolean
  module_badges: Record<string, string>
  checkin_entry_point: string
  employees_source: string
  schedules_source: string
  legacy_preserved: boolean
}

function isControlMetadata(value: unknown): value is AfroditaControlMetadata {
  if (!value || typeof value !== 'object') return false
  const v = value as AfroditaControlMetadata
  return typeof v.execution_mode === 'string' && typeof v.ui_badge === 'string'
}

function isControlResponse(value: unknown): value is AfroditaControlResponse {
  if (!value || typeof value !== 'object') return false
  const v = value as AfroditaControlResponse
  return typeof v.execution_mode === 'string' && typeof v.real_execution === 'boolean'
}

function partialNestedFields(nested: unknown): Pick<AfroditaControlMetadata, 'module' | 'ui_badge' | 'flags'> {
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

export function extractAfroditaControl(source?: unknown): AfroditaControlMetadata | null {
  if (!source) return null
  if (isControlMetadata(source)) return source
  if (!isControlResponse(source)) return null
  const nested = source.afrodita_control
  if (nested && isControlMetadata(nested)) return nested
  const extras = partialNestedFields(nested)
  return {
    execution_mode: source.execution_mode,
    data_origin: source.data_origin ?? 'backend',
    real_execution: source.real_execution,
    ...extras,
  }
}

export async function fetchAfroditaStatus() {
  return api.get('/api/v1/afrodita/v1/status') as Promise<AfroditaStatusResponse>
}

export async function fetchAfroditaRrhhStatus() {
  return api.get('/api/v1/afrodita/rrhh/v1/status') as Promise<
    AfroditaStatusResponse & { afrodita_finalization?: Record<string, unknown> }
  >
}

export async function createAfroditaEmployee(payload: {
  full_name: string
  employee_code: string
  role_title?: string
  phone?: string
  hourly_rate?: number
}) {
  return api.post('/api/v1/afrodita/rrhh/v1/employees', payload) as Promise<
    AfroditaControlResponse & {
      success: boolean
      employee: AfroditaEmployee
      executed: boolean
      message?: string
    }
  >
}

export async function fetchAfroditaEmployees() {
  return api.get('/api/v1/afrodita/rrhh/v1/employees') as Promise<
    AfroditaControlResponse & { success: boolean; employees: AfroditaEmployee[]; count: number }
  >
}

export async function fetchAfroditaSchedules() {
  return api.get('/api/v1/afrodita/rrhh/v1/schedules') as Promise<
    AfroditaControlResponse & { success: boolean; schedules: AfroditaScheduleRow[]; count: number }
  >
}

export async function submitAfroditaQrCheckin(qrCode: string) {
  return api.post('/api/v1/afrodita/rrhh/v1/checkin/qr', { qr_code: qrCode }) as Promise<
    AfroditaControlResponse & { success: boolean; result: Record<string, unknown>; text?: string }
  >
}

export async function submitAfroditaContractDraft(payload: {
  employee_name: string
  role: string
  salary: number
  contract_type: string
}) {
  return api.post('/api/v1/afrodita/rrhh/v1/contract-draft', payload) as Promise<
    AfroditaControlResponse & { success: boolean; text?: string }
  >
}

export const MODULE_UI_BADGES: Record<string, string> = {
  facial_checkin: 'NONE',
  qr_checkin: 'PARCIAL',
  employee_manager: 'REAL',
  shift_generator: 'PARTIAL',
}
