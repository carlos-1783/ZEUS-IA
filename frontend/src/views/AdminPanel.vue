<template>
  <div class="admin-panel">
    <!-- Overlay móvil para cerrar sidebar -->
    <div
      v-if="sidebarOpen"
      class="admin-sidebar-overlay"
      aria-hidden="true"
      @click="sidebarOpen = false"
    />

    <!-- Cabecera móvil: hamburguesa + título + volver -->
    <header class="admin-mobile-header">
      <button
        type="button"
        class="admin-mobile-menu-btn"
        aria-label="Abrir menú"
        @click="sidebarOpen = !sidebarOpen"
      >
        <span></span>
        <span></span>
        <span></span>
      </button>
      <h1 class="admin-mobile-title">⚡ Admin</h1>
      <button type="button" class="admin-mobile-back" @click="goToDashboard">
        ← Volver
      </button>
    </header>

    <!-- Sidebar -->
    <aside class="admin-sidebar" :class="{ 'open': sidebarOpen }">
      <div class="logo">
        <h1>⚡ ZEUS-IA</h1>
        <p>Panel de Administración</p>
      </div>

      <nav class="admin-nav">
        <button 
          :class="{ active: currentView === 'overview' }"
          @click="selectView('overview')"
        >
          📊 Overview
        </button>
        <button 
          :class="{ active: currentView === 'customers' }"
          @click="selectView('customers')"
        >
          👥 Clientes
        </button>
        <button 
          :class="{ active: currentView === 'revenue' }"
          @click="selectView('revenue')"
        >
          💰 Ingresos
        </button>
        <button 
          :class="{ active: currentView === 'settings' }"
          @click="selectView('settings')"
        >
          ⚙️ Configuración
        </button>
      </nav>

      <button class="btn-back" @click="goToDashboard">
        ← Volver al Dashboard
      </button>
    </aside>

    <!-- Main Content -->
    <main class="admin-content">
      <!-- Overview -->
      <section v-if="currentView === 'overview'" class="overview">
        <h2>Dashboard General</h2>
        
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon">👥</div>
            <div class="stat-value">{{ formatNumber(stats.totalCustomers) }}</div>
            <div class="stat-label">Clientes Totales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-value">€{{ formatCurrency(stats.monthlyRevenue) }}</div>
            <div class="stat-label">Ingresos Mensuales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">📈</div>
            <div class="stat-value">€{{ formatCurrency(stats.totalRevenue) }}</div>
            <div class="stat-label">Ingresos Totales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">🎯</div>
            <div class="stat-value">{{ formatNumber(stats.activeSubscriptions) }}</div>
            <div class="stat-label">Suscripciones Activas</div>
          </div>
        </div>

        <!-- Revenue Chart -->
        <div class="chart-section">
          <h3>Ingresos por Mes</h3>
          <div class="chart-container">
            <canvas ref="revenueChartCanvas"></canvas>
            <div v-if="loading && !chartReady" class="chart-loading">
              Cargando datos del gráfico...
            </div>
            <div v-if="error && !chartReady" class="chart-error">
              {{ error }}
            </div>
          </div>
        </div>
      </section>

      <!-- Customers -->
      <section v-if="currentView === 'customers'" class="customers">
        <div class="section-header">
          <h2>Clientes</h2>
          <button class="btn-refresh" @click="loadCustomers">
            🔄 Actualizar
          </button>
        </div>

        <div class="customers-table-wrapper">
          <table class="customers-table">
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Email</th>
                <th>Plan</th>
                <th>Empleados</th>
                <th>Estado</th>
                <th>Próximo pago</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="customer in customers" :key="customer.id">
                <td>{{ customer.company_name }}</td>
                <td>{{ customer.email }}</td>
                <td>
                  <span class="plan-badge" :class="customer.plan">
                    {{ getPlanName(customer.plan) }}
                  </span>
                </td>
                <td>{{ customer.employees }}</td>
                <td>
                  <span class="status-badge" :class="customer.status">
                    {{ customer.status === 'active' ? 'Activo' : 'Inactivo' }}
                  </span>
                </td>
                <td>{{ formatDate(customer.next_payment) }}</td>
                <td>
                  <button class="btn-action" @click="viewCustomer(customer)">
                    👁️ Ver
                  </button>
                  <button class="btn-action" @click="openEditCustomer(customer)">
                    ✏️ Editar
                  </button>
                  <button class="btn-action danger" @click="toggleCustomerStatus(customer)">
                    {{ customer.status === 'active' ? '⏸️' : '▶️' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="customers.length === 0" class="empty-state">
            <p>No hay clientes registrados aún</p>
          </div>
        </div>
      </section>

      <!-- Modal Ver Cliente -->
      <div v-if="viewingCustomer" class="admin-modal-overlay" @click.self="closeViewCustomer">
        <div class="admin-modal admin-modal-wide">
          <h3>Detalle del cliente</h3>
          <p class="admin-modal-email">{{ viewingCustomer.email }}</p>
          <div v-if="loadingCustomerDetail" class="admin-modal-hint">Cargando…</div>
          <div v-else class="admin-modal-form">
            <p><strong>ID:</strong> {{ customerDetail.id }}</p>
            <p><strong>Nombre:</strong> {{ customerDetail.full_name || '—' }}</p>
            <p><strong>Empresa (perfil):</strong> {{ customerDetail.company_name || '—' }}</p>
            <p><strong>Plan:</strong> {{ getPlanName(customerDetail.plan || 'none') }}</p>
            <p><strong>Empleados:</strong> {{ customerDetail.employees ?? 0 }}</p>
            <p><strong>Estado:</strong> {{ customerDetail.status === 'active' ? 'Activo' : 'Inactivo' }}</p>
            <p><strong>Teléfono:</strong> {{ customerDetail.phone || '—' }}</p>
            <p><strong>Registro:</strong> {{ formatDate(customerDetail.created_at) }}</p>
            <div v-if="customerDetail.companies?.length" class="admin-companies-list">
              <strong>Empresas vinculadas</strong>
              <ul>
                <li v-for="co in customerDetail.companies" :key="co.id">
                  {{ co.name }} ({{ co.slug }}) — {{ co.status || 'activa' }}
                </li>
              </ul>
            </div>
          </div>
          <div class="admin-modal-actions">
            <button type="button" class="btn-action" @click="closeViewCustomer">Cerrar</button>
            <button type="button" class="btn-action primary" @click="openEditFromView">Editar / Gestionar</button>
          </div>
        </div>
      </div>

      <!-- Modal Editar Cliente -->
      <div v-if="editingCustomer" class="admin-modal-overlay" @click.self="closeEditCustomer">
        <div class="admin-modal admin-modal-wide">
          <h3>Editar cliente</h3>
          <p class="admin-modal-email">{{ editingCustomer.email }}</p>
          <div class="admin-modal-form">
            <label>Empresa</label>
            <input v-model="editForm.company_name" type="text" placeholder="Nombre de la empresa">
            <label>Plan</label>
            <select v-model="editForm.plan">
              <option value="">— Sin plan —</option>
              <option value="startup">Startup</option>
              <option value="growth">Growth</option>
              <option value="business">Business</option>
              <option value="enterprise">Enterprise</option>
            </select>
            <label>Empleados</label>
            <input v-model.number="editForm.employees" type="number" min="0" placeholder="0">
            <div class="admin-modal-web-public">
              <label class="checkbox-label">
                <input v-model="editForm.public_site_enabled" type="checkbox">
                Web pública (landing + reservas)
              </label>
              <template v-if="editForm.public_site_enabled">
                <label>Slug (URL)</label>
                <input v-model="editForm.public_site_slug" type="text" placeholder="mi-restaurante" class="slug-input">
                <p class="admin-modal-hint">Los clientes verán: /p/{{ (editForm.public_site_slug || '').toLowerCase() || 'slug' }}</p>
              </template>
            </div>

            <div class="admin-danger-zone">
              <h4>Zona superadmin</h4>
              <p class="admin-modal-hint">
                Desactiva cuentas inactivas o elimina registros de prueba/duplicados. La eliminación borra el usuario y empresas que solo le pertenecen.
              </p>
              <label>Motivo (desactivar / eliminar)</label>
              <select v-model="adminAction.reason">
                <option v-for="opt in deleteReasonOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
              <div class="admin-modal-actions inline-actions">
                <button
                  type="button"
                  class="btn-action danger"
                  :disabled="adminAction.busy || editingCustomer.is_superuser"
                  @click="setCustomerActive(false)"
                >
                  {{ adminAction.busy ? '…' : 'Desactivar cuenta' }}
                </button>
                <button
                  v-if="editingCustomer.status !== 'active'"
                  type="button"
                  class="btn-action"
                  :disabled="adminAction.busy"
                  @click="setCustomerActive(true)"
                >
                  Reactivar cuenta
                </button>
              </div>
              <label>Confirmar email para eliminar</label>
              <p class="admin-modal-hint">
                Escribe exactamente: <strong>{{ editingCustomer.email }}</strong>
              </p>
              <input
                v-model="deleteConfirmEmail"
                type="email"
                :placeholder="editingCustomer.email"
                autocomplete="off"
                @input="adminDeleteError = ''"
              >
              <p v-if="deleteConfirmEmail && !canDeleteCustomer" class="admin-modal-hint warn">
                El email no coincide. Copia y pega el correo mostrado arriba.
              </p>
              <p v-if="adminDeleteError" class="admin-modal-hint warn">{{ adminDeleteError }}</p>
              <button
                type="button"
                class="btn-action danger full-width"
                :class="{ 'btn-muted': !canDeleteCustomer && !adminAction.busy }"
                :disabled="adminAction.busy || editingCustomer.is_superuser"
                @click="deleteCustomerPermanent"
              >
                {{ adminAction.busy ? 'Procesando…' : 'Eliminar cuenta y empresa (irreversible)' }}
              </button>
              <p v-if="editingCustomer.is_superuser" class="admin-modal-hint warn">
                No se puede modificar ni eliminar un superusuario desde aquí.
              </p>
            </div>
          </div>
          <div class="admin-modal-actions">
            <button type="button" class="btn-action" @click="closeEditCustomer">Cancelar</button>
            <button type="button" class="btn-action primary" :disabled="savingEdit" @click="saveEditCustomer">{{ savingEdit ? 'Guardando…' : 'Guardar' }}</button>
          </div>
        </div>
      </div>

      <!-- Revenue -->
      <section v-if="currentView === 'revenue'" class="revenue">
        <h2>Ingresos y Facturación</h2>
        
        <div class="revenue-summary">
          <div class="revenue-card">
            <h3>Este mes</h3>
            <p class="amount">€{{ formatCurrency(stats.monthlyRevenue) }}</p>
            <p class="detail">{{ formatNumber(stats.activeSubscriptions) }} suscripciones activas</p>
          </div>
          
          <div class="revenue-card">
            <h3>Setup fees (total)</h3>
            <p class="amount">€{{ formatCurrency(stats.totalSetupFees) }}</p>
            <p class="detail">Pagos únicos de instalación</p>
          </div>
          
          <div class="revenue-card">
            <h3>Proyección anual</h3>
            <p class="amount">€{{ formatCurrency(stats.monthlyRevenue * 12) }}</p>
            <p class="detail">Basado en suscripciones actuales</p>
          </div>
        </div>

        <h3>Por plan</h3>
        <div class="plans-breakdown">
          <div class="plan-revenue" v-for="plan in revenueByPlan" :key="plan.name">
            <div class="plan-info">
              <span class="plan-name">{{ plan.name }}</span>
              <span class="plan-count">{{ plan.count }} clientes</span>
            </div>
            <div class="plan-amount">€{{ formatCurrency(plan.monthly_total) }}/mes</div>
          </div>
        </div>
      </section>

      <!-- Settings -->
      <section v-if="currentView === 'settings'" class="settings">
        <h2>Configuración de Admin</h2>
        
        <div class="settings-section">
          <h3>Integraciones</h3>
          <div class="integration-status">
            <div class="integration-item">
              <span>💳 Stripe</span>
              <span class="status-dot" :class="{ active: integrationProbe.stripe ?? integrationStatus.stripe }"></span>
            </div>
            <div class="integration-item">
              <span>📱 WhatsApp (Twilio)</span>
              <span class="status-dot" :class="{ active: integrationProbe.whatsapp ?? integrationStatus.whatsapp }"></span>
            </div>
            <div class="integration-item">
              <span>📧 Email (SendGrid)</span>
              <span class="status-dot" :class="{ active: integrationProbe.email ?? integrationStatus.email }"></span>
            </div>
          </div>
          <p class="integration-hint">
            El punto verde solo indica que la variable existe en Railway. Para garantía real antes de pagar, ejecuta la verificación E2E.
          </p>
          <button
            type="button"
            class="btn-e2e"
            :disabled="e2eRunning"
            @click="runIntegrationsE2E"
          >
            {{ e2eRunning ? 'Verificando APIs reales…' : '🔍 Verificar E2E (sin cargo)' }}
          </button>
          <div v-if="e2eResult" class="e2e-results" :class="{ ok: e2eResult.external_ready, warn: !e2eResult.external_ready }">
            <p class="e2e-summary">
              {{ e2eResult.summary.passed }}/{{ e2eResult.summary.total }} OK
              <span v-if="e2eResult.external_ready"> · Externas listas</span>
              <span v-else> · Revisa externas antes de pagar</span>
            </p>
            <p class="e2e-recommendation">{{ e2eResult.recommendation }}</p>
            <ul class="e2e-checks">
              <li v-for="check in e2eResult.checks" :key="check.id" :class="{ pass: check.ok, fail: !check.ok }">
                <strong>{{ check.name }}</strong>
                <span>{{ check.ok ? '✓' : '✗' }}</span>
                <small>{{ check.detail }}</small>
                <small v-if="check.error" class="e2e-error">{{ check.error }}</small>
              </li>
            </ul>
            <p class="e2e-disclaimer">{{ e2eResult.disclaimer }}</p>
          </div>
        </div>

        <div class="settings-section">
          <h3>Notificaciones</h3>
          <label class="checkbox-label">
            <input type="checkbox" v-model="settings.emailOnNewCustomer" />
            <span>Email cuando hay nuevo cliente</span>
          </label>
          <label class="checkbox-label">
            <input type="checkbox" v-model="settings.emailOnPaymentFailed" />
            <span>Email cuando falla un pago</span>
          </label>
        </div>

        <button class="btn-save" @click="saveSettings">
          💾 Guardar configuración
        </button>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Chart, registerables } from 'chart.js'

// Registrar componentes de Chart.js
Chart.register(...registerables)

const router = useRouter()
const authStore = useAuthStore()

const currentView = ref('overview')
const sidebarOpen = ref(false)

function selectView(view) {
  currentView.value = view
  sidebarOpen.value = false
}

// Stats
const stats = ref({
  totalCustomers: 0,
  monthlyRevenue: 0,
  totalRevenue: 0,
  activeSubscriptions: 0,
  totalSetupFees: 0
})

// Customers
const customers = ref([])
const loading = ref(false)
const error = ref(null)
// Editar cliente (empresa piloto: asignar empresa y plan)
const editingCustomer = ref(null)
const viewingCustomer = ref(null)
const customerDetail = ref({})
const loadingCustomerDetail = ref(false)
const editForm = ref({ company_name: '', plan: '', employees: '' })
const savingEdit = ref(false)
const adminAction = ref({ reason: 'test_account', busy: false })
const deleteConfirmEmail = ref('')
const adminDeleteError = ref('')

const deleteReasonOptions = [
  { value: 'test_account', label: 'Cuenta de prueba / test' },
  { value: 'duplicate', label: 'Registro duplicado' },
  { value: 'inactive', label: 'Cuenta inactiva / sin uso' },
  { value: 'customer_request', label: 'Solicitud del cliente' },
  { value: 'non_payment', label: 'Impago' },
  { value: 'fraud', label: 'Fraude / abuso' },
  { value: 'other', label: 'Otro motivo' }
]

const adminApiUrl = (path) => {
  const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
  return base ? `${base}${p}` : p
}

const getAdminToken = () => {
  const t = authStore.getToken ? authStore.getToken() : authStore.token
  if (!t) throw new Error('No hay token de autenticación')
  return t
}

const canDeleteCustomer = computed(() => {
  if (!editingCustomer.value?.email) return false
  const expected = editingCustomer.value.email.trim().toLowerCase()
  const typed = (deleteConfirmEmail.value || '').trim().toLowerCase()
  return typed.length > 0 && typed === expected
})

// Revenue by plan
const revenueByPlan = ref([])

// Chart
const revenueChartCanvas = ref(null)
let revenueChart = null
const chartReady = ref(false)

// Settings
const settings = ref({
  emailOnNewCustomer: true,
  emailOnPaymentFailed: true
})

// Integration status
const integrationStatus = ref({
  stripe: false,
  whatsapp: false,
  email: false
})

const integrationProbe = ref({
  stripe: null,
  whatsapp: null,
  email: null,
})

const e2eRunning = ref(false)
const e2eResult = ref(null)

// Auto-refresh interval
let refreshInterval = null

onMounted(async () => {
  console.log('[AdminPanel] Component mounted, loading data...')
  
  await loadStats()
  await loadCustomers()
  await loadIntegrationStatus()
  
  // Cargar gráfico después de que el DOM esté listo
  await nextTick()
  setTimeout(async () => {
    await loadChartData()
  }, 500)
  
  // Configurar auto-refresh cada 30 segundos
  refreshInterval = setInterval(async () => {
    console.log('[AdminPanel] Auto-refreshing data...')
    await loadStats()
    await loadCustomers()
    await loadChartData()
    await loadIntegrationStatus()
  }, 30000) // 30 segundos
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  if (revenueChart) {
    revenueChart.destroy()
  }
})

const loadStats = async () => {
  loading.value = true
  error.value = null
  
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }

    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/admin/stats', token)
    
    if (data.success) {
      stats.value = {
        totalCustomers: data.stats.total_customers || 0,
        monthlyRevenue: data.stats.monthly_revenue || 0,
        totalRevenue: data.stats.total_revenue || 0,
        activeSubscriptions: data.stats.active_subscriptions || 0,
        totalSetupFees: data.stats.total_setup_fees || 0
      }
      
      revenueByPlan.value = data.revenue_by_plan || []
      console.log('✅ Estadísticas cargadas:', stats.value)
    }
  } catch (err) {
    console.error('Error cargando estadísticas:', err)
    error.value = err.message || 'Error desconocido'
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      return
    }

    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/admin/customers', token)
    
    if (data.success) {
      customers.value = data.customers || []
      console.log('✅ Clientes cargados:', customers.value.length)
    }
  } catch (err) {
    console.error('Error cargando clientes:', err)
    // No mostrar error al usuario, solo log
  }
}

