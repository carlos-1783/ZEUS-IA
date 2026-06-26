import api from '@/services/api'

export type ZeusModuleStatus =
  | 'REAL'
  | 'PARTIAL_REAL'
  | 'EMPTY_REAL'
  | 'REAL_WITH_OUTPUT'
  | 'SIMULATED'
  | 'ERROR'

export interface ZeusModuleState {
  status: ZeusModuleStatus
  read: boolean
  write: boolean
  playbook_count?: number
}

export interface ZeusExecutionStatus {
  status: string
  execution_mode: 'REAL' | 'SIMULATED' | 'ERROR'
  writes_enabled: boolean
  db_status: { connected: boolean; flags_loaded: boolean }
  connected_modules: string[]
  modules: {
    rrhh: ZeusModuleState
    ops: ZeusModuleState
    workspace: ZeusModuleState
  }
  simulation_layers_present: boolean
  flag_consistency: string
  pipeline?: Record<string, unknown>
  timestamp?: string
}

export async function fetchZeusExecutionStatus() {
  return api.get('/api/v1/zeus/status') as Promise<ZeusExecutionStatus>
}

export function moduleStatusLabel(status?: ZeusModuleStatus | string): string {
  if (!status) return 'NO EXECUTION'
  if (status === 'REAL' || status === 'REAL_WITH_OUTPUT') return 'REAL'
  if (status === 'EMPTY_REAL') return 'CONNECTED'
  if (status === 'PARTIAL_REAL') return 'PARTIAL'
  if (status === 'ERROR') return 'SYSTEM ERROR'
  return 'NO EXECUTION'
}
