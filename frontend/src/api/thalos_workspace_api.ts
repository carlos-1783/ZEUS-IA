import api from '@/services/api'

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

export async function fetchThalosWorkspaceItems(limit = 50) {
  const res = await api.get(`/api/v1/thalos/v1/workspace/items?limit=${limit}`)
  return res as { success: boolean; items: ThalosWorkspaceItem[]; count: number }
}

export async function runThalosMonitor(companyId?: number, autoExecute = false) {
  const res = await api.post('/api/v1/thalos/v1/monitor', {
    company_id: companyId ?? null,
    auto_execute: autoExecute,
  })
  return res
}

export async function fetchThalosEvents(limit = 50) {
  const res = await api.get(`/api/v1/thalos/v1/events?limit=${limit}`)
  return res as { events: Record<string, unknown>[] }
}

export async function fetchThalosStatus() {
  return api.get('/api/v1/thalos/v1/status')
}