const loadIntegrationStatus = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      return
    }

    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/integrations/status', token)
    
    integrationStatus.value = {
      stripe: data.stripe?.configured || false,
      whatsapp: data.whatsapp?.configured || false,
      email: data.email?.configured || false
    }
    
    console.log('✅ Estado de integraciones cargado:', integrationStatus.value)
  } catch (err) {
    console.error('Error cargando estado de integraciones:', err)
  }
}

const runIntegrationsE2E = async () => {
  e2eRunning.value = true
  e2eResult.value = null
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) return
    const api = (await import('@/services/api')).default
    const data = await api.post('/api/v1/test/integrations-e2e', {}, token)
    e2eResult.value = data
    const byId = Object.fromEntries((data.checks || []).map((c) => [c.id, c.ok]))
    integrationProbe.value = {
      stripe: byId.stripe ?? null,
      whatsapp: byId.whatsapp ?? null,
      email: byId.email ?? null,
    }
  } catch (err) {
    console.error('Error E2E integraciones:', err)
    e2eResult.value = {
      external_ready: false,
      summary: { passed: 0, failed: 1, total: 1 },
      recommendation: err?.message || 'No se pudo ejecutar la verificación E2E',
      checks: [],
      disclaimer: '',
    }
  } finally {
    e2eRunning.value = false
  }
}

