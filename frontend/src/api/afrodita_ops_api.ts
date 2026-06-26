import api from '@/services/api'
import type { AfroditaControlResponse, AfroditaExecutionMode } from '@/api/afrodita_workspace_api'

export type { AfroditaExecutionMode }

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
  erp_id?: number
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

export interface OpsRouteItem {
  id: number
  origin: string
  destination: string
  distance: number
  created_at?: string
  plan?: Record<string, unknown>
}

export interface WarehouseSummary {
  implemented: boolean
  total_skus: number
  low_stock_count: number
  total_units: number
  locations: Array<{
    code: string
    label: string
    sku_count: number
    units_on_hand: number
    low_stock_skus: number
  }>
  low_stock_items: Array<{ id?: string; name?: string; stock?: number | null }>
}

export async function fetchAfroditaOpsInventory() {
  return api.get('/api/v1/afrodita/ops/v1/inventory') as Promise<
    AfroditaControlResponse & {
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
    AfroditaControlResponse & {
      success: boolean
      movements: InventoryMovementItem[]
      count: number
    }
  >
}

export async function createAfroditaMovement(payload: {
  product_id: number
  movement_type: string
  quantity: number
  reference?: string
  notes?: string
}) {
  return api.post('/api/v1/afrodita/ops/v1/movements/create', payload) as Promise<
    AfroditaControlResponse & {
      success: boolean
      movement: InventoryMovementItem
      stock_after: number
      tpv_synced?: string | null
      message?: string
    }
  >
}

export async function createAfroditaRoute(payload: {
  origin: string
  destination: string
  deliveries?: Record<string, unknown>[]
}) {
  return api.post('/api/v1/afrodita/ops/v1/routes/create', payload) as Promise<
    AfroditaControlResponse & {
      success: boolean
      route: OpsRouteItem
      message?: string
    }
  >
}

export async function fetchAfroditaOpsRoutes(limit = 50) {
  return api.get(`/api/v1/afrodita/ops/v1/routes?limit=${limit}`) as Promise<
    AfroditaControlResponse & {
      success: boolean
      routes: OpsRouteItem[]
      count: number
    }
  >
}

export async function fetchAfroditaWarehouse() {
  return api.get('/api/v1/afrodita/ops/v1/warehouse') as Promise<
    AfroditaControlResponse & { success: boolean } & WarehouseSummary
  >
}
