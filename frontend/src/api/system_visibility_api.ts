import api from '@/services/api'

export type AgentStatusLabel = 'REAL' | 'PARTIAL' | 'FAKE' | 'DISCONNECTED'
export type StandardExecutionMode = 'SIMULATED' | 'READ_ONLY' | 'REAL'

export interface AgentVisibilityRow {
  name: string
  status: AgentStatusLabel
  execution_mode: StandardExecutionMode
  execution_ready: boolean
  api_prefix: string
  notes: string
}

export interface SystemExecutionStatusResponse {
  phase: string
  system_id: string
  system_state: string
  visibility: string
  fake_components: string
  ready_for_flags_activation: boolean
  zeus_core_orchestration_active?: boolean
  timestamp: string
  flags: Record<string, boolean>
  agents: AgentVisibilityRow[]
  summary: {
    execution_ready_count: number
    partial_count: number
    fake_count: number
  }
}

export async function fetchSystemExecutionStatus() {
  return api.get('/api/v1/system/execution-status') as Promise<SystemExecutionStatusResponse>
}

export async function fetchSystemFixPass() {
  return api.get('/api/v1/system/fix-pass') as Promise<Record<string, unknown>>
}
