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

export async function simulateAfroditaRoute(deliveries: Record<string, unknown>[], startLocation = 'depot') {
  return api.post('/api/v1/afrodita/ops/v1/routes/simulate', {
    deliveries,
    start_location: startLocation,
  }) as Promise<AfroditaControlResponse & { success: boolean; result?: Record<string, unknown> }>
}
