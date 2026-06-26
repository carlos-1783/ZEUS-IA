<template>
  <div class="afrodita-ops">
    <header v-if="truthStatus" class="ops-header">
      <ThalosExecutionBadge
        :global-mode="truthStatus.execution_mode"
        :real-execution="truthStatus.execution_mode === 'REAL'"
      />
      <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
    </header>

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

    <section class="card">
      <h3>🔄 Movimientos</h3>
      <div v-if="canWrite" class="movement-form">
        <select v-model.number="movementForm.product_id">
          <option :value="0" disabled>Producto ERP</option>
          <option v-for="p in writableProducts" :key="p.product_id" :value="p.product_id">
            {{ p.name }} ({{ p.id }})
          </option>
        </select>
        <select v-model="movementForm.movement_type">
          <option value="adjustment">Ajuste</option>
          <option value="purchase">Entrada</option>
          <option value="sale">Salida</option>
          <option value="return">Devolución</option>
        </select>
        <input v-model.number="movementForm.quantity" type="number" step="1" placeholder="Cantidad (+/-)" />
        <button :disabled="loading.createMovement" @click="runCreateMovement">
          {{ loading.createMovement ? 'Guardando…' : 'Registrar movimiento' }}
        </button>
      </div>
      <p v-else class="hint">Escritura OPS requiere modo REAL global.</p>
      <button @click="loadMovements" :disabled="loading.movements">
        {{ loading.movements ? 'Cargando...' : 'Refrescar lista' }}
      </button>
      <ul v-if="movements.length">
        <li v-for="m in movements" :key="m.id">
          {{ m.product_name }} — {{ m.type }} — {{ m.quantity }}
        </li>
      </ul>
      <p v-else-if="movementsLoaded">No hay movimientos</p>
    </section>

    <section class="card">
      <h3>🏭 Almacén</h3>
      <button @click="loadWarehouse" :disabled="loading.warehouse">
        {{ loading.warehouse ? 'Cargando...' : 'Refrescar almacén' }}
      </button>
      <div v-if="warehouse">
        <p><strong>{{ warehouse.total_skus }}</strong> SKUs · <strong>{{ warehouse.total_units }}</strong> unidades</p>
        <p v-if="warehouse.low_stock_count">⚠️ {{ warehouse.low_stock_count }} en stock bajo</p>
        <ul v-if="warehouse.low_stock_items?.length">
          <li v-for="item in warehouse.low_stock_items" :key="item.id">{{ item.name }} ({{ item.stock }})</li>
        </ul>
      </div>
    </section>

    <section class="card">
      <h3>🚚 Rutas</h3>
      <div v-if="canWrite" class="route-form">
        <input v-model="routeForm.origin" placeholder="Origen" />
        <input v-model="routeForm.destination" placeholder="Destino" />
        <button :disabled="loading.routes" @click="runCreateRoute">
          {{ loading.routes ? 'Guardando…' : 'Crear y persistir ruta' }}
        </button>
      </div>
      <ul v-if="routes.length" class="route-list">
        <li v-for="r in routes" :key="r.id">
          {{ r.origin }} → {{ r.destination }} · {{ r.distance }} km
        </li>
      </ul>
      <pre v-if="routeResult">{{ routeResult }}</pre>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { executionModeLabel, fetchAfroditaStatus, type AfroditaTruthStatus } from '@/api/afrodita_workspace_api'
import {
  createAfroditaMovement,
  createAfroditaRoute,
  fetchAfroditaOpsInventory,
  fetchAfroditaOpsMovements,
  fetchAfroditaOpsRoutes,
  fetchAfroditaWarehouse,
  type InventoryMovementItem,
  type MergedProductItem,
  type OpsRouteItem,
  type WarehouseSummary,
} from '@/api/afrodita_ops_api'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

