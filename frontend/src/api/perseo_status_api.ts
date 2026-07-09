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

export async function probeBackendHealth(): Promise<{ ok: boolean; apiBase: string; detail?: string }> {
  const { API_BASE_URL } = await import('@/config')
  const base = (API_BASE_URL || '').replace(/\/api\/v1\/?$/, '')
  const url = `${base}/api/v1/health`
  try {
    const res = await fetch(url, { method: 'GET', cache: 'no-store' })
    if (!res.ok) return { ok: false, apiBase: API_BASE_URL, detail: `HTTP ${res.status}` }
    return { ok: true, apiBase: API_BASE_URL }
  } catch (err) {
    return {
      ok: false,
      apiBase: API_BASE_URL,
      detail: err instanceof Error ? err.message : 'Network Error',
    }
  }
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

export async function pollPerseoVideoJob(jobId: string) {
  return api.get(`/api/v1/perseo/video/jobs/${jobId}`) as Promise<PerseoVideoEditResponse>
}

export interface PerseoVideoGeneratePayload {
  tenant_id: string
  image_url: string
  product_info?: string
  branding?: { logo?: string; primary_color?: string }
  lead_id?: number
  campaign_id?: string
  customer_id?: number
}

export interface PerseoVideoGenerateResponse {
  success: boolean
  engine: string
  version: string
  video_url: string
  script: { hook: string; problem: string; solution: string; cta: string }
  storage: string
  crm: { crm_saved: boolean; store_video_asset: boolean; link_to_campaign: boolean }
  copy_engine?: { ai_powered?: boolean; mode?: string }
}

export async function generatePerseoVideo(payload: PerseoVideoGeneratePayload) {
  return api.post('/api/v1/perseo/video/generate', payload) as Promise<PerseoVideoGenerateResponse>
}

export async function fetchPerseoVideoEngineInfo() {
  return api.get('/api/v1/perseo/video/engine') as Promise<{
    success: boolean
    engine: string
    version: string
    configured: boolean
    execution: string
  }>
}

export interface PerseoVideoProPayload {
  tenant_id: string
  image_url: string
  product_info?: string
  branding?: { logo?: string; primary_color?: string; font_style?: string }
  platform?: string
  lead_id?: number
  campaign_id?: string
  customer_id?: number
  enable_audio?: boolean
  enable_voiceover?: boolean
}

export interface PerseoVideoProResponse {
  success: boolean
  engine: string
  version: string
  video_url: string
  preview?: string | null
  script: Record<string, string>
  ready_for_ads: boolean
  validation: Record<string, boolean>
  audio_engine?: { enabled?: boolean; voiceover?: boolean }
}

export async function generatePerseoVideoPro(payload: PerseoVideoProPayload) {
  return api.post('/api/v1/perseo/video-pro/generate', payload) as Promise<PerseoVideoProResponse>
}

export async function fetchPerseoVideoProEngineInfo() {
  return api.get('/api/v1/perseo/video-pro/engine') as Promise<{
    success: boolean
    engine: string
    version: string
    configured: boolean
    mode: string
  }>
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

export async function perseoAnalyzeImage(payload: {
  image_url: string
  goals?: string[]
  tags?: string[]
}) {
  return api.post('/api/v1/perseo/v2/ai/analyze-image', payload) as Promise<Record<string, unknown>>
}

export async function perseoRecommendVideo(payload: {
  duration_seconds?: number
  tone?: string
  platform?: string
}) {
  return api.post('/api/v1/perseo/v2/ai/recommend-video', payload) as Promise<Record<string, unknown>>
}

export async function perseoSeoAudit(payload: {
  url?: string
  keywords?: string[]
  html_snapshot?: string
}) {
  return api.post('/api/v1/perseo/v2/ai/seo-audit', payload) as Promise<Record<string, unknown>>
}

export async function perseoGenerateAds(payload: {
  product?: string
  budget?: number
  audience?: string
  objective?: string
}) {
  return api.post('/api/v1/perseo/v2/ai/generate-ads', payload) as Promise<Record<string, unknown>>
}

export async function perseoGenerateVideo(payload: {
  prompt: string
  duration_sec?: number
  transaction_id?: string
}) {
  return api.post('/api/v1/perseo/v2/ai/generate-video', payload) as Promise<PerseoVideoEditResponse>
}

export function perseoFeatureBadge(status?: PerseoFeatureStatus): string {
  if (status === 'REAL') return 'REAL'
  if (status === 'BROKEN') return 'ERROR'
  if (status === 'MISSING') return 'NO DISPONIBLE'
  return 'SIMULADO'
}
