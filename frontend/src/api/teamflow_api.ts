import api from '@/services/api'

export interface TeamFlowItem {
  id: string
  db_id?: number
  owner_agent: string
  source_agent?: string | null
  target_agent?: string | null
  workflow_id?: string | null
  item_type: string
  title: string
  status: string
  content: Record<string, unknown>
  execution_id?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export async function fetchTeamFlowItems(params?: {
  agent?: string
  owner_agent?: string
  status?: string
  limit?: number
}) {
  const qs = new URLSearchParams()
  if (params?.agent) qs.set('agent', params.agent)
  if (params?.owner_agent) qs.set('owner_agent', params.owner_agent)
  if (params?.status) qs.set('status', params.status)
  qs.set('limit', String(params?.limit ?? 50))
  return api.get(`/api/v1/teamflow/list?${qs}`) as Promise<{
    success: boolean
    items: TeamFlowItem[]
    count: number
  }>
}