interface InventoryRow {
  id: string
  product_id?: number
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

const loading = reactive({
  inventory: false,
  movements: false,
  createMovement: false,
  routes: false,
  warehouse: false,
})
const error = ref('')
const statusNote = ref('')
const truthStatus = ref<AfroditaTruthStatus | null>(null)
const rawProducts = ref<MergedProductItem[]>([])
const rawMovements = ref<InventoryMovementItem[]>([])
const routes = ref<OpsRouteItem[]>([])
const warehouse = ref<WarehouseSummary | null>(null)
const inventoryLoaded = ref(false)
const movementsLoaded = ref(false)
const routeResult = ref<string | null>(null)

const movementForm = reactive({
  product_id: 0,
  movement_type: 'adjustment',
  quantity: 1,
})
const routeForm = reactive({
  origin: 'HQ',
  destination: 'Cliente',
})

const canWrite = computed(() => truthStatus.value?.execution_mode === 'REAL')

const inventory = computed<InventoryRow[]>(() =>
  rawProducts.value.map((p) => ({
    id: p.id,
    product_id: p.product_id,
    name: p.name,
    erp_stock: p.erp_quantity_on_hand,
    tpv_stock: p.tpv_stock,
    source: p.source,
    low_stock: p.low_stock,
  }))
)

const writableProducts = computed(() =>
  inventory.value.filter((p) => typeof p.product_id === 'number' && p.product_id > 0)
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
    const mode = truthStatus.value.execution_mode
    if (mode === 'ERROR') {
      statusNote.value = 'SYSTEM ERROR — base de datos no disponible.'
    } else if (mode === 'REAL') {
      statusNote.value = 'OPS REAL — inventario, movimientos y rutas persisten en BD.'
    } else {
      statusNote.value = `${executionModeLabel(mode)} — escritura global deshabilitada.`
    }
    await Promise.all([loadInventory(true), loadMovements(true), loadRoutes(true), loadWarehouse(true)])
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
    const first = writableProducts.value[0]
    if (first?.product_id) movementForm.product_id = first.product_id
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.inventory = false
  }
}

const loadMovements = async (silent = false) => {
  if (!silent) error.value = ''
  loading.movements = true
  try {
    const out = await fetchAfroditaOpsMovements()
    rawMovements.value = out.movements || []
    movementsLoaded.value = true
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.movements = false
  }
}

const loadRoutes = async (silent = false) => {
  if (!silent) error.value = ''
  loading.routes = true
  try {
    const out = await fetchAfroditaOpsRoutes()
    routes.value = out.routes || []
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.routes = false
  }
}

const loadWarehouse = async (silent = false) => {
  if (!silent) error.value = ''
  loading.warehouse = true
  try {
    warehouse.value = await fetchAfroditaWarehouse()
  } catch (e) {
    if (!silent) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.warehouse = false
  }
}

const runCreateMovement = async () => {
  if (!movementForm.product_id) {
    error.value = 'Seleccione un producto ERP'
    return
  }
  error.value = ''
  loading.createMovement = true
  try {
    const out = await createAfroditaMovement({
      product_id: movementForm.product_id,
      movement_type: movementForm.movement_type,
      quantity: movementForm.quantity,
      reference: 'afrodita_ops_ui',
    })
    if (!out.success) {
      error.value = out.message || 'Movimiento no persistido'
      return
    }
    await Promise.all([loadInventory(true), loadMovements(true), loadWarehouse(true)])
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.createMovement = false
  }
}

const runCreateRoute = async () => {
  error.value = ''
  routeResult.value = null
  loading.routes = true
  try {
    const out = await createAfroditaRoute({
      origin: routeForm.origin,
      destination: routeForm.destination,
      deliveries: [{ stop: 1 }],
    })
    if (!out.success) {
      error.value = 'Ruta no persistida'
      return
    }
    routeResult.value = out.message || `Ruta #${out.route.id} — ${out.route.distance} km`
    await loadRoutes(true)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    routeResult.value = error.value
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
}

.movement-form,
.route-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.movement-form input,
.movement-form select,
.route-form input {
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
}

.hint {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 8px;
}

.card button {
  border: none;
  border-radius: 8px;
  background: #059669;
  color: #fff;
  padding: 8px 12px;
  cursor: pointer;
  margin-bottom: 10px;
  margin-right: 8px;
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

ul,
.route-list {
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
