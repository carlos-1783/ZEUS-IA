import { API_BASE_URL } from '@/config'
import tokenService from './tokenService'

type Payload = Record<string, unknown>

const buildHeaders = () => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = tokenService.getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function formatApiError(data: unknown, fallback: string): string {
  const payload = data as { detail?: unknown; message?: unknown }
  const detail = payload?.detail ?? payload?.message
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const row = item as { msg?: string; message?: string }
          return row.msg || row.message || JSON.stringify(item)
        }
        return String(item)
      })
      .join('; ')
  }
  if (detail && typeof detail === 'object') {
    const row = detail as { msg?: string; message?: string }
    return row.msg || row.message || JSON.stringify(detail)
  }
  return fallback
}

async function postScan<T = Record<string, unknown>>(path: string, body: Payload): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/scan${path}`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(formatApiError(data, 'Error en escaneo'))
  }
  return data as T
}

export type ScanIngestBody = {
  scan_type: 'QR_SCAN' | 'NFC_SCAN' | 'MRZ_SCAN' | 'qr' | 'nfc' | 'mrz' | 'dni'
  payload?: string
  payload_hex?: string
  image_base64?: string
  company_id?: number
  email?: string
  phone?: string
  employee_id?: string
  checkin_type?: string
  force_execute?: boolean
}

export const scanFlowApi = {
  /** Pipeline unificado v2 — producción */
  ingest: (body: ScanIngestBody) => postScan('/ingest', body),

  scanQr: (data: string, companyId?: number, forceExecute = false) =>
    scanFlowApi.ingest({
      scan_type: 'QR_SCAN',
      payload: data,
      company_id: companyId,
      force_execute: forceExecute,
    }),

  scanNfc: (opts: {
    text?: string
    payload_hex?: string
    company_id?: number
    employee_id?: string
    checkin_type?: string
  }) =>
    scanFlowApi.ingest({
      scan_type: 'NFC_SCAN',
      payload: opts.text,
      payload_hex: opts.payload_hex,
      company_id: opts.company_id,
      employee_id: opts.employee_id,
      checkin_type: opts.checkin_type,
    }),

  scanDni: (mrz: string, opts?: { company_id?: number; email?: string; phone?: string }) =>
    scanFlowApi.ingest({
      scan_type: 'MRZ_SCAN',
      payload: mrz,
      company_id: opts?.company_id,
      email: opts?.email,
      phone: opts?.phone,
    }),

  scanDniImage: (imageBase64: string, opts?: { company_id?: number; email?: string; phone?: string }) =>
    scanFlowApi.ingest({
      scan_type: 'MRZ_SCAN',
      image_base64: imageBase64,
      company_id: opts?.company_id,
      email: opts?.email,
      phone: opts?.phone,
    }),
}
