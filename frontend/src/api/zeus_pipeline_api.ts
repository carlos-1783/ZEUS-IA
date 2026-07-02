import api from '@/services/api'

export interface ZeusPipelineResult {
  event_type?: string
  analysis?: {
    risk_score?: number
    compliance?: boolean
    recommendations?: string[]
    agent_source?: string
  }
  financial?: {
    invoice_required?: boolean
    estimated_value?: number
    agent_source?: string
  }
  thalos?: {
    monitored?: boolean
    severity?: string
    agent_source?: string
  }
  automation_triggered?: string[]
  real_execution?: boolean
}

export async function fetchZeusDocumentPipelineStatus() {
  return api.get('/api/v1/zeus/document-pipeline/status') as Promise<
    Record<string, unknown> & { success: boolean; active?: boolean; agents?: string[] }
  >
}
