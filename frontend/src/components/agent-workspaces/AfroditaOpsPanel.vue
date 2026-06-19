<template>
  <section class="ops-panel">
    <header>
      <div class="header-row">
        <div>
          <h4>📦 Operaciones (OPS)</h4>
          <p>Inventario unificado TPV + ERP, movimientos y rutas.</p>
        </div>
        <ThalosExecutionBadge
          v-if="globalStatus"
          :global-mode="globalStatus.system_default_mode"
          :control="globalStatus.afrodita_ops_control"
          :data-origin="globalStatus.data_origin"
          :real-execution="globalStatus.real_execution"
        />
      </div>
      <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
    </header>

    <div class="ops-grid">
      <div class="ops-card highlight">
        <div class="card-title-row">
          <h5>Inventario</h5>
          <ThalosExecutionBadge module-badge="REAL" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Vista merged — prioridad ERP (`quantity_on_hand`) sobre TPV (`stock`).</p>
        <button :disabled="loading.inventory" @click="loadInventory">
          {{ loading.inventory ? 'Cargando…' : 'Cargar inventario' }}
        </button>
        <ul v-if="products.length" class="data-list">
          <li v-for="p in products.slice(0, 12)" :key="p.id">
            <strong>{{ p.name }}</strong>
            <span>{{ p.id }} · stock {{ p.stock ?? '—' }} · {{ p.source }}</span>
            <span v-if="p.low_stock" class="warn">Low stock</span>
          </li>
        </ul>
        <p v-else-if="inventoryLoaded" class="hint">Sin productos en TPV ni ERP.</p>
        <ThalosExecutionBadge v-if="lastInvControl" :control="lastInvControl" :show-global="false" />
      </div>

      <div class="ops-card">
        <div class="card-title-row">
          <h5>Movimientos</h5>
          <ThalosExecutionBadge module-badge="PARCIAL" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Lectura de `inventory_movements` (ERP).</p>
        <button :disabled="loading.movements" @click="loadMovements">
          {{ loading.movements ? 'Cargando…' : 'Ver movimientos' }}
        </button>
        <ul v-if="movements.length" class="data-list">
          <li v-for="m in movements.slice(0, 8)" :key="m.id">
            {{ m.movement_type }} · {{ m.product_name }} · {{ m.quantity }}
          </li>
        </ul>
        <ThalosExecutionBadge v-if="lastMovControl" :control="lastMovControl" :show-global="false" />
      </div>

      <div class="ops-card stub">
        <div class="card-title-row">
          <h5>Almacén</h5>
          <ThalosExecutionBadge module-badge="NONE" :inline="true" :show-global="false" />
        </div>
        <p class="hint">Bins/ubicaciones — fase 3 (no implementado).</p>
        <button :disabled="loading.warehouse" @click="loadWarehouseStub">
          {{ loading.warehouse ? '…' : 'Estado módulo' }}
        </button>
        <p v-if="warehouseNote" class="tool-text">{{ warehouseNote }}</p>
      </div>

      <div class="ops-card legacy">
        <div class="card-title-row">
          <h5>Rutas</h5>
          <ThalosExecutionBadge module-badge="SIMULADO" :inline="true" :show-global="false" />
        </div>
        <p class="hint">`optimize_route` — stub marcado SIMULADO.</p>
        <button :disabled="loading.routes" @click="runRouteSim">
          {{ loading.routes ? 'Simulando…' : 'Simular ruta' }}
        </button>
        <p v-if="routeResult" class="tool-text">{{ routeResult }}</p>
        <ThalosExecutionBadge v-if="lastRouteControl" :control="lastRouteControl" :show-global="false" />
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  extractAfroditaOpsControl,
  fetchAfroditaOpsInventory,
  fetchAfroditaOpsMovements,
  fetchAfroditaOpsStatus,
  fetchAfroditaOpsWarehouseStub,
  simulateAfroditaRoute,
  type AfroditaOpsControlMetadata,
  type AfroditaOpsStatusResponse,
  type InventoryMovementItem,
  type MergedProductItem,
} from '@/api/afrodita_ops_api'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

