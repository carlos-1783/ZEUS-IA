import api from '@/services/api'

export type PerseoFeatureStatus = 'REAL' | 'SIMULATED' | 'BROKEN' | 'MISSING'

export interface PerseoFeatureInfo {
  status: PerseoFeatureStatus
  endpoint?: string | null
  notes?: string
  ffmpeg_available?: boolean
  blocked_for_real_badges?: boolean
}

export interface PerseoStatusResponse {
  success: boolean
  agent: string
  execution_mode: string
  writes_enabled: boolean
  feature_status_map: Record<string, PerseoFeatureInfo>
  zeus_module: string
}

export interface PerseoVideoEditResponse {
  success: boolean
  job_id: string
  status: string
  progress: number
  poll_url?: string
  video_url?: string
  thumbnail_url?: string
  duration?: number
  error?: string
}

export async function fetchPerseoStatus() {
  return api.get('/api/v1/perseo/status') as Promise<PerseoStatusResponse>
}

export async function fetchPerseoAudit() {
  return api.get('/api/v1/perseo/audit') as Promise<Record<string, unknown>>
}

export async function submitPerseoVideoEdit(payload: {
  input_url: string
  operations?: Array<Record<string, unknown>>
  transaction_id?: string
}) {
  return api.post('/api/v1/perseo/video/edit', payload) as Promise<PerseoVideoEditResponse>
}

export async function fetchPerseoV2Status() {
  return api.get('/api/v1/perseo/v2/status') as Promise<{
    success: boolean
    version: string
    perseo_v2_enabled: boolean
    execution_mode: string
    writes_enabled: boolean
    storage: { backend: string; s3_configured: boolean; cloud_required: boolean }
    engines: Record<string, unknown>
    queue: { active: number; queued: number; failed: number }
  }>
}

export async function submitPerseoV2VideoEdit(payload: {
  input_url: string
  operations?: Array<Record<string, unknown>>
  transaction_id?: string
}) {
  return api.post('/api/v1/perseo/v2/video/edit', payload) as Promise<PerseoVideoEditResponse>
}

export async function pollPerseoV2Job(jobId: string) {
  return api.get(`/api/v1/perseo/v2/jobs/${jobId}`) as Promise<PerseoVideoEditResponse & { output?: Record<string, unknown> }>
}

export function perseoFeatureBadge(status?: PerseoFeatureStatus): string {
  if (status === 'REAL') return 'REAL'
  if (status === 'BROKEN') return 'ERROR'
  if (status === 'MISSING') return 'NO DISPONIBLE'
  return 'SIMULADO'
}
