import api from '@/services/api'

export type AfroditaOpsExecutionMode = 'SIMULATION' | 'READ_ONLY' | 'REAL_ACTIVE'
export type AfroditaOpsDataOrigin = 'backend' | 'user_input' | 'mock' | 'mixed'

export interface AfroditaOpsControlMetadata {
  execution_mode: AfroditaOpsExecutionMode
  data_origin: AfroditaOpsDataOrigin
  real_execution: boolean
  module: string
  ui_badge: string
  flags: Record<string, boolean>
}

export interface AfroditaOpsControlResponse {
  execution_mode: AfroditaOpsExecutionMode
  data_origin?: AfroditaOpsDataOrigin
  real_execution: boolean
  afrodita_ops_control?: AfroditaOpsControlMetadata
}

export interface MergedProductItem {
  id: string
  name: string
  source: 'erp' | 'tpv' | 'merged'
  stock: number | null
  erp_quantity_on_hand: number | null
  tpv_stock: number | null
  low_stock: boolean
  category: string
  price: number
  ui_badge: string
}

export interface InventoryMovementItem {
  id: number
  product_id: number
  product_name: string
  product_sku: string
  movement_type: string
  quantity: number
  reference?: string
  notes?: string
  created_at?: string
}

export interface AfroditaOpsStatusResponse extends AfroditaOpsControlResponse {
  system_default_mode: AfroditaOpsExecutionMode
  afrodita_ops_control?: AfroditaOpsControlMetadata
  AFRODITA_OPS_ENABLED: boolean
  AFRODITA_OPS_READ_ONLY: boolean
  AFRODITA_USE_TPV: boolean
  AFRODITA_USE_ERP: boolean
  AFRODITA_ENABLE_STOCK_SYNC: boolean
  AFRODITA_ENABLE_ROUTE_ENGINE: boolean
  module_badges: Record<string, string>
  erp_api_path: string
  tpv_api_path: string
  inventory_precedence: string
  legacy_preserved: boolean
}

function isOpsMetadata(value: unknown): value is AfroditaOpsControlMetadata {
  if (!value || typeof value !== 'object') return false
  const v = value as AfroditaOpsControlMetadata
  return typeof v.ui_badge === 'string' && typeof v.execution_mode === 'string'
}

function isOpsResponse(value: unknown): value is AfroditaOpsControlResponse {
  if (!value || typeof value !== 'object') return false
  return typeof (value as AfroditaOpsControlResponse).real_execution === 'boolean'
}

export function extractAfroditaOpsControl(source?: unknown): AfroditaOpsControlMetadata | null {
  if (!source) return null
  if (isOpsMetadata(source)) return source
  if (!isOpsResponse(source)) return null
  const nested = source.afrodita_ops_control
  if (nested && isOpsMetadata(nested)) return nested
  return {
    execution_mode: source.execution_mode,
    data_origin: source.data_origin ?? 'backend',
    real_execution: source.real_execution,
    module: nested?.module ?? '',
    ui_badge: nested?.ui_badge ?? '',
    flags: nested?.flags ?? {},
  }
}

export async function fetchAfroditaOpsStatus() {
  return api.get('/api/v1/afrodita/ops/v1/status') as Promise<AfroditaOpsStatusResponse>
}

export async function fetchAfroditaOpsInventory() {
  return api.get('/api/v1/afrodita/ops/v1/inventory') as Promise<
    AfroditaOpsControlResponse & {
      success: boolean
      items: MergedProductItem[]
      count: number
      erp_count: number
      tpv_count: number
      precedence: string
      read_only: boolean
    }
  >
}

export async function fetchAfroditaOpsMovements(limit = 50) {
  return api.get(`/api/v1/afrodita/ops/v1/movements?limit=${limit}`) as Promise<
    AfroditaOpsControlResponse & {
      success: boolean
      movements: InventoryMovementItem[]
      count: number
    }
  >
}

export async function simulateAfroditaRoute(deliveries: Record<string, unknown>[], startLocation = 'depot') {
  return api.post('/api/v1/afrodita/ops/v1/routes/simulate', {
    deliveries,
    start_location: startLocation,
  }) as Promise<AfroditaOpsControlResponse & { success: boolean; result: Record<string, unknown> }>
}

export async function fetchAfroditaOpsWarehouseStub() {
  return api.get('/api/v1/afrodita/ops/v1/warehouse') as Promise<
    AfroditaOpsControlResponse & { success: boolean; implemented: boolean; label: string }
  >
}
