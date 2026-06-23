<template>
  <div class="afrodita-ops">
    <header v-if="truthStatus" class="ops-header">
      <ThalosExecutionBadge
        :global-mode="truthStatus.execution_mode"
        :real-execution="truthStatus.writes_enabled && truthStatus.db_connected"
      />
      <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
    </header>

    <!-- INVENTARIO -->
    <section class="card">
      <h3>📦 Inventario</h3>

      <button @click="() => loadInventory()" :disabled="loading.inventory">
        {{ loading.inventory ? 'Cargando...' : 'Refrescar' }}
      </button>

      <table v-if="inventory.length">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Stock (ERP)</th>
            <th>Stock (TPV)</th>
            <th>Fuente</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in inventory" :key="item.id">
            <td>
              {{ item.name }}
              <span v-if="item.low_stock" class="low-stock">Low</span>
            </td>
            <td>{{ formatStock(item.erp_stock) }}</td>
            <td>{{ formatStock(item.tpv_stock) }}</td>
            <td>{{ item.source }}</td>
          </tr>
        </tbody>
      </table>

      <p v-else-if="inventoryLoaded">No hay datos</p>
    </section>

    <!-- MOVIMIENTOS -->
    <section class="card">
      <h3>🔄 Movimientos</h3>

      <button @click="loadMovements" :disabled="loading.movements">
        {{ loading.movements ? 'Cargando...' : 'Refrescar' }}
      </button>

      <ul v-if="movements.length">
        <li v-for="m in movements" :key="m.id">
          {{ m.product_name }} — {{ m.type }} — {{ m.quantity }}
        </li>
      </ul>

      <p v-else-if="movementsLoaded">No hay movimientos</p>
    </section>

    <!-- ALMACÉN -->
    <section class="card">
      <h3>🏭 Almacén</h3>
      <p>No implementado aún</p>
    </section>

    <!-- RUTAS -->
    <section class="card">
      <h3>🚚 Rutas</h3>

      <button @click="simulateRoute" :disabled="loading.routes">
        {{ loading.routes ? 'Calculando...' : 'Simular ruta' }}
      </button>

      <pre v-if="routeResult">{{ routeResult }}</pre>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchAfroditaStatus, type AfroditaTruthStatus } from '@/api/afrodita_workspace_api'
import {
  fetchAfroditaOpsInventory,
  fetchAfroditaOpsMovements,
  fetchAfroditaOpsStatus,
  simulateAfroditaRoute,
  type AfroditaOpsStatusResponse,
  type InventoryMovementItem,
  type MergedProductItem,
} from '@/api/afrodita_ops_api'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

interface InventoryRow {
  id: string
  name: string
  erp_stock: number | null
  tpv_stock: number | null
  source: string
  low_stock: boolean
}

interface MovementRow {
  id: number
  product_name: string
  type: string
  quantity: number
}

const loading = reactive({ inventory: false, movements: false, routes: false })
const error = ref('')
const statusNote = ref('')
const truthStatus = ref<AfroditaTruthStatus | null>(null)
const globalStatus = ref<AfroditaOpsStatusResponse | null>(null)
const rawProducts = ref<MergedProductItem[]>([])
const rawMovements = ref<InventoryMovementItem[]>([])
const inventoryLoaded = ref(false)
const movementsLoaded = ref(false)
const routeResult = ref<string | null>(null)

const inventory = computed<InventoryRow[]>(() =>
  rawProducts.value.map((p) => ({
    id: p.id,
    name: p.name,
    erp_stock: p.erp_quantity_on_hand,
    tpv_stock: p.tpv_stock,
    source: p.source,
    low_stock: p.low_stock,
  }))
)

const movements = computed<MovementRow[]>(() =>
  rawMovements.value.map((m) => ({
    id: m.id,
    product_name: m.product_name,
    type: m.movement_type,
    quantity: m.quantity,
  }))
)

const formatStock = (v: number | null | undefined) => (v == null ? '-' : String(v))

onMounted(async () => {
  try {
    truthStatus.value = await fetchAfroditaStatus()
    globalStatus.value = await fetchAfroditaOpsStatus()
    statusNote.value = globalStatus.value.AFRODITA_OPS_READ_ONLY
      ? 'Modo lectura: `/api/v1/afrodita/ops/v1/inventory` consolida TPV + ERP (prioridad ERP).'
      : 'OPS activo.'
    await loadInventory(true)
  } catch {
    /* optional */
  }
})

const loadInventory = async (silent = false) => {
  if (!silent) error.value = ''
  loading.inventory = true
  try {
    const out = await fetchAfroditaOpsInventory()
    rawProducts.value = out.items || []
    inventoryLoaded.value = true
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.inventory = false
  }
}

const loadMovements = async () => {
  error.value = ''
  loading.movements = true
  try {
    const out = await fetchAfroditaOpsMovements()
    rawMovements.value = out.movements || []
    movementsLoaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.movements = false
  }
}

const simulateRoute = async () => {
  error.value = ''
  loading.routes = true
  routeResult.value = null
  try {
    const out = await simulateAfroditaRoute([], 'HQ')
    routeResult.value = JSON.stringify(out.result ?? out, null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.routes = false
  }
}
</script>

<style scoped>
.afrodita-ops {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 24px;
}

.ops-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-note {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.card {
  padding: 16px;
  border: 1px solid rgba(16, 185, 129, 0.35);
  border-radius: 10px;
  background: #fff;
}

.card h3 {
  margin: 0 0 12px;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.real {
  background: #dcfce7;
  color: #15803d;
}
.badge.partial {
  background: #fef3c7;
  color: #b45309;
}
.badge.simulated {
  background: #f1f5f9;
  color: #64748b;
}
.badge.none {
  background: #fee2e2;
  color: #b91c1c;
}

.card button {
  border: none;
  border-radius: 8px;
  background: #059669;
  color: #fff;
  padding: 8px 12px;
  cursor: pointer;
  margin-bottom: 10px;
}

.card button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

table {
  width: 100%;
  margin-top: 10px;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 6px;
  text-align: left;
}

th {
  color: #64748b;
  font-weight: 600;
}

.low-stock {
  margin-left: 6px;
  font-size: 10px;
  color: #b45309;
  font-weight: 700;
}

ul {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 13px;
}

pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
  margin-top: 10px;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}
</style>
