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
  return data
}

export const workspaceTools = {
  // PERSEO — /api/v1/tools/* (heurístico, sin persistencia BD)
  runPerseoImageAnalyzer: (payload: Payload) =>
    post('/tools/analyze-image', payload),
  runPerseoVideoEnhancer: (payload: Payload) =>
    post('/tools/improve-video', payload),
  runPerseoSeoAudit: (payload: Payload) =>
    post('/tools/seo-audit', payload),
  runPerseoAdsBuilder: (payload: Payload) =>
    post('/tools/generate-ads-plan', payload),

  // RAFAEL — scan real vía scanFlowApi; forms vía workspace
  runRafaelQrReader: (payload: Payload) =>
    post('/workspaces/rafael/qr-reader', payload),
  runRafaelNfcScanner: (payload: Payload) =>
    post('/workspaces/rafael/nfc-scanner', payload),
  runRafaelDniParser: (payload: Payload) =>
    post('/workspaces/rafael/dni-ocr', payload),
  runRafaelForms: (payload: Payload) =>
    post('/workspaces/rafael/forms', payload),

  // JUSTICIA — stubs documentales (usar /api/v1/justicia/v1 para auditoría real)
  runJusticiaSigner: (payload: Payload) =>
    post('/workspaces/justicia/pdf-signer', payload),
  runJusticiaContract: (payload: Payload) =>
    post('/workspaces/justicia/contract', payload),
  runJusticiaGdpr: (payload: Payload) =>
    post('/workspaces/justicia/gdpr-audit', payload),

  // THALOS legacy — preferir thalos_workspace_api (/api/v1/thalos/v1/*)
  runThalosLogMonitor: (payload: Payload) =>
    post('/workspaces/thalos/log-monitor', payload),
  runThalosThreatDetector: (payload: Payload) =>
    post('/workspaces/thalos/threat-detector', payload),
  runThalosCredentialRevoker: (payload: Payload) =>
    post('/workspaces/thalos/credential-revoker', payload),

  // LEGACY REMOVED — AFRODITA usa afrodita_workspace_api.ts:
  //   /api/v1/afrodita/rrhh/v1/*  /api/v1/afrodita/ops/v1/*
  //   /workspaces/afrodita/* devuelve 403 (workspace aislado)
}

export type WorkspaceToolResponse = Awaited<
  ReturnType<(typeof workspaceTools)[keyof typeof workspaceTools]>
>