const loadChartData = async () => {
  try {
    console.log('[Chart] Iniciando carga de datos...')
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      console.error('[Chart] No hay token de autenticación')
      error.value = 'No hay token de autenticación'
      return
    }

    console.log('[Chart] Haciendo petición a /api/v1/admin/revenue-chart...')
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/admin/revenue-chart?months=12', token)
    console.log('[Chart] Datos recibidos:', data)
    console.log('[Chart] Datos recibidos:', data)
    
    if (data.success && data.chart_data) {
      console.log('[Chart] Datos válidos, renderizando gráfico...')
      // Esperar a que el DOM esté actualizado
      await nextTick()
      
      // Esperar un frame más para asegurar que el canvas esté renderizado
      setTimeout(() => {
        renderChart(data.chart_data)
      }, 200)
    } else {
      console.warn('[Chart] Datos no válidos o vacíos:', data)
      renderEmptyChart('No hay datos disponibles')
    }
  } catch (err) {
    console.error('[Chart] Error cargando datos del gráfico:', err)
    error.value = err.message || 'Error cargando datos del gráfico'
    renderEmptyChart(err.message || 'Error cargando datos')
  }
}

const renderEmptyChart = (message = 'No hay datos disponibles') => {
  if (!revenueChartCanvas.value) {
    setTimeout(() => renderEmptyChart(message), 200)
    return
  }

  // Destruir gráfico anterior si existe
  if (revenueChart) {
    revenueChart.destroy()
    revenueChart = null
  }

  // Crear un gráfico simple con un dataset vacío para mostrar el mensaje
  const ctx = revenueChartCanvas.value.getContext('2d')
  
  // Asegurar que el canvas tenga dimensiones correctas
  const container = revenueChartCanvas.value.parentElement
  let width = 600
  let height = 400
  
  if (container) {
    width = container.clientWidth - 40
    height = 400
  }
  
  revenueChartCanvas.value.width = width
  revenueChartCanvas.value.height = height
  
  // Limpiar el canvas
  ctx.clearRect(0, 0, width, height)
  
  // Dibujar mensaje directamente
  ctx.save()
  ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
  ctx.font = 'bold 18px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(message, width / 2, height / 2)
  ctx.restore()

  chartReady.value = true
  console.log('[Chart] Mensaje renderizado en canvas:', message, 'Dimensiones:', width, 'x', height)
}

