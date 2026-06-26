import api from '@/services/api'

export type AfroditaExecutionMode = 'REAL' | 'SIMULATED' | 'ERROR'
export type AfroditaDataOrigin = 'backend' | 'user_input' | 'mock' | 'mixed'

export interface AfroditaControlResponse {
  execution_mode: AfroditaExecutionMode
  data_origin?: AfroditaDataOrigin
  real_execution: boolean
  writes_enabled?: boolean
  db_connected?: boolean
  success?: boolean
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

export interface AfroditaTruthStatus {
  execution_mode: AfroditaExecutionMode
  system_default_mode?: AfroditaExecutionMode
  db_connected: boolean
  writes_enabled: boolean
  flags_loaded: boolean
  execution_enabled: boolean
  read_only_mode: boolean
  AFRODITA_EXECUTION_ENABLED: boolean
  AFRODITA_READ_ONLY_MODE: boolean
  flags: Record<string, boolean>
  flags_env_present?: Record<string, boolean>
  checkin_entry_point: string
  employees_source: string
  schedules_source: string
  rrhh_api_prefix: string
  ops_api_prefix?: string
  salvaged_from_misconfigured_env?: boolean
  resolution?: Record<string, string>
  railway_env_audit?: {
    count: number
    misconfigured_env_vars: Array<{ host_var: string; embedded: string; hint: string }>
  }
  workspace?: {
    enabled: boolean
    connected: boolean
    db_connected: boolean
    files_api: string
    playbooks_api: string
    status: AfroditaExecutionMode
  }
}

export interface AfroditaWorkspaceFile {
  id: number
  name: string
  content: string | null
  company_id?: number | null
  created_at: string | null
  updated_at: string | null
}

export interface AfroditaWorkspacePlaybook {
  id: number
  title: string
  content: Record<string, unknown>
  created_at: string | null
}

export function executionModeLabel(mode: AfroditaExecutionMode | null | undefined): string {
  if (mode === 'REAL') return 'REAL'
  if (mode === 'ERROR') return 'SYSTEM ERROR'
  return 'NO EXECUTION'
}

export async function fetchAfroditaStatus() {
  return api.get('/api/v1/afrodita/status') as Promise<AfroditaTruthStatus>
}

export async function fetchAfroditaWorkspaceFiles(limit = 100) {
  return api.get(`/api/v1/afrodita/workspace/files?limit=${limit}`) as Promise<
    AfroditaControlResponse & {
      success: boolean
      files: AfroditaWorkspaceFile[]
      count: number
      connected?: boolean
    }
  >
}

export async function fetchAfroditaWorkspacePlaybooks(limit = 100) {
  return api.get(`/api/v1/afrodita/workspace/playbooks?limit=${limit}`) as Promise<
    AfroditaControlResponse & {
      success: boolean
      playbooks: AfroditaWorkspacePlaybook[]
      count: number
      connected?: boolean
    }
  >
}

export async function fetchAfroditaRrhhStatus() {
  return api.get('/api/v1/afrodita/rrhh/v1/status') as Promise<
    AfroditaTruthStatus & { afrodita_finalization?: Record<string, unknown> }
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
      employee_id: number
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
    AfroditaControlResponse & {
      success: boolean
      checkin_id?: number
      result: Record<string, unknown>
      text?: string
    }
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