const loading = reactive({ inventory: false, movements: false, warehouse: false, routes: false })
const error = ref('')
const statusNote = ref('')
const globalStatus = ref<AfroditaOpsStatusResponse | null>(null)
const products = ref<MergedProductItem[]>([])
const movements = ref<InventoryMovementItem[]>([])
const inventoryLoaded = ref(false)
const warehouseNote = ref<string | null>(null)
const routeResult = ref<string | null>(null)

const lastInvControl = ref<AfroditaOpsControlMetadata | null>(null)
const lastMovControl = ref<AfroditaOpsControlMetadata | null>(null)
const lastRouteControl = ref<AfroditaOpsControlMetadata | null>(null)

const pickControl = (out: unknown) => extractAfroditaOpsControl(out)

onMounted(async () => {
  try {
    globalStatus.value = await fetchAfroditaOpsStatus()
    statusNote.value = globalStatus.value.AFRODITA_OPS_READ_ONLY
      ? 'Modo lectura OPS: inventario consolidado visible; escritura de stock en fase 3.'
      : 'OPS activo — revisar flags en Railway.'
    await loadInventory(true)
  } catch {
    /* optional */
  }
})

const loadInventory = async (silent = false) => {
  if (!silent) error.value = ''
  loading.inventory = true
  lastInvControl.value = null
  try {
    const out = await fetchAfroditaOpsInventory()
    lastInvControl.value = pickControl(out)
    products.value = out.items || []
    inventoryLoaded.value = true
  } catch (err) {
    if (!silent) error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.inventory = false
  }
}

const loadMovements = async () => {
  error.value = ''
  loading.movements = true
  lastMovControl.value = null
  try {
    const out = await fetchAfroditaOpsMovements()
    lastMovControl.value = pickControl(out)
    movements.value = out.movements || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.movements = false
  }
}

const loadWarehouseStub = async () => {
  loading.warehouse = true
  warehouseNote.value = null
  try {
    const out = await fetchAfroditaOpsWarehouseStub()
    warehouseNote.value = String(out.label || out.note || 'No implementado')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.warehouse = false
  }
}

const runRouteSim = async () => {
  error.value = ''
  loading.routes = true
  routeResult.value = null
  lastRouteControl.value = null
  try {
    const out = await simulateAfroditaRoute(
      [{ id: 'D1', address: 'Calle Mayor 1' }, { id: 'D2', address: 'Av. Logística 5' }],
      'depot'
    )
    lastRouteControl.value = pickControl(out)
    const r = out.result || {}
    routeResult.value = String(r.note || r.status || 'Ruta simulada (stub)')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.routes = false
  }
}
</script>

<style scoped>
.ops-panel {
  margin-top: 24px;
  padding: 22px;
  border-radius: 16px;
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: #ecfdf5;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.ops-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.ops-card {
  background: white;
  border: 1px solid rgba(16, 185, 129, 0.35);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ops-card.highlight {
  border-color: #059669;
}
.ops-card.stub,
.ops-card.legacy {
  opacity: 0.95;
}
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}
.status-note {
  margin-top: 8px;
  font-size: 12px;
  color: #475569;
}
.ops-card button {
  border: none;
  border-radius: 8px;
  background: #059669;
  color: #fff;
  padding: 8px 10px;
  cursor: pointer;
}
.data-list {
  margin: 0;
  padding-left: 16px;
  font-size: 12px;
}
.data-list li {
  margin-bottom: 4px;
}
.data-list span {
  display: block;
  color: #64748b;
}
.warn {
  color: #b45309;
  font-weight: 600;
}
.tool-text {
  margin: 0;
  padding: 8px;
  border-radius: 8px;
  background: #f0fdf4;
  font-size: 12px;
}
.tool-error {
  margin-top: 10px;
  color: #b91c1c;
}
</style>