const renderChart = (chartData) => {
  console.log('[Chart] Intentando renderizar gráfico...')
  console.log('[Chart] Canvas disponible?', !!revenueChartCanvas.value)
  console.log('[Chart] Datos recibidos:', chartData)
  
  if (!revenueChartCanvas.value) {
    console.warn('[Chart] Canvas no disponible aún, reintentando en 200ms...')
    setTimeout(() => {
      if (revenueChartCanvas.value) {
        if (chartData && chartData.labels && chartData.labels.length > 0) {
          renderChart(chartData)
        } else {
          renderEmptyChart('No hay datos disponibles')
        }
      } else {
        console.error('[Chart] Canvas nunca estuvo disponible')
        error.value = 'No se pudo inicializar el gráfico'
      }
    }, 200)
    return
  }

  // Validar que hay datos
  if (!chartData || !chartData.labels || chartData.labels.length === 0) {
    console.warn('[Chart] No hay datos para mostrar, renderizando gráfico vacío')
    renderEmptyChart('No hay datos para mostrar')
    return
  }

  // Destruir gráfico anterior si existe
  if (revenueChart) {
    console.log('[Chart] Destruyendo gráfico anterior')
    revenueChart.destroy()
    revenueChart = null
  }

  // Formatear labels de meses (YYYY-MM -> Mes YYYY)
  const formattedLabels = chartData.labels.map(label => {
    try {
      const [year, month] = label.split('-')
      const date = new Date(parseInt(year), parseInt(month) - 1)
      return date.toLocaleDateString('es-ES', { month: 'short', year: 'numeric' })
    } catch (e) {
      console.warn('[Chart] Error formateando label:', label, e)
      return label
    }
  })

  console.log('[Chart] Labels formateados:', formattedLabels)

  // Crear nuevo gráfico
  const ctx = revenueChartCanvas.value.getContext('2d')
  
  // Asegurar que el canvas tenga dimensiones correctas
  const container = revenueChartCanvas.value.parentElement
  if (container) {
    const containerWidth = container.clientWidth - 40
    const containerHeight = 400
    revenueChartCanvas.value.width = containerWidth
    revenueChartCanvas.value.height = containerHeight
  } else {
    revenueChartCanvas.value.width = 600
    revenueChartCanvas.value.height = 400
  }
  
  console.log('[Chart] Dimensiones del canvas:', revenueChartCanvas.value.width, 'x', revenueChartCanvas.value.height)
  
  revenueChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: formattedLabels,
      datasets: chartData.datasets.map((dataset, index) => ({
        ...dataset,
        tension: 0.4,
        fill: index === 0, // Solo llenar el primer dataset
        pointRadius: 4,
        pointHoverRadius: 6
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: 'rgba(255, 255, 255, 0.8)',
            font: {
              size: 12,
              family: "'Inter', sans-serif"
            },
            padding: 15,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: 'rgba(10, 14, 25, 0.95)',
          titleColor: '#fff',
          bodyColor: 'rgba(255, 255, 255, 0.9)',
          borderColor: 'rgba(59, 130, 246, 0.5)',
          borderWidth: 1,
          padding: 12,
          displayColors: true,
          callbacks: {
            label: (context) => {
              const value = context.parsed.y
              return `${context.dataset.label}: €${formatNumber(value, 2)}`
            }
          }
        }
      },
      scales: {
        x: {
          ticks: {
            color: 'rgba(255, 255, 255, 0.6)',
            font: {
              size: 11
            }
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.05)',
            drawBorder: false
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: 'rgba(255, 255, 255, 0.6)',
            font: {
              size: 11
            },
            callback: (value) => {
              return '€' + formatNumber(value, 0)
            }
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.05)',
            drawBorder: false
          }
        }
      }
    }
  })

  chartReady.value = true
  console.log('✅ Gráfico renderizado exitosamente')
  error.value = null // Limpiar errores si el gráfico se renderizó correctamente
}

