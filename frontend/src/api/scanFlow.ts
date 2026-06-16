import { API_BASE_URL } from '@/config'
import tokenService from './tokenService'

type Payload = Record<string, unknown>

const buildHeaders = () => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = tokenService.getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function postScan<T = Record<string, unknown>>(path: string, body: Payload): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/scan${path}`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) {
    const detail = data?.detail || data?.message || 'Error en escaneo'
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data as T
}

export const scanFlowApi = {
  scanQr: (data: string, companyId?: number, forceExecute = false) =>
    postScan('/qr', { data, company_id: companyId, force_execute: forceExecute }),

  scanNfc: (opts: {
    text?: string
    payload_hex?: string
    company_id?: number
    employee_id?: string
    checkin_type?: string
  }) => postScan('/nfc', opts),

  scanDni: (mrz: string, opts?: { company_id?: number; email?: string; phone?: string }) =>
    postScan('/dni', { mrz, ...opts }),
}
