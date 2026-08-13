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
  verified_real?: boolean
  safe_lock?: {
    lock_id: string
    warning_count: number
    verified_real: boolean
    warnings: Array<{ code: string; message: string; module: string }>
  }
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
  // Migrado de /api/v1/zeus/status a /api/v1/zeus-core/status (Bloque 3,
  // limpieza de simulación): el endpoint real se movió al orquestador
  // zeus_core_v2.py al eliminar app/api/v1/endpoints/zeus_core.py.
  return api.get('/api/v1/zeus-core/status') as Promise<ZeusExecutionStatus>
}

export function moduleStatusLabel(status?: ZeusModuleStatus | string): string {
  if (!status) return 'UNKNOWN'
  if (status === 'REAL' || status === 'REAL_WITH_OUTPUT') return 'REAL'
  if (status === 'EMPTY_REAL') return 'CONNECTED'
  if (status === 'PARTIAL_REAL') return 'PARTIAL'
  if (status === 'ERROR') return 'SYSTEM ERROR'
  if (status === 'SIMULATED') return 'SIMULATED'
  return 'UNKNOWN'
}