// Funciones de formateo
const formatCurrency = (value) => {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

const formatNumber = (value, decimals = 0) => {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString('es-ES', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

const getPlanName = (plan) => {
  const names = {
    startup: 'STARTUP',
    growth: 'GROWTH',
    business: 'BUSINESS',
    enterprise: 'ENTERPRISE'
  }
  return names[plan] || plan.toUpperCase()
}

const formatDate = (date) => {
  if (!date) return '-'
  try {
    return new Date(date).toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch (e) {
    return '-'
  }
}

const fetchCustomerDetail = async (customerId) => {
  const token = getAdminToken()
  const response = await fetch(adminApiUrl(`/api/v1/admin/customers/${customerId}`), {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || 'No se pudieron cargar los detalles')
  }
  const data = await response.json()
  return data.customer || data
}

const viewCustomer = async (customer) => {
  viewingCustomer.value = customer
  loadingCustomerDetail.value = true
  customerDetail.value = { ...customer }
  try {
    customerDetail.value = await fetchCustomerDetail(customer.id)
  } catch (e) {
    console.error('Error cargando detalles del cliente:', e)
    customerDetail.value = { ...customer }
  } finally {
    loadingCustomerDetail.value = false
  }
}

const closeViewCustomer = () => {
  viewingCustomer.value = null
  customerDetail.value = {}
}

const openEditFromView = () => {
  const c = viewingCustomer.value
  closeViewCustomer()
  if (c) openEditCustomer(c)
}

const openEditCustomer = (customer) => {
  editingCustomer.value = customer
  adminAction.value = { reason: 'test_account', busy: false }
  deleteConfirmEmail.value = ''
  adminDeleteError.value = ''
  editForm.value = {
    company_name: customer.company_name && customer.company_name !== 'N/A' ? customer.company_name : '',
    plan: customer.plan && customer.plan !== 'none' ? customer.plan : '',
    employees: customer.employees ?? '',
    public_site_enabled: !!customer.public_site_enabled,
    public_site_slug: customer.public_site_slug || ''
  }
}

const closeEditCustomer = () => {
  editingCustomer.value = null
  adminAction.value = { reason: 'test_account', busy: false }
  deleteConfirmEmail.value = ''
  adminDeleteError.value = ''
}

const setCustomerActive = async (active) => {
  if (!editingCustomer.value) return
  const label = active ? 'reactivar' : 'desactivar'
  if (!active && !confirm(`¿${label.charAt(0).toUpperCase() + label.slice(1)} la cuenta ${editingCustomer.value.email}?`)) {
    return
  }
  adminAction.value.busy = true
  try {
    const token = getAdminToken()
    const response = await fetch(
      adminApiUrl(`/api/v1/admin/customers/${editingCustomer.value.id}/status`),
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          is_active: active,
          reason: adminAction.value.reason
        })
      }
    )
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || response.statusText)
    }
    editingCustomer.value.status = active ? 'active' : 'inactive'
    await loadCustomers()
    alert(active ? '✅ Cuenta reactivada' : '✅ Cuenta desactivada')
  } catch (e) {
    alert('❌ ' + (e.message || 'No se pudo cambiar el estado'))
  } finally {
    adminAction.value.busy = false
  }
}

