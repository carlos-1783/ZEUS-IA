import { API_BASE_URL } from '@/config'
import tokenService from './tokenService'

type Payload = Record<string, any>

const buildHeaders = () => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = tokenService.getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

const post = async (path: string, body: Payload) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok || data?.success === false) {
    const detail = data?.detail || data?.error || 'Error ejecutando herramienta'
    throw new Error(detail)
  }
  return data.result ?? data
}

export const workspaceTools = {
  runPerseoImageAnalyzer: (payload: Payload) =>
    post('/workspaces/perseo/image-analyzer', payload),
  runPerseoVideoEnhancer: (payload: Payload) =>
    post('/workspaces/perseo/video-enhancer', payload),
  runPerseoSeoAudit: (payload: Payload) =>
    post('/workspaces/perseo/seo-audit', payload),
  runPerseoAdsBuilder: (payload: Payload) =>
    post('/workspaces/perseo/ads-builder', payload),
  runRafaelQrReader: (payload: Payload) =>
    post('/workspaces/rafael/qr-reader', payload),
  runRafaelNfcScanner: (payload: Payload) =>
    post('/workspaces/rafael/nfc-scanner', payload),
  runRafaelDniParser: (payload: Payload) =>
    post('/workspaces/rafael/dni-ocr', payload),
  runRafaelForms: (payload: Payload) =>
    post('/workspaces/rafael/forms', payload),
  runJusticiaSigner: (payload: Payload) =>
    post('/workspaces/justicia/pdf-signer', payload),
  runJusticiaContract: (payload: Payload) =>
    post('/workspaces/justicia/contract', payload),
  runJusticiaGdpr: (payload: Payload) =>
    post('/workspaces/justicia/gdpr-audit', payload),
  runThalosLogMonitor: (payload: Payload) =>
    post('/workspaces/thalos/log-monitor', payload),
  runThalosThreatDetector: (payload: Payload) =>
    post('/workspaces/thalos/threat-detector', payload),
  runThalosCredentialRevoker: (payload: Payload) =>
    post('/workspaces/thalos/credential-revoker', payload),
  runAfroditaFaceCheckIn: (payload: Payload) =>
    post('/workspaces/afrodita/face-check-in', payload),
  runAfroditaQrCheckIn: (payload: Payload) =>
    post('/workspaces/afrodita/qr-check-in', payload),
  runAfroditaEmployeeManager: (payload: Payload) =>
    post('/workspaces/afrodita/employee-manager', payload),
  runAfroditaContract: (payload: Payload) =>
    post('/workspaces/afrodita/contract', payload),
}

export type WorkspaceToolResponse = Awaited<
  ReturnType<(typeof workspaceTools)[keyof typeof workspaceTools]>
>


