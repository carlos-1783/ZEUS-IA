import api from '@/services/api'
import type { AfroditaControlResponse } from '@/api/afrodita_workspace_api'

export interface WorkspacePlaybookItem {
  id: number
  title: string
  content: Record<string, unknown>
  agent_source?: string
  agent_name?: string
  created_at: string | null
}

export async function fetchWorkspacePlaybooks(limit = 100, agentSource?: string) {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (agentSource) qs.set('agent_source', agentSource)
  return api.get(`/api/v1/workspace/playbooks?${qs}`) as Promise<
    AfroditaControlResponse & {
      success: boolean
      playbooks: WorkspacePlaybookItem[]
      count: number
    }
  >
}

export async function createWorkspacePlaybook(payload: {
  title: string
  content: Record<string, unknown>
  agent_source?: string
}) {
  return api.post('/api/v1/workspace/playbooks/create', payload) as Promise<
    AfroditaControlResponse & {
      success: boolean
      playbook_id: number
      title: string
      agent_source: string
      message?: string
    }
  >
}