const deleteCustomerPermanent = async () => {
  if (!editingCustomer.value) return
  if (!canDeleteCustomer.value) {
    adminDeleteError.value = `Escribe exactamente: ${editingCustomer.value.email}`
    return
  }
  const email = editingCustomer.value.email
  if (
    !confirm(
      `ELIMINAR PERMANENTEMENTE:\n${email}\n\nSe borrarán el usuario y las empresas que solo le pertenezcan.\nEsta acción no se puede deshacer.`
    )
  ) {
    return
  }
  adminAction.value.busy = true
  adminDeleteError.value = ''
  try {
    const token = getAdminToken()
    const payload = {
      reason: adminAction.value.reason,
      confirm_email: deleteConfirmEmail.value.trim()
    }
    const url = adminApiUrl(`/api/v1/admin/customers/${editingCustomer.value.id}/delete`)
    let response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })
    if (!response.ok && response.status === 405) {
      response = await fetch(
        adminApiUrl(`/api/v1/admin/customers/${editingCustomer.value.id}`),
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        }
      )
    }
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      const detail = err.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || d).join(' ')
            : 'No se pudo eliminar la cuenta'
      throw new Error(msg)
    }
    closeEditCustomer()
    await loadCustomers()
    alert('✅ Cuenta eliminada correctamente')
  } catch (e) {
    adminDeleteError.value = e.message || 'No se pudo eliminar'
    alert('❌ ' + adminDeleteError.value)
  } finally {
    adminAction.value.busy = false
  }
}

