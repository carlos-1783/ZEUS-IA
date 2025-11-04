<template>
  <div class="admin-panel">
    <!-- Sidebar -->
    <aside class="admin-sidebar">
      <div class="logo">
        <h1>⚡ ZEUS-IA</h1>
        <p>Panel de Administración</p>
      </div>

      <nav class="admin-nav">
        <button 
          :class="{ active: currentView === 'overview' }"
          @click="currentView = 'overview'"
        >
          📊 Overview
        </button>
        <button 
          :class="{ active: currentView === 'customers' }"
          @click="currentView = 'customers'"
        >
          👥 Clientes
        </button>
        <button 
          :class="{ active: currentView === 'revenue' }"
          @click="currentView = 'revenue'"
        >
          💰 Ingresos
        </button>
        <button 
          :class="{ active: currentView === 'settings' }"
          @click="currentView = 'settings'"
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
            <div class="stat-value">{{ stats.totalCustomers }}</div>
            <div class="stat-label">Clientes Totales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-value">€{{ stats.monthlyRevenue }}</div>
            <div class="stat-label">Ingresos Mensuales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">📈</div>
            <div class="stat-value">€{{ stats.totalRevenue }}</div>
            <div class="stat-label">Ingresos Totales</div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon">🎯</div>
            <div class="stat-value">{{ stats.activeSubscriptions }}</div>
            <div class="stat-label">Suscripciones Activas</div>
          </div>
        </div>

        <!-- Revenue Chart Placeholder -->
        <div class="chart-section">
          <h3>Ingresos por Mes</h3>
          <div class="chart-placeholder">
            📊 Gráfico de ingresos (implementar con Chart.js)
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

        <div class="customers-table">
          <table>
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

      <!-- Revenue -->
      <section v-if="currentView === 'revenue'" class="revenue">
        <h2>Ingresos y Facturación</h2>
        
        <div class="revenue-summary">
          <div class="revenue-card">
            <h3>Este mes</h3>
            <p class="amount">€{{ stats.monthlyRevenue }}</p>
            <p class="detail">{{ stats.activeSubscriptions }} suscripciones activas</p>
          </div>
          
          <div class="revenue-card">
            <h3>Setup fees (total)</h3>
            <p class="amount">€{{ stats.totalSetupFees }}</p>
            <p class="detail">Pagos únicos de instalación</p>
          </div>
          
          <div class="revenue-card">
            <h3>Proyección anual</h3>
            <p class="amount">€{{ stats.monthlyRevenue * 12 }}</p>
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
            <div class="plan-amount">€{{ plan.monthly_total }}/mes</div>
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
              <span class="status-dot active"></span>
            </div>
            <div class="integration-item">
              <span>📱 WhatsApp (Twilio)</span>
              <span class="status-dot" :class="{ active: false }"></span>
            </div>
            <div class="integration-item">
              <span>📧 Email (SendGrid)</span>
              <span class="status-dot" :class="{ active: false }"></span>
            </div>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const currentView = ref('overview')

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

// Revenue by plan
const revenueByPlan = ref([
  { name: 'ZEUS STARTUP', count: 0, monthly_total: 0 },
  { name: 'ZEUS GROWTH', count: 0, monthly_total: 0 },
  { name: 'ZEUS BUSINESS', count: 0, monthly_total: 0 },
  { name: 'ZEUS ENTERPRISE', count: 0, monthly_total: 0 }
])

// Settings
const settings = ref({
  emailOnNewCustomer: true,
  emailOnPaymentFailed: true
})

onMounted(() => {
  loadStats()
  loadCustomers()
})

const loadStats = async () => {
  // TODO: Cargar stats reales del backend
  stats.value = {
    totalCustomers: 0,
    monthlyRevenue: 0,
    totalRevenue: 0,
    activeSubscriptions: 0,
    totalSetupFees: 0
  }
}

const loadCustomers = async () => {
  // TODO: Cargar clientes del backend
  customers.value = []
}

const getPlanName = (plan) => {
  const names = {
    startup: 'STARTUP',
    growth: 'GROWTH',
    business: 'BUSINESS',
    enterprise: 'ENTERPRISE'
  }
  return names[plan] || plan
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('es-ES')
}

const viewCustomer = (customer) => {
  console.log('Ver cliente:', customer)
  // TODO: Abrir modal con detalles
}

const toggleCustomerStatus = (customer) => {
  console.log('Toggle status:', customer)
  // TODO: Activar/desactivar cliente
}

const saveSettings = () => {
  console.log('Guardar settings:', settings.value)
  // TODO: Guardar en backend
}

const goToDashboard = () => {
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

.chart-placeholder {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
  font-size: 18px;
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

/* Responsive */
@media (max-width: 768px) {
  .admin-panel {
    flex-direction: column;
  }

  .admin-sidebar {
    width: 100%;
  }

  .admin-content {
    padding: 20px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  table {
    font-size: 12px;
  }

  th, td {
    padding: 8px;
  }
}
</style>