const saveEditCustomer = async () => {
  if (!editingCustomer.value) return
  savingEdit.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    const url = adminApiUrl(`/api/v1/admin/customers/${editingCustomer.value.id}`)
    const response = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        company_name: editForm.value.company_name || null,
        plan: editForm.value.plan || null,
        employees: editForm.value.employees === '' ? null : Number(editForm.value.employees),
        public_site_enabled: editForm.value.public_site_enabled,
        public_site_slug: editForm.value.public_site_slug ? String(editForm.value.public_site_slug).trim() : null
      })
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || response.statusText)
    }
    await loadCustomers()
    closeEditCustomer()
    alert('✅ Cliente actualizado. Empresa y plan guardados.')
  } catch (e) {
    console.error('Error guardando cliente:', e)
    alert('❌ ' + (e.message || 'No se pudo guardar'))
  } finally {
    savingEdit.value = false
  }
}

const toggleCustomerStatus = async (customer) => {
  const newActive = customer.status !== 'active'
  const label = newActive ? 'activar' : 'desactivar'
  if (!confirm(`¿${label.charAt(0).toUpperCase() + label.slice(1)} ${customer.email}?`)) return
  try {
    const token = getAdminToken()
    const response = await fetch(
      adminApiUrl(`/api/v1/admin/customers/${customer.id}/toggle-status`),
      {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          is_active: newActive,
          reason: newActive ? 'reactivated' : 'inactive'
        })
      }
    )
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || response.statusText)
    }
    customer.status = newActive ? 'active' : 'inactive'
    await loadCustomers()
    alert(`✅ Cliente ${newActive ? 'activado' : 'desactivado'}`)
  } catch (error) {
    console.error('Error cambiando estado del cliente:', error)
    alert('❌ ' + (error.message || 'No se pudo cambiar el estado'))
  }
}

const saveSettings = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const api = (await import('@/services/api')).default
    await api.post('/api/v1/admin/settings', {
      notifications: {
        email_on_new_customer: settings.value.emailOnNewCustomer,
        email_on_payment_failed: settings.value.emailOnPaymentFailed
      }
    }, token)
    
    alert('✅ Configuración guardada correctamente')
  } catch (error) {
    console.error('Error guardando configuración:', error)
    // Fallback a localStorage
    localStorage.setItem('zeus_admin_settings', JSON.stringify(settings.value))
    alert('✅ Configuración guardada localmente')
  }
}

const goToDashboard = () => {
  sidebarOpen.value = false
  router.push('/dashboard')
}
</script>

<style scoped>
.admin-panel {
  display: flex;
  min-height: 100vh;
  background: #0a0e1a;
  color: #fff;
}

/* Sidebar */
.admin-sidebar {
  width: 280px;
  background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
}

.logo h1 {
  font-size: 24px;
  margin: 0 0 4px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.logo p {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin: 0 0 40px;
}

.admin-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: auto;
}

.admin-nav button {
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.admin-nav button:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.admin-nav button.active {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.btn-back {
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  margin-top: 20px;
}

/* Main Content */
.admin-content {
  flex: 1;
  padding: 40px;
  overflow-y: auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.admin-content h2 {
  font-size: 32px;
  margin: 0 0 32px;
}

.admin-content h3 {
  font-size: 20px;
  margin: 32px 0 16px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.stat-card {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 24px;
  text-align: center;
}

.stat-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 8px;
}

.stat-label {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

/* Customers Table */
.customers-table {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: rgba(59, 130, 246, 0.1);
}

th {
  padding: 16px;
  text-align: left;
  font-weight: 600;
  color: #3b82f6;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

td {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.plan-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.plan-badge.startup {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.plan-badge.growth {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.plan-badge.business {
  background: rgba(139, 92, 246, 0.2);
  color: #8b5cf6;
}

.plan-badge.enterprise {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.active {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.status-badge.inactive {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.btn-action {
  padding: 6px 12px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  color: #3b82f6;
  cursor: pointer;
  margin-right: 8px;
  font-size: 12px;
}

.btn-action:hover {
  background: rgba(59, 130, 246, 0.3);
}

.btn-action.danger {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.btn-refresh {
  padding: 10px 20px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  color: #3b82f6;
  cursor: pointer;
}

.empty-state {
  padding: 60px;
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
}

/* Revenue */
.revenue-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.revenue-card {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
}

.revenue-card h3 {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 12px;
  font-weight: 500;
}

.revenue-card .amount {
  font-size: 32px;
  font-weight: 700;
  color: #10b981;
  margin: 0 0 8px;
}

.revenue-card .detail {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.plans-breakdown {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.plan-revenue {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.plan-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.plan-name {
  font-weight: 600;
}

.plan-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.plan-amount {
  font-size: 24px;
  font-weight: 700;
  color: #3b82f6;
}

/* Chart */
.chart-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 32px;
}

.chart-container {
  height: 400px;
  position: relative;
  padding: 20px;
  min-height: 400px;
  width: 100%;
}

.chart-container canvas {
  width: 100% !important;
  height: 100% !important;
  display: block !important;
}

.chart-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.5);
  font-size: 16px;
  z-index: 10;
  pointer-events: none;
}

.chart-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #ef4444;
  font-size: 14px;
  z-index: 10;
  pointer-events: none;
  text-align: center;
  padding: 20px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
  max-width: 80%;
}

.chart-container {
  height: 400px;
  position: relative;
  padding: 20px;
}

.chart-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.5);
  font-size: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
}

.chart-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ef4444;
  font-size: 14px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

/* Settings */
.settings-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.integration-status {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.integration-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.5);
}

.status-dot.active {
  background: #10b981;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
}

.integration-hint {
  margin: 12px 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.4;
}

.btn-e2e {
  margin-top: 8px;
  padding: 12px 20px;
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 8px;
  background: rgba(59, 130, 246, 0.15);
  color: #93c5fd;
  font-weight: 600;
  cursor: pointer;
}

.btn-e2e:disabled {
  opacity: 0.6;
  cursor: wait;
}

.e2e-results {
  margin-top: 16px;
  padding: 16px;
  border-radius: 8px;
  font-size: 13px;
}

.e2e-results.ok {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.35);
}

.e2e-results.warn {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.e2e-summary {
  margin: 0 0 8px;
  font-weight: 700;
}

.e2e-recommendation {
  margin: 0 0 12px;
  color: rgba(255, 255, 255, 0.8);
}

.e2e-checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.e2e-checks li {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
}

.e2e-checks li.pass strong {
  color: #6ee7b7;
}

.e2e-checks li.fail strong {
  color: #fca5a5;
}

.e2e-checks li small {
  grid-column: 1 / -1;
  color: rgba(255, 255, 255, 0.55);
}

.e2e-error {
  color: #f87171 !important;
}

.e2e-disclaimer {
  margin: 12px 0 0;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  cursor: pointer;
}

.checkbox-label input {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.btn-save {
  padding: 14px 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-weight: 600;
  cursor: pointer;
  margin-top: 24px;
}

.btn-save:hover {
  transform: scale(1.02);
}

/* Modal Editar Cliente */
.admin-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.admin-modal {
  background: #1a1f2e;
  border-radius: 12px;
  padding: 24px;
  min-width: 320px;
  max-width: 90vw;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}
.admin-modal h3 {
  margin: 0 0 8px 0;
  color: #fff;
  font-size: 1.25rem;
}
.admin-modal-email {
  margin: 0 0 16px 0;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.9rem;
}
.admin-modal-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}
.admin-modal-form label {
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.875rem;
}
.admin-modal-form input,
.admin-modal-form select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  font-size: 1rem;
}
.admin-modal-web-public { margin-top: 12px; }
.admin-modal-web-public .checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.admin-modal-web-public .slug-input { margin-top: 6px; }
.admin-modal-hint { margin: 4px 0 0 0; font-size: 0.8rem; color: rgba(255, 255, 255, 0.5); }
.admin-modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
.admin-modal-wide {
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}
.admin-danger-zone {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(239, 68, 68, 0.35);
}
.admin-danger-zone h4 {
  margin: 0 0 8px;
  color: #f87171;
  font-size: 0.95rem;
}
.admin-danger-zone .inline-actions {
  margin: 10px 0;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}
.admin-danger-zone .full-width {
  width: 100%;
  margin-top: 8px;
}
.btn-action.btn-muted {
  opacity: 0.55;
}
.btn-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.admin-modal-hint.warn {
  color: #fbbf24;
}
.admin-companies-list ul {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.75);
}
.admin-modal-actions .btn-action.primary {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

/* Cabecera móvil (solo en viewport pequeño) */
.admin-mobile-header {
  display: none;
}

.admin-sidebar-overlay {
  display: none;
}

/* Responsive: Admin Panel móvil */
@media (max-width: 768px) {
  .admin-mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 56px;
    padding: 0 16px;
    background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    z-index: 1001;
  }

  .admin-mobile-menu-btn {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 8px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: #fff;
  }
  .admin-mobile-menu-btn span {
    display: block;
    width: 22px;
    height: 2px;
    background: currentColor;
    border-radius: 1px;
  }

  .admin-mobile-title {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .admin-mobile-back {
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #fff;
    font-size: 14px;
    cursor: pointer;
  }

  .admin-sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }

  .admin-panel {
    flex-direction: row;
  }

  .admin-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 280px;
    max-width: 85vw;
    height: 100vh;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
  }

  .admin-sidebar.open {
    transform: translateX(0);
  }

  .admin-content {
    padding: 72px 16px 24px;
    min-height: 100vh;
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .customers-table-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin: 0 -16px;
    padding: 0 16px;
  }

  .customers-table {
    min-width: 640px;
  }

  table {
    font-size: 12px;
  }

  th, td {
    padding: 10px;
  }
}
</style>

