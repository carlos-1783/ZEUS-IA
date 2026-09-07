<template>
  <div class="dashboard-profesional dashboard-root" :class="{ 'dashboard-executive-root': currentView === 'dashboard' }">
    <!-- Overlay para móvil -->
    <div 
      class="sidebar-overlay" 
      :class="{ active: sidebarOpen }"
      @click="sidebarOpen = false"
    ></div>

    <!-- Sidebar Oscura -->
    <aside class="sidebar-dark" :class="{ open: sidebarOpen }">
      <div class="logo-section">
        <img src="/images/logo-zeus.png" alt="ZEUS" class="logo-zeus-img" />
        <h1>ZEUS-IA</h1>
        <p class="subtitle">{{ t('dashboardPro.subtitle') }}</p>
      </div>

      <nav class="nav-menu">
        <button 
          class="nav-item" 
          :class="{ active: currentView === 'dashboard' }"
          @click="currentView = 'dashboard'; closeSidebarOnMobile()"
        >
          <span class="icon">🏛️</span>
          <span>{{ t('dashboardPro.nav.dashboard') }}</span>
        </button>
        <!-- Admin Panel: solo superusuario (el resto de empresas no lo ve en producción) -->
        <button 
          v-if="!isEmployee && (authStore.isAdmin || authStore.user?.is_superuser)"
          class="nav-item admin-btn"
          @click="closeSidebarOnMobile(); goToAdmin()"
        >
          <span class="icon">🔐</span>
          <span>{{ t('dashboardPro.nav.admin') }}</span>
        </button>
        <button 
          v-if="showModule('analytics')"
          class="nav-item"
          :class="{ active: currentView === 'analytics' }"
          @click="currentView = 'analytics'; closeSidebarOnMobile()"
        >
          <span class="icon">📊</span>
          <span>{{ t('dashboardPro.nav.analytics') }}</span>
        </button>
        <button 
          v-if="showModule('tpv')"
          class="nav-item tpv-nav-btn"
          @click="goToTPV"
        >
          <span class="icon">💳</span>
          <span>{{ t('dashboardPro.nav.tpv') }}</span>
        </button>
        <button 
          v-if="showModule('control_horario')"
          class="nav-item control-horario-nav-btn"
          @click="goToControlHorario"
        >
          <span class="icon">⏰</span>
          <span>{{ t('dashboardPro.nav.controlHorario') }}</span>
        </button>
        <button 
          v-if="showModule('crm') && !isEmployee"
          type="button"
          class="nav-item"
          @click="closeSidebarOnMobile(); goToOfficeCrm()"
        >
          <span class="icon">📁</span>
          <span>{{ t('dashboardPro.nav.officeCrm') }}</span>
        </button>
        <!-- Seguros: sin gating por company_type (vertical nueva, ver AUDIT_VERTICAL_SEGUROS.md) -->
        <button
          v-if="!isEmployee"
          type="button"
          class="nav-item"
          @click="closeSidebarOnMobile(); goToInsurance()"
        >
          <span class="icon">🛡️</span>
          <span>{{ t('dashboardPro.nav.insurance') }}</span>
        </button>
        <!-- Nóminas: solo dueño de empresa (empleado no ve) -->
        <button
          v-if="showModule('payroll')"
          class="nav-item"
          @click="closeSidebarOnMobile(); goToPayroll()"
        >
          <span class="icon">📋</span>
          <span>{{ t('dashboardPro.nav.payroll') }}</span>
        </button>
        <button 
          v-if="!isEmployee"
          class="nav-item"
          @click="closeSidebarOnMobile(); goToUserSettings()"
        >
          <span class="icon">⚙️</span>
          <span>{{ t('dashboardPro.nav.settings') }}</span>
        </button>
      </nav>

      <div class="metrics-mini">
        <div class="metric-item">
          <div class="metric-value">{{ backendHealthLabel }}</div>
          <div class="metric-label">{{ backendHealthDetail }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ agentsData.length }}</div>
          <div class="metric-label">{{ t('dashboardPro.metrics.activeAgents') }}</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content" :class="{ 'main-content--dashboard': currentView === 'dashboard' }">
      <!-- Header (analytics / settings views) -->
      <header v-if="currentView !== 'dashboard'" class="dashboard-header">
        <div class="header-left">
          <!-- Botón hamburguesa para móvil -->
          <button 
            class="hamburger-btn" 
            :class="{ active: sidebarOpen }"
            @click="sidebarOpen = !sidebarOpen"
          >
            <span></span>
            <span></span>
            <span></span>
          </button>
          <div>
            <h2>{{ t('dashboardPro.header.title') }}</h2>
            <p class="breadcrumb">{{ t('dashboardPro.header.breadcrumb') }}</p>
          </div>
        </div>
        <div class="header-right">
          <PWAControls
            :system-online="backendHealthLabel === 'OK'"
            :system-detail="backendHealthDetail"
          />
        </div>
      </header>

      <!-- Executive panel — KPI + ZEUS CORE + agents grid -->
      <div v-if="currentView === 'dashboard'" class="zeus-dashboard dashboard-executive">
        <div class="executive-pwa-bar">
          <PWAControls
            compact
            :system-online="backendHealthLabel === 'OK'"
            :system-detail="backendHealthDetail"
          />
        </div>
        <button
          class="hamburger-btn executive-hamburger"
          :class="{ active: sidebarOpen }"
          @click="sidebarOpen = !sidebarOpen"
          type="button"
          aria-label="Menú"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <div class="executive-section executive-section--kpi">
          <KPIBar :items="executiveKpis" />
        </div>

        <div class="executive-section executive-section--zeus">
          <div class="zeus-core-highlight zeus-core">
            <div class="zeus-core-card" @click="selectAgent(zeusCoreAgent)">
              <div class="zeus-core-avatar-container">
                <img
                  :src="zeusCoreAgent.image"
                  :alt="zeusCoreAgent.name"
                  class="zeus-core-avatar"
                />
                <span
                  class="status-dot"
                  :class="zeusCoreAgent.status"
                  :title="agentStatusLabel(zeusCoreAgent.status)"
                  aria-hidden="true"
                ></span>
              </div>
              <div class="zeus-core-info">
                <h2 class="zeus-core-name">
                  {{ zeusCoreAgent.name }}
                  <span v-if="zeusCoreAgent.beta" class="beta-badge">BETA</span>
                </h2>
                <p class="zeus-core-role">{{ zeusCoreAgent.role }}</p>
                <div class="zeus-core-metrics">
                  <span class="zeus-core-status" :class="backendHealthLabel === 'OK' ? 'online' : 'degraded'">
                    ● {{ backendHealthLabel === 'OK' ? t('dashboardPro.systemOnline') : backendHealthDetail }}
                  </span>
                  <span class="zeus-core-activity">
                    {{ zeusCoreAgent.activities_24h || 0 }} {{ t('dashboardPro.agentCard.activities24h') }}
                  </span>
                </div>
                <button class="btn-interact zeus-core-interact" @click.stop="chatWith(zeusCoreAgent)">
                  <span>💬</span>
                  {{ t('dashboardPro.agentCard.interact') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <section class="agents-grid executive-agents-grid">
        <div
          v-for="agent in executiveGridAgents"
          :key="agent.name"
          class="agent-card agent-card--executive"
          :class="{ 'has-avatar': agent.hasGLB }"
          @click="selectAgent(agent)"
        >
          <!-- Avatar Image: mismo asset real, con tratamiento CSS propio
               por agente (sin arte nuevo, ver AUDIT_REDISENO_TARJETAS_AGENTE.md) -->
          <div class="avatar-container" :class="agentAvatarFx(agent.name)">
            <img
              v-if="agent.name === 'JUSTICIA'"
              :src="agent.image"
              alt=""
              aria-hidden="true"
              class="avatar-ghost"
            />
            <img
              :src="agent.image"
              :alt="agent.name"
              class="avatar-image"
            />
            <span
              class="status-dot"
              :class="agent.status"
              :title="agentStatusLabel(agent.status)"
              aria-hidden="true"
            ></span>
          </div>

          <!-- Agent Info -->
          <div class="agent-info">
            <h3 class="agent-name">
              {{ agent.name }}
              <span v-if="agent.beta" class="beta-badge">BETA</span>
            </h3>
            <p class="agent-role">{{ agent.role }}</p>

            <div class="agent-stats">
              <div class="stat">
                <span class="stat-label">{{ t('dashboardPro.agentCard.status') }}</span>
                <span class="stat-value" :class="`status-${agent.status}`">{{ agentStatusLabel(agent.status) }}</span>
              </div>
              <div class="stat">
                <span class="stat-label">{{ t('dashboardPro.agentCard.activities24h') }}</span>
                <span class="stat-value">{{ agent.activities_24h || 0 }}</span>
              </div>
            </div>

            <button class="btn-interact" @click.stop="chatWith(agent)">
              <span>💬</span>
              {{ t('dashboardPro.agentCard.interact') }}
            </button>
          </div>
        </div>
        </section>
      </div>

      <!-- Analytics View -->
      <section v-if="currentView === 'analytics'" class="analytics-view">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon">📈</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.totalInteractions') }}</h3>
              <p class="stat-number">{{ dashboardMetrics.totalInteractions.toLocaleString() }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.interactionsTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.avgResponseTime') }}</h3>
              <p class="stat-number">{{ dashboardMetrics.avgResponseTime }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.responseTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.costSavings') }}</h3>
              <p class="stat-number">{{ dashboardMetrics.costSavings }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.savingsTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">✅</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.successRate') }}</h3>
              <p class="stat-number">{{ dashboardMetrics.successRate }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.successTrend }}</span>
            </div>
          </div>
        </div>

        <div class="stats-grid financial-grid">
          <div class="stat-card">
            <div class="stat-icon">💶</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.totalRevenue') }}</h3>
              <p class="stat-number">€{{ financialMetrics.totalRevenue.toLocaleString('es-ES', { minimumFractionDigits: 2 }) }}</p>
              <span class="stat-change">{{ financialMetrics.tpvSales }} TPV · {{ financialMetrics.cmrPayments }} CMR</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">🧾</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.salesCount') }}</h3>
              <p class="stat-number">{{ financialMetrics.salesCount }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">📊</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.avgTicket') }}</h3>
              <p class="stat-number">€{{ financialMetrics.avgTicket.toLocaleString('es-ES', { minimumFractionDigits: 2 }) }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">👥</div>
            <div class="stat-content">
              <h3>{{ t('dashboardPro.analytics.activeCustomers') }}</h3>
              <p class="stat-number">{{ financialMetrics.activeCustomers }}</p>
            </div>
          </div>
        </div>

        <div class="chart-real">
          <h3>{{ t('dashboardPro.analytics.chartTitle') }}</h3>
          <div v-if="salesByDay.length" class="bar-chart">
            <div
              v-for="bar in salesByDay"
              :key="bar.date"
              class="bar-col"
              :title="`${bar.date}: €${bar.total}`"
            >
              <div
                class="bar-fill"
                :style="{ height: `${barHeight(bar.total)}%` }"
              />
              <span class="bar-label">{{ bar.label }}</span>
            </div>
          </div>
          <p v-else class="chart-empty">{{ t('dashboardPro.analytics.noSalesData') }}</p>
        </div>
      </section>

      <!-- Ajustes de cuenta (idioma/tema/2FA): página dedicada /settings -->
      <section v-if="currentView === 'settings'" class="settings-view">
        <div class="settings-grid">
          <div class="settings-card">
            <h3>🔔 {{ t('dashboardPro.notifications.title') }}</h3>
            <div class="setting-item">
              <label>{{ t('dashboardPro.notifications.email') }}</label>
              <input type="checkbox" v-model="notificationSettings.email" />
            </div>
            <div class="setting-item">
              <label>{{ t('dashboardPro.notifications.push') }}</label>
              <input type="checkbox" v-model="notificationSettings.push" />
            </div>
            <div class="setting-item">
              <label>{{ t('dashboardPro.notifications.agentStatus') }}</label>
              <input type="checkbox" v-model="notificationSettings.agentStatus" />
            </div>
          </div>

          <div class="settings-card">
            <h3>⚙️ {{ t('dashboardPro.advanced.title') }}</h3>
            <p class="settings-embed-hint">{{ t('dashboardPro.settingsEmbed') }} <a href="#" class="settings-link" @click.prevent="goToUserSettings">{{ t('dashboardPro.settingsEmbedLink') }}</a></p>
            <div class="setting-item">
              <label>{{ t('dashboardPro.advanced.apiAccess') }}</label>
              <button class="btn-secondary" @click="handleGenerateApiKey">{{ t('dashboardPro.advanced.generateKey') }}</button>
            </div>
            <div class="setting-item">
              <label>{{ t('dashboardPro.advanced.exportData') }}</label>
              <button class="btn-secondary" @click="handleExportData">{{ t('dashboardPro.advanced.download') }}</button>
            </div>
          </div>
        </div>
      </section>

      <!-- Agent Activity Panel (si hay agente seleccionado) -->
      <Transition name="agent-modal">
        <div
          v-if="selectedAgent"
          class="agent-overlay"
          role="dialog"
          aria-modal="true"
          :aria-label="`Workspace de ${selectedAgent?.name || 'agente'}`"
          @click.self="closeAgentPanel"
        >
          <div class="agent-panel-container">
            <button class="btn-close-panel" @click="closeAgentPanel" aria-label="Cerrar">✕</button>
            <AgentActivityPanel :agent="selectedAgent" />
          </div>
        </div>
      </Transition>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import AgentActivityPanel from './AgentActivityPanel.vue'
import KPIBar from './KPIBar.vue'
import PWAControls from './PWAControls.vue'
import { isModuleVisible } from '@/utils/companyModules'

const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const { t } = useI18n()

const props = defineProps({
  agents: Array
})

const emit = defineEmits(['agentClicked'])

/** Estado backend/BD desde GET /api/v1/health/detailed (sin números inventados). */
const backendHealthLabel = ref('…')
const backendHealthDetail = ref('API / BD')

const selectedAgent = ref(null)
const currentView = ref('dashboard')
const sidebarOpen = ref(false)

// Settings
const notificationSettings = ref({
  email: true,
  push: true,
  agentStatus: false
})

const closeSidebarOnMobile = () => {
  // Cerrar sidebar en móvil después de seleccionar una opción
  if (window.innerWidth <= 768) {
    sidebarOpen.value = false
  }
}

const goToAdmin = () => {
  router.push('/admin')
}

// Navegar al TPV
const goToTPV = () => {
  router.push('/tpv')
}

// Navegar a Control Horario
const goToControlHorario = () => {
  router.push('/control-horario')
}

const goToOfficeCrm = () => {
  router.push('/office-crm')
}

const goToInsurance = () => {
  router.push('/insurance')
}

// Navegar a Nóminas
const goToPayroll = () => {
  router.push('/payroll')
}

const goToUserSettings = () => {
  router.push('/settings')
}

// Settings handlers
const handleGenerateApiKey = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const api = (await import('@/services/api')).default
    const data = await api.post('/api/v1/api-keys', undefined, token)
    const apiKey = data.api_key || data.key
    if (apiKey) {
      await navigator.clipboard.writeText(apiKey)
      alert(`✅ Clave API generada y copiada al portapapeles\n\nClave: ${apiKey}\n\n⚠️ Guarda esta clave en un lugar seguro. No se mostrará de nuevo.`)
    } else {
      alert('⚠️ Función disponible próximamente')
    }
  } catch (error) {
    console.error('Error generando API key:', error)
    alert('⚠️ Función disponible próximamente')
  }
}

const handleExportData = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    // Para export, necesitamos usar request directamente para obtener blob
    const api = (await import('@/services/api')).default
    const url = api.baseURL ? `${api.baseURL}/api/v1/user/export` : '/api/v1/user/export'
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.ok) {
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `zeus-export-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(blobUrl)
      document.body.removeChild(a)
      alert('✅ Datos exportados correctamente')
    } else {
      // Fallback: exportar datos locales
      const localData = {
        user: authStore.user,
        settings: {
          notifications: notificationSettings.value,
          app: { ...settingsStore.settings },
        },
        exportedAt: new Date().toISOString()
      }
      const dataStr = JSON.stringify(localData, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `zeus-export-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      alert('✅ Datos exportados correctamente (datos locales)')
    }
  } catch (error) {
    console.error('Error exportando datos:', error)
    // Fallback: exportar datos locales
    const localData = {
      user: authStore.user,
      settings: {
        notifications: notificationSettings.value,
        app: { ...settingsStore.settings },
      },
      exportedAt: new Date().toISOString()
    }
    const dataStr = JSON.stringify(localData, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `zeus-export-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    alert('✅ Datos exportados correctamente (datos locales)')
  }
}

// Métricas reales desde backend
const dashboardMetrics = ref({
  totalInteractions: 0,
  avgResponseTime: '0.0s',
  costSavings: '$0',
  successRate: '0%',
  interactionsTrend: '0%',
  responseTrend: '0%',
  savingsTrend: '0%',
  successTrend: '0%'
})

const executiveAnalytics = ref({
  agents: 6,
  tasks24h: 0,
  alerts: 0,
  automations: 0,
  efficiency: 0,
  system: 'unknown',
})

const applyExecutiveAnalytics = (data) => {
  if (!data) return
  const ex = data.executive || null
  if (!ex) return
  executiveAnalytics.value = {
    agents: ex.agents ?? 6,
    tasks24h: ex.tasks24h ?? 0,
    alerts: ex.alerts ?? 0,
    automations: ex.automations ?? 0,
    efficiency: ex.efficiency ?? 0,
    system: ex.system ?? 'unknown',
  }
}

const financialMetrics = ref({
  totalRevenue: 0,
  salesCount: 0,
  avgTicket: 0,
  activeCustomers: 0,
  cmrPayments: 0,
  tpvSales: 0,
})

const salesByDay = ref([])

const maxSalesDayTotal = computed(() => {
  const vals = salesByDay.value.map((b) => Number(b.total) || 0)
  return vals.length ? Math.max(...vals) : 0
})

function barHeight(total) {
  const max = maxSalesDayTotal.value
  if (!max) return 0
  return Math.max(8, Math.round((Number(total) / max) * 100))
}

// Módulos disponibles (desde endpoint unificado)
// Inicializar con valores por defecto: superusuarios tienen acceso completo
const availableModules = ref({
  tpv: false,
  control_horario: false,
  crm: false,
  payroll: false,
  dashboard: true,
  analytics: false,
  agents: true,
  admin: false,
  settings: true,
})

// Computed para verificar si el usuario es admin (reactivo) - múltiples formas de verificación
const isAdmin = computed(() => {
  const isAdmin1 = authStore.isAdmin || false
  const isAdmin2 = authStore.user?.is_superuser || false
  return isAdmin1 || isAdmin2
})

  // Empleado: solo TPV + control horario; sin nóminas ni admin
  const isEmployee = computed(() => {
    const u = authStore.user
    return u && typeof u === 'object' && 'role' in u && u.role === 'employee'
  })

const moduleOpts = computed(() => ({
  isSuperuser: isAdmin.value,
  isEmployee: isEmployee.value,
}))

const mergedModules = computed(() => {
  const fromAuth = authStore.modules || {}
  const fromMetrics = availableModules.value || {}
  return {
    dashboard: true,
    settings: true,
    agents: true,
    analytics: !!(fromAuth.analytics || fromMetrics.analytics),
    tpv: !!(fromAuth.tpv || fromMetrics.tpv),
    control_horario: !!(fromAuth.control_horario || fromMetrics.control_horario),
    crm: !!(fromAuth.crm || fromMetrics.crm),
    payroll: !!(fromAuth.payroll || fromMetrics.payroll),
    admin: !!(fromAuth.admin || fromMetrics.admin),
  }
})

function showModule(key) {
  return isModuleVisible(mergedModules.value, key, moduleOpts.value)
}

const loadBackendHealth = async () => {
  try {
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/health/detailed').catch(() => null)
    if (!data) {
      backendHealthLabel.value = '!'
      backendHealthDetail.value = 'Sin diagnóstico'
      return
    }
    const ok =
      data?.status === 'healthy' &&
      (data?.database === 'healthy' || String(data?.database || '').startsWith('healthy'))
    backendHealthLabel.value = ok ? 'OK' : '!'
    backendHealthDetail.value = ok ? 'API + BD' : 'Revisar BD'
  } catch {
    backendHealthLabel.value = '!'
    backendHealthDetail.value = 'Sin diagnóstico'
  }
}

// Cargar datos unificados del dashboard desde endpoint unificado
const loadDashboardMetrics = async () => {
  try {
    if (!authStore.getToken?.() && !authStore.token) {
      console.warn('⚠️ No hay token, no se pueden cargar métricas')
      return
    }
    await authStore.ensureAccessTokenFresh(300)

    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/metrics/summary?days=30').catch(() => null)
    if (!data) return
    
    if (data.success && data.metrics) {
      // Actualizar métricas
      dashboardMetrics.value = {
        totalInteractions: data.metrics.total_interactions || 0,
        avgResponseTime: data.metrics.avg_response_time || '0.0s',
        costSavings: data.metrics.cost_savings || '$0',
        successRate: data.metrics.success_rate || '0%',
        interactionsTrend: data.metrics.interactions_trend || '0%',
        responseTrend: data.metrics.response_trend || '0%',
        savingsTrend: data.metrics.savings_trend || '0%',
        successTrend: data.metrics.success_trend || '0%'
      }

      if (data.company_type) {
        authStore.companyType = data.company_type
      }
      if (data.available_modules) {
        availableModules.value = { ...availableModules.value, ...data.available_modules }
        authStore.applyProfileModules({
          company_type: data.company_type,
          modules: data.available_modules,
        })
      }

      if (data.analytics) {
        applyAnalyticsPayload(data.analytics)
      } else if (data.metrics?.total_revenue != null) {
        applyAnalyticsPayload({
          success: true,
          financial: {
            total_revenue: data.metrics.total_revenue,
            sales_count: data.metrics.sales_count,
            avg_ticket: data.metrics.avg_ticket,
            cmr_payments_count: data.metrics.cmr_payments_count,
            tpv_sales_count: data.metrics.tpv_sales_count,
          },
          customers: { active_total: data.metrics.active_customers },
          sales_by_day: data.analytics?.sales_by_day || [],
        })
      }

      applyExecutiveAnalytics(data)

      console.log('✅ Dashboard unificado cargado:', {
        metrics: dashboardMetrics.value,
        executive: executiveAnalytics.value,
        modules: availableModules.value,
        isSuperuser: data.user?.is_superuser
      })
    } else {
      console.warn('⚠️ Respuesta del servidor sin datos válidos:', data)
    }
  } catch (error) {
    console.error('❌ Error cargando dashboard unificado:', error)
    // Usar valores por defecto en caso de error
    // Para superusuarios, siempre mostrar TPV, Control Horario y Admin
    const isSuperuser = authStore.isAdmin || authStore.user?.is_superuser || false
    if (isSuperuser) {
      availableModules.value.tpv = true
      availableModules.value.control_horario = true
      availableModules.value.admin = true
      console.log('✅ Habilitando módulos por defecto para superusuario (error handler)')
    }
  }
}

const applyAnalyticsPayload = (data) => {
  if (!data?.success) return
  const fin = data.financial || data.metrics || {}
  financialMetrics.value = {
    totalRevenue: Number(fin.total_revenue) || 0,
    salesCount: Number(fin.sales_count) || 0,
    avgTicket: Number(fin.avg_ticket) || 0,
    activeCustomers: Number(data.customers?.active_total ?? fin.active_customers) || 0,
    cmrPayments: Number(fin.cmr_payments_count) || 0,
    tpvSales: Number(fin.tpv_sales_count) || 0,
  }
  salesByDay.value = Array.isArray(data.sales_by_day) ? data.sales_by_day : []
}

const loadFinancialAnalytics = async () => {
  try {
    if (!authStore.getToken?.() && !authStore.token) return
    await authStore.ensureAccessTokenFresh(300)
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/analytics/summary?days=30').catch(() => null)
    if (data) {
      applyAnalyticsPayload(data)
      applyExecutiveAnalytics(data)
    }
  } catch (error) {
    console.error('❌ Error cargando analytics financieros:', error)
  }
}

// Cargar configuración guardada
const loadSavedSettings = () => {
  try {
    const saved = localStorage.getItem('zeus_notification_settings')
    if (saved) {
      notificationSettings.value = { ...notificationSettings.value, ...JSON.parse(saved) }
    }
  } catch (error) {
    console.error('Error cargando settings:', error)
  }
}

// Guardar configuración
const saveNotificationSettings = () => {
  try {
    localStorage.setItem('zeus_notification_settings', JSON.stringify(notificationSettings.value))
  } catch (error) {
    console.error('Error guardando settings:', error)
  }
}

// Watch para guardar settings automáticamente (al nivel superior, no en onMounted)
watch(notificationSettings, () => {
  saveNotificationSettings()
}, { deep: true })

// Función para actualizar módulos basado en permisos de superusuario
const updateModulesForSuperuser = () => {
  const isAdmin = authStore.isAdmin || authStore.user?.is_superuser || false
  if (isAdmin) {
    availableModules.value.tpv = true
    availableModules.value.control_horario = true
    availableModules.value.admin = true
    console.log('✅ Módulos habilitados para superusuario:', {
      isAdmin: isAdmin,
      authStoreIsAdmin: authStore.isAdmin,
      userIsSuperuser: authStore.user?.is_superuser,
      modules: availableModules.value
    })
  }
}

// Watcher para actualizar módulos cuando cambie el estado de admin
watch(() => authStore.isAdmin, (isAdmin) => {
  if (isAdmin) {
    updateModulesForSuperuser()
  }
}, { immediate: true })

// Watcher para cuando cambie el usuario
watch(() => authStore.user?.is_superuser, (isSuperuser) => {
  if (isSuperuser) {
    updateModulesForSuperuser()
  }
}, { immediate: true })

// Watcher para isAdmin computed
watch(isAdmin, (isAdmin) => {
  if (isAdmin) {
    updateModulesForSuperuser()
  }
}, { immediate: true })

const resetDashboardSessionState = () => {
  dashboardMetrics.value = {
    totalInteractions: 0,
    avgResponseTime: '0.0s',
    costSavings: '$0',
    successRate: '0%',
    interactionsTrend: '0%',
    responseTrend: '0%',
    savingsTrend: '0%',
    successTrend: '0%',
  }
  executiveAnalytics.value = {
    agents: 6,
    tasks24h: 0,
    alerts: 0,
    automations: 0,
    efficiency: 0,
    system: 'unknown',
  }
  financialMetrics.value = {
    totalRevenue: 0,
    salesCount: 0,
    avgTicket: 0,
    activeCustomers: 0,
    cmrPayments: 0,
    tpvSales: 0,
  }
  salesByDay.value = []
}

watch(
  () => authStore.user?.id,
  async (newId, oldId) => {
    if (!newId || newId === oldId) return
    resetDashboardSessionState()
    updateModulesForSuperuser()
    await refreshDashboardData()
  },
)

watch(currentView, (view) => {
  if (view === 'analytics') {
    loadFinancialAnalytics()
  }
  syncExecutiveBodyClass()
})

const syncExecutiveBodyClass = () => {
  const active = currentView.value === 'dashboard'
  document.body.classList.toggle('dashboard-executive-mode', active)
  document.documentElement.classList.toggle('dashboard-executive-mode', active)
}

const DASHBOARD_POLL_MS = 30000
let dashboardPollTimer = null
let pollTick = 0

const refreshDashboardData = async () => {
  pollTick += 1
  await loadDashboardMetrics()
  if (currentView.value === 'analytics') {
    await loadFinancialAnalytics()
  }
  if (pollTick % 2 === 0) {
    await loadBackendHealth()
    await loadAgentsActivities()
    await loadAgentsStatus()
  }
}

// Cargar al montar y refrescar periódicamente (un solo interval, cleanup en unmount)
onMounted(async () => {
  // Inicializar authStore si aún no tiene el usuario cargado. OJO:
  // authStore.isAuthenticated solo indica que hay un token válido (ver
  // stores/auth.ts), no que authStore.user ya se haya rellenado desde
  // /auth/me — comprobar isAuthenticated aquí hacía que, en una recarga
  // directa con sesión ya guardada, nunca se llamara a initialize() y
  // authStore.user se quedara en null para siempre en esta vista.
  if (!authStore.user && authStore.initialize) {
    console.log('🔄 Inicializando authStore...')
    await authStore.initialize()
  }
  // Empleado: ir directo al TPV (comandero)
  if (isEmployee.value) {
    router.push('/tpv')
    return
  }

  syncExecutiveBodyClass()

  // Debug: Verificar estado de authStore
  console.log('🔍 Estado inicial de authStore:', {
    isAdmin: authStore.isAdmin,
    isAuthenticated: authStore.isAuthenticated,
    user: authStore.user,
    userIsSuperuser: authStore.user?.is_superuser
  })
  
  // Asegurar que superusuarios tengan acceso completo desde el inicio
  updateModulesForSuperuser()
  
  loadSavedSettings()
  await refreshDashboardData()
  // Estado online/offline real inmediato, sin esperar al primer poll
  // (refreshDashboardData solo lo refresca cuando pollTick es par).
  await loadAgentsStatus()

  dashboardPollTimer = window.setInterval(() => {
    void refreshDashboardData()
  }, DASHBOARD_POLL_MS)
  
  // Verificar después de múltiples delays para asegurar que authStore esté listo.
  // Antes esto referenciaba shouldShowTPV/shouldShowControlHorario/shouldShowAdmin,
  // que no existían en ningún sitio del componente: el ReferenceError se lanzaba
  // al construir el objeto del console.log, ANTES de llegar a llamar a
  // updateModulesForSuperuser() — es decir, los 3 reintentos estaban muertos
  // desde siempre. Se usa showModule(), la función real que decide qué ve el
  // usuario, para que el log refleje el estado real y el reintento se ejecute.
  const logModuleVisibilityState = (label) => {
    console.log(`🔍 Estado de módulos (${label}):`, {
      isAdmin: authStore.isAdmin,
      userIsSuperuser: authStore.user?.is_superuser,
      user: authStore.user,
      showTPV: showModule('tpv'),
      showControlHorario: showModule('control_horario'),
      showAdmin: showModule('admin'),
    })
  }

  setTimeout(() => {
    logModuleVisibilityState('100ms')
    updateModulesForSuperuser()
  }, 100)

  setTimeout(() => {
    logModuleVisibilityState('500ms')
    updateModulesForSuperuser()
  }, 500)

  setTimeout(() => {
    logModuleVisibilityState('1000ms')
    updateModulesForSuperuser()
  }, 1000)
})

onUnmounted(() => {
  if (dashboardPollTimer != null) {
    clearInterval(dashboardPollTimer)
    dashboardPollTimer = null
  }
  document.body.classList.remove('dashboard-executive-mode')
  document.documentElement.classList.remove('dashboard-executive-mode')
})

// NOTA sobre `beta`: no existe ningún campo real en el backend (ver
// GET /api/v1/agents/status → AGENT_REGISTRY en
// backend/app/api/v1/endpoints/agents.py) que marque un agente como
// "beta". Es una decisión de producto puramente informativa, no una
// condición de negocio, así que se marca a mano solo en ZEUS CORE
// (el orquestador es el componente más nuevo y menos rodado del
// núcleo). Si en el futuro el backend expone un campo real de
// versión/estabilidad por agente, este flag debe leerse de ahí.
const agentsData = ref([
  {
    name: 'ZEUS CORE',
    role: 'Supreme Orchestrator',
    image: '/images/avatars/Zeus-avatar.jpg',
    activities_24h: 0,
    status: 'loading',
    beta: true
  },
  {
    name: 'PERSEO',
    role: 'Growth Strategist',
    image: '/images/avatars/Perseo-avatar.jpg',
    activities_24h: 0,
    status: 'loading'
  },
  {
    name: 'RAFAEL',
    role: 'Fiscal Guardian',
    image: '/images/avatars/Rafael-avatar.jpg',
    activities_24h: 0,
    status: 'loading'
  },
  {
    name: 'THALOS',
    role: 'Cybersecurity Defender',
    image: '/images/avatars/Thalos-avatar.jpg',
    activities_24h: 0,
    status: 'loading'
  },
  {
    name: 'JUSTICIA',
    role: 'Legal & GDPR Advisor',
    image: '/images/avatars/Justicia-avatar.jpg',
    activities_24h: 0,
    status: 'loading'
  },
  {
    name: 'AFRODITA',
    role: 'HR & Logistics Manager',
    image: '/images/avatars/Afrodita-avatar.jpg',
    activities_24h: 0,
    status: 'loading'
  }
])

// Estado real online/idle/offline por agente — GET /api/v1/agents/status
// (mismo endpoint que ya consumen OlymposDashboard.vue y KpiAgentsView.vue,
// calculado desde agent_activities, no un valor fijo).
const loadAgentsStatus = async () => {
  if (!authStore.getToken?.() && !authStore.token) return
  try {
    await authStore.ensureAccessTokenFresh(300)
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/agents/status')
    const backendAgents = data?.agents || {}
    agentsData.value.forEach((agent) => {
      const info = backendAgents[agent.name]
      agent.status = info?.status || 'offline'
    })
  } catch (error) {
    console.error('Error cargando estado de agentes:', error)
  }
}

const AGENT_STATUS_LABELS = {
  online: 'En línea',
  idle: 'Inactivo',
  offline: 'Desconectado',
  loading: 'Cargando…'
}

const agentStatusLabel = (status) => AGENT_STATUS_LABELS[status] || AGENT_STATUS_LABELS.offline

// Clase de tratamiento visual por agente sobre el avatar real (mismo
// asset, sin arte nuevo — ver AUDIT_REDISENO_TARJETAS_AGENTE.md para el
// porqué de cada tratamiento).
const AGENT_AVATAR_FX = {
  PERSEO: 'avatar-fx-perseo',
  RAFAEL: 'avatar-fx-rafael',
  THALOS: 'avatar-fx-thalos',
  JUSTICIA: 'avatar-fx-justicia',
  AFRODITA: 'avatar-fx-afrodita'
}

const agentAvatarFx = (agentName) => AGENT_AVATAR_FX[agentName] || ''

const zeusCoreAgent = computed(() =>
  agentsData.value.find((a) => a.name.includes('ZEUS')) || agentsData.value[0]
)

const executiveGridAgents = computed(() =>
  agentsData.value.filter((a) => !a.name.includes('ZEUS'))
)

const tasksRunning24h = computed(() =>
  agentsData.value.reduce((sum, a) => sum + (Number(a.activities_24h) || 0), 0)
)

const executiveKpis = computed(() => {
  const ex = executiveAnalytics.value
  const systemOk = ex.system === 'healthy' && backendHealthLabel.value === 'OK'
  return [
    {
      key: 'agents_active',
      label: 'Agentes',
      value: ex.agents || agentsData.value.length,
      icon: '🤖',
      route: '/agents',
    },
    {
      key: 'tasks_running',
      label: 'Tareas 24h',
      value: ex.tasks24h ?? tasksRunning24h.value,
      icon: '⚡',
      route: '/analytics/tasks',
    },
    {
      key: 'efficiency',
      label: 'Eficiencia',
      value: `${ex.efficiency ?? 0}%`,
      icon: '📈',
      route: '/analytics/efficiency',
    },
    {
      key: 'alerts',
      label: 'Alertas',
      value: ex.alerts ?? 0,
      icon: '🔔',
      route: '/alerts',
    },
    {
      key: 'automations',
      label: 'Automatiz.',
      value: ex.automations ?? 0,
      icon: '⚙️',
      route: '/automations',
    },
    {
      key: 'system_health',
      label: 'Sistema',
      value: systemOk ? 'OK' : '!',
      icon: '💚',
      route: '/system-health',
    },
  ]
})

// Cargar actividades reales de cada agente (últimas 24h) — requiere JWT (igual que /metrics/summary)
const loadAgentsActivities = async () => {
  if (!authStore.getToken?.() && !authStore.token) {
    console.warn('⚠️ No hay token, no se pueden cargar actividades de agentes')
    return
  }
  await authStore.ensureAccessTokenFresh(300)
  const api = (await import('@/services/api')).default
  for (const agent of agentsData.value) {
    try {
      const agentName = agent.name.split(' ')[0].toUpperCase()
      const data = await api.get(`/api/v1/activities/${agentName}?days=1`)
      if (data.success) {
        agent.activities_24h = data.total_activities || 0
      }
    } catch (error) {
      console.error(`Error cargando actividades de ${agent.name}:`, error)
      agent.activities_24h = 0
    }
  }
}

const selectAgent = (agent) => {
  selectedAgent.value = agent
  emit('agentClicked', agent)
}

const chatWith = (agent) => {
  selectedAgent.value = agent
  emit('agentClicked', agent)
}

const closeAgentPanel = () => {
  selectedAgent.value = null
}

const handleAgentPanelKeydown = (event) => {
  if (event.key === 'Escape' && selectedAgent.value) {
    closeAgentPanel()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleAgentPanelKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleAgentPanelKeydown)
})
</script>

<style scoped>
.dashboard-profesional {
  position: relative;
  display: flex;
  height: 100vh;
  min-height: 100vh;
  max-height: 100vh;
  background-image: var(--zeus-bg);
  color: var(--zeus-text);
  font-family: var(--zeus-font-sans);
  overflow: hidden;
  box-sizing: border-box;
}

/* Grano/ruido del fondo de bandas metálicas — obligatorio en toda
   página, sin excepción. */
.dashboard-profesional::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
  z-index: 0;
}

.dashboard-profesional > * {
  position: relative;
  z-index: 1;
}

/* SIDEBAR OVERLAY (solo móvil) */
.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.4);
  z-index: 998;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}

.sidebar-overlay.active {
  opacity: 1;
  pointer-events: all;
}

/* SIDEBAR */
.sidebar-dark {
  width: 280px;
  background: var(--zeus-surface);
  border-right: 1px solid var(--zeus-border);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease;
  z-index: 999;
}

.logo-section {
  margin-bottom: 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.logo-section .logo-zeus-img {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

.logo-section h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: var(--zeus-text-muted);
  font-size: 12px;
  margin: 4px 0 0;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  border-radius: var(--zeus-radius-sm);
  color: var(--zeus-text-secondary);
  cursor: pointer;
  transition: background var(--zeus-transition), color var(--zeus-transition);
  font-size: 14px;
  font-weight: 500;
}

.nav-item:hover {
  background: var(--zeus-bg-subtle);
  color: var(--zeus-text);
}

.nav-item.active {
  background: var(--zeus-accent-soft);
  color: var(--zeus-accent);
}

.nav-item.admin-btn {
  margin-top: 8px;
  background: var(--zeus-accent-2-soft);
  border: 1px solid rgba(139, 92, 246, 0.25);
  color: #7c3aed;
}

.nav-item.admin-btn:hover {
  background: rgba(124, 58, 237, 0.14);
  color: #7c3aed;
  border-color: rgba(139, 92, 246, 0.4);
}

.nav-item.tpv-nav-btn {
  background: var(--zeus-success-soft);
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #0d9668;
}

.nav-item.tpv-nav-btn:hover {
  background: rgba(16, 185, 129, 0.16);
  color: #0d9668;
  border-color: rgba(16, 185, 129, 0.4);
}

.nav-item.control-horario-nav-btn {
  background: var(--zeus-info-soft);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: #2563eb;
}

.nav-item.control-horario-nav-btn:hover {
  background: rgba(59, 130, 246, 0.16);
  color: #2563eb;
  border-color: rgba(59, 130, 246, 0.4);
}

.icon {
  font-size: 18px;
}

.metrics-mini {
  display: flex;
  gap: 16px;
  padding-top: 24px;
  border-top: 1px solid var(--zeus-border);
}

.metric-item {
  flex: 1;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--zeus-accent);
}

.metric-label {
  font-size: 11px;
  color: var(--zeus-text-muted);
  margin-top: 4px;
}

/* BOTÓN HAMBURGUESA (oculto en desktop) */
.hamburger-btn {
  display: none;
  flex-direction: column;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  margin-right: 16px;
}

.hamburger-btn span {
  display: block;
  width: 24px;
  height: 2px;
  background: var(--zeus-text);
  transition: all 0.3s;
}

/* MAIN CONTENT */
.main-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 32px 40px;
  box-sizing: border-box;
}

.main-content--dashboard {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px;
  gap: 12px;
}

.zeus-dashboard {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  box-sizing: border-box;
}

/* EXECUTIVE PANEL MODE */
.dashboard-executive {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 0;
  position: relative;
}

.executive-hamburger {
  display: none;
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 10;
}

.executive-pwa-bar {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 11;
  max-width: calc(100% - 48px);
}

.executive-section {
  flex-shrink: 0;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.executive-section--kpi {
  flex: 0 0 12%;
  max-height: 12%;
  min-height: 52px;
}

.executive-section--zeus {
  flex: 0 0 23%;
  max-height: 23%;
  min-height: 72px;
}

.zeus-core-highlight {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.zeus-core-card {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 720px;
  height: 100%;
  padding: 10px 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.06) 0%, rgba(139, 92, 246, 0.05) 100%), var(--zeus-surface);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: var(--zeus-radius-lg);
  box-shadow: var(--zeus-shadow);
  box-sizing: border-box;
  cursor: pointer;
  transition: box-shadow var(--zeus-transition), border-color var(--zeus-transition);
}

.zeus-core-card:hover {
  box-shadow: var(--zeus-shadow-md);
  border-color: rgba(59, 130, 246, 0.4);
}

.zeus-core-avatar-container {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  border: none;
  background: none;
}

.zeus-core-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(59, 130, 246, 0.6);
  flex-shrink: 0;
}

.zeus-core-info {
  min-width: 0;
  flex: 1;
  text-align: left;
}

.zeus-core-interact {
  margin-top: 12px;
}

.zeus-core-name {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--zeus-text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.zeus-core-role {
  margin: 2px 0 8px;
  font-size: 12px;
  color: var(--zeus-text-secondary);
}

.zeus-core-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
}

.zeus-core-status {
  font-weight: 600;
}

.zeus-core-status.online {
  color: #10b981;
}

.zeus-core-status.degraded {
  color: #f59e0b;
}

.zeus-core-activity {
  color: var(--zeus-text-muted);
}

.executive-agents-grid {
  flex: 1;
  min-height: 0;
  height: auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  color: var(--zeus-text);
}

.breadcrumb {
  color: var(--zeus-text-muted);
  font-size: 14px;
  margin: 4px 0 0;
}

.status-badge {
  padding: 8px 16px;
  border-radius: var(--zeus-radius-full);
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
}

.status-badge.degraded {
  background: var(--zeus-warning-soft);
  color: #b45309;
  border-color: rgba(245, 158, 11, 0.3);
}

.status-badge.online {
  background: var(--zeus-success-soft);
  color: #0d9668;
  border-color: rgba(16, 185, 129, 0.25);
}

/* RESPONSIVE - MÓVIL Y TABLET */
@media (max-width: 1024px) {
  /* Mostrar overlay */
  .sidebar-overlay {
    display: block;
  }

  /* Sidebar oculto por defecto en móvil */
  .sidebar-dark {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transform: translateX(-100%);
    z-index: 999;
    box-shadow: var(--zeus-shadow-lg);
  }

  /* Sidebar visible cuando está abierto */
  .sidebar-dark.open {
    transform: translateX(0);
  }

  /* Mostrar botón hamburguesa en móvil */
  .hamburger-btn {
    display: flex;
  }
  
  /* Animación del botón hamburguesa cuando está abierto */
  .hamburger-btn.active span:nth-child(1) {
    transform: rotate(45deg) translate(5px, 5px);
  }
  
  .hamburger-btn.active span:nth-child(2) {
    opacity: 0;
  }
  
  .hamburger-btn.active span:nth-child(3) {
    transform: rotate(-45deg) translate(7px, -6px);
  }

  /* Ajustar main content */
  .main-content {
    padding: 16px 20px;
  }

  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-left {
    width: 100%;
  }

  .header-left h2 {
    font-size: 24px;
  }

  .header-right {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  
  .pwa-install-btn {
    padding: 8px 16px;
    background: rgba(59, 130, 246, 0.9);
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 20px;
    color: #fff;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.3s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  
.pwa-install-btn:hover {
  background: rgba(59, 130, 246, 0.7);
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.pwa-clear-cache-link {
  padding: 6px 12px;
  background: rgba(255, 165, 0, 0.12);
  border: 1px solid rgba(255, 165, 0, 0.35);
  border-radius: 12px;
  color: #ffa500;
  font-size: 11px;
  font-weight: 500;
  text-decoration: underline;
  white-space: nowrap;
}

.pwa-clear-cache-link:hover {
  background: rgba(255, 165, 0, 0.22);
}

.pwa-debug-info {
  padding: 6px 12px;
  background: rgba(255, 165, 0, 0.15);
  border: 1px solid rgba(255, 165, 0, 0.3);
  border-radius: 12px;
  color: #ffa500;
  font-size: 11px;
  font-weight: 500;
  cursor: help;
}

  /* Agents grid más compacto en móvil */
  .executive-pwa-bar {
    top: 40px;
    right: 4px;
    left: 4px;
    max-width: none;
  }

  .executive-hamburger {
    display: flex;
  }

  .executive-section--kpi {
    flex: 0 0 auto;
    max-height: none;
    min-height: 88px;
    padding-top: 36px;
  }

  .executive-section--zeus {
    flex: 0 0 auto;
    max-height: none;
    min-height: 100px;
  }

  .main-content--dashboard {
    overflow-y: auto;
  }

  .dashboard-executive {
    min-height: auto;
  }

  .executive-agents-grid {
    /* Tablet: 2 columnas, igual que desktop y que móvil — la rejilla de
       tarjetas de agente se mantiene siempre en 2 columnas en este
       breakpoint intermedio en vez de colapsar a 1 sola (con solo 5
       tarjetas, 1 columna desperdicia el ancho disponible). */
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: none;
    grid-auto-rows: minmax(150px, auto);
    height: auto;
    max-height: none;
    overflow-y: auto;
    flex: 1;
  }

  .agent-card--executive {
    min-height: 220px;
  }

  .agent-overlay {
    padding: 24px 12px;
    align-items: flex-start;
  }

  .agent-panel-container {
    width: 100%;
    max-height: none;
    gap: 12px;
  }

  .btn-close-panel {
    position: sticky;
    top: 0;
    margin-left: auto;
  }
}

/* AGENTS GRID — 2 columnas (5 tarjetas de agente sin ZEUS CORE, que
   tiene su propia fila destacada arriba). Antes era 3×2: se reduce a
   2 columnas para dar más aire a cada tarjeta (avatar + estado real +
   badge), a costa de una fila extra que cabe con scroll vertical
   dentro de la sección en vez de forzar cada tarjeta a encogerse. */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-auto-rows: minmax(0, 1fr);
  gap: 10px;
  height: 100%;
  width: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.agent-card {
  height: 100%;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: var(--zeus-surface);
  border: 1px solid var(--zeus-border);
  border-radius: var(--zeus-radius);
  padding: 10px;
  cursor: pointer;
  transition: transform var(--zeus-transition), border-color var(--zeus-transition), box-shadow var(--zeus-transition);
  overflow: hidden;
  box-sizing: border-box;
  box-shadow: var(--zeus-shadow-sm);
}

.agent-card:hover {
  transform: translateY(-3px);
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: var(--zeus-shadow-md);
}

.agent-card--executive .avatar-container {
  width: 64px;
  height: 64px;
}

.agent-card--executive .agent-name {
  font-size: 14px;
}

.agent-card--executive .agent-role {
  font-size: 11px;
}

.agent-card--executive .stat-label,
.agent-card--executive .stat-value {
  font-size: 10px;
}

.agent-card--executive .btn-interact {
  height: 28px;
  min-height: 28px;
  padding: 0 12px;
  font-size: 11px;
}

.avatar-container {
  position: relative;
  width: 80px;
  height: 80px;
  margin: auto;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, transparent 70%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid rgba(59, 130, 246, 0.18);
  transition: all 0.3s;
}

.agent-card:hover .avatar-container {
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.08);
}

.avatar-image {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.agent-card:hover .avatar-image {
  transform: scale(1.1);
}

/* ---- Tratamiento de dinamismo por agente sobre la MISMA foto real ----
   No hay generación de ilustraciones nuevas disponible en este entorno
   (decisión ya acordada con el usuario): se aplican transformaciones
   CSS sutiles sobre el asset ya existente para sugerir personalidad,
   nunca desfigurando la foto. Ver AUDIT_REDISENO_TARJETAS_AGENTE.md. */

/* PERSEO — atlético/dinámico: encuadre inclinado + líneas de velocidad
   que se desvanecen desde el borde izquierdo (sugiere movimiento hacia
   la derecha, sin animación permanente). */
.avatar-container.avatar-fx-perseo .avatar-image {
  transform: rotate(-5deg) scale(1.14);
  object-position: 55% 30%;
}

.agent-card:hover .avatar-container.avatar-fx-perseo .avatar-image {
  transform: rotate(-5deg) scale(1.2);
}

.avatar-container.avatar-fx-perseo::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: repeating-linear-gradient(
    100deg,
    transparent 0px, transparent 6px,
    rgba(255, 255, 255, 0.5) 6px, rgba(255, 255, 255, 0.5) 8px,
    transparent 8px, transparent 20px
  );
  -webkit-mask-image: linear-gradient(90deg, black 0%, transparent 40%);
  mask-image: linear-gradient(90deg, black 0%, transparent 40%);
}

/* RAFAEL — ejecutivo/sobrio: marco recto en vez del círculo genérico,
   sin inclinación, borde de un solo tono neutro (nada de gradiente). */
.avatar-container.avatar-fx-rafael {
  border-radius: 10px;
  border-color: rgba(82, 96, 122, 0.45);
}

.avatar-container.avatar-fx-rafael .avatar-image {
  border-radius: 7px;
}

.agent-card:hover .avatar-container.avatar-fx-rafael {
  border-color: rgba(82, 96, 122, 0.7);
}

/* THALOS — defensivo: aura/anillo frío estático (sin pulso: un escudo
   no parpadea), en vez del anillo índigo genérico. */
.avatar-container.avatar-fx-thalos {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 5px rgba(59, 130, 246, 0.14), 0 0 18px rgba(59, 130, 246, 0.28);
}

.agent-card:hover .avatar-container.avatar-fx-thalos {
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 0 7px rgba(59, 130, 246, 0.18), 0 0 24px rgba(59, 130, 246, 0.4);
}

/* JUSTICIA — movimiento/doble exposición: una segunda copia de la misma
   foto, desplazada y difuminada detrás, como un "ghost trail". */
.avatar-ghost {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.4;
  filter: blur(2px) grayscale(0.15);
  transform: translateX(-7px) scale(1.06);
}

/* AFRODITA — cercana/cálida: aura suave en tono ámbar (token ya
   existente --zeus-warning, sin introducir un color nuevo). */
.avatar-container.avatar-fx-afrodita {
  border-color: rgba(245, 158, 11, 0.35);
  box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.1);
}

.agent-card:hover .avatar-container.avatar-fx-afrodita {
  border-color: rgba(245, 158, 11, 0.6);
  box-shadow: 0 0 0 7px rgba(245, 158, 11, 0.16);
}

/* ---- Indicador de estado real (online/idle/offline) ---- */
.status-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  z-index: 3;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--zeus-surface, #fff);
  background: #cbd5e1;
}

.status-dot.online {
  background: #10b981;
}

.status-dot.idle {
  background: #f59e0b;
}

.status-dot.offline {
  background: #94a3b8;
}

.status-dot.loading {
  background: #cbd5e1;
}

/* Pulso sutil solo cuando está realmente online — respeta
   prefers-reduced-motion (ver media query al final del bloque). */
.status-dot.online::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid #10b981;
  opacity: 0.55;
  animation: status-dot-pulse 1.8s ease-out infinite;
}

@keyframes status-dot-pulse {
  0% { transform: scale(0.55); opacity: 0.55; }
  100% { transform: scale(1.7); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot.online::after {
    animation: none;
    display: none;
  }
}

/* ---- Badge BETA (informativo de producto, ver comentario en <script>
   sobre por qué solo ZEUS CORE lo lleva hardcodeado) ---- */
.beta-badge {
  display: inline-block;
  padding: 2px 7px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--zeus-accent);
  background: var(--zeus-accent-soft);
  border-radius: var(--zeus-radius-full);
  line-height: 1.4;
}

.agent-name {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.agent-info {
  text-align: center;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 6px;
}

.agent-name {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
  color: var(--zeus-text);
}

.agent-role {
  color: var(--zeus-text-muted);
  font-size: 12px;
  margin: 0;
}

.agent-stats {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 6px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--zeus-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--zeus-text);
}

.status-active {
  color: #0d9668;
}

/* Texto del stat "Estado" en la tarjeta — coloreado según el estado
   real devuelto por GET /api/v1/agents/status (mismo criterio de color
   que el punto de estado del avatar). */
.status-online {
  color: #0d9668;
}

.status-idle {
  color: #b45309;
}

.status-offline {
  color: #64748b;
}

.status-loading {
  color: var(--zeus-text-muted);
}

/* Botón secundario: el Dashboard es una vista de selección entre 6
   agentes de igual jerarquía — ninguno de los 6 "Interactuar" es "el"
   botón primario de la vista (mismo criterio que el open-trigger del
   preview de referencia: un disparador que abre otra vista no es la
   acción de mayor jerarquía de ESTA vista). El gradiente vibrante queda
   reservado para la acción única de mayor jerarquía dentro de cada
   panel de agente ya abierto (ej. "Actualizar"). */
.btn-interact {
  padding: 8px 16px;
  background: #ffffff;
  border: 1px solid #D1D5DB;
  border-radius: var(--zeus-radius-sm);
  color: var(--zeus-text, #0f172a);
  font-weight: 600;
  cursor: pointer;
  box-shadow: none;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  align-self: center;
  flex-shrink: 0;
}

.btn-interact:hover {
  border-color: #9aa2af;
}

@media (prefers-reduced-motion: reduce) {
  .btn-interact {
    transition-duration: 1ms;
  }
}

/* AGENT ACTIVITY PANEL OVERLAY */
.agent-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 32px 24px;
  overflow-y: auto;
}

/* Modal animado — entrada/salida (240ms), backdrop en fade, panel con
   fade + escala + desplazamiento sutil. Easing distinto para entrada
   (desaceleración natural) y salida (aceleración) — sistema de motion
   compartido, ver tokens zeus-ease y zeus-dur en zeus-light-system.css.
   Ver .agent-modal-* más abajo para las clases que genera
   <Transition name="agent-modal">. */
.agent-modal-enter-active {
  transition: background-color var(--zeus-dur-modal, 240ms) var(--zeus-ease-enter, ease-out);
}

.agent-modal-leave-active {
  transition: background-color var(--zeus-dur-modal, 240ms) var(--zeus-ease-exit, ease-in);
}

.agent-modal-enter-active .agent-panel-container {
  transition: opacity var(--zeus-dur-modal, 240ms) var(--zeus-ease-enter, ease-out),
    transform var(--zeus-dur-modal, 240ms) var(--zeus-ease-enter, ease-out);
}

.agent-modal-leave-active .agent-panel-container {
  transition: opacity var(--zeus-dur-modal, 240ms) var(--zeus-ease-exit, ease-in),
    transform var(--zeus-dur-modal, 240ms) var(--zeus-ease-exit, ease-in);
}

.agent-modal-enter-from,
.agent-modal-leave-to {
  background-color: rgba(15, 23, 42, 0);
}

.agent-modal-enter-from .agent-panel-container,
.agent-modal-leave-to .agent-panel-container {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

/* Respeta la preferencia del sistema de reducir movimiento: sin escala
   ni desplazamiento, solo un fade casi instantáneo. */
@media (prefers-reduced-motion: reduce) {
  .agent-modal-enter-active,
  .agent-modal-leave-active,
  .agent-modal-enter-active .agent-panel-container,
  .agent-modal-leave-active .agent-panel-container {
    transition-duration: 1ms;
  }

  .agent-modal-enter-from .agent-panel-container,
  .agent-modal-leave-to .agent-panel-container {
    transform: none;
  }
}

.agent-panel-container {
  position: relative;
  width: min(95vw, 1600px);
  max-height: calc(100vh - 64px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
}


.btn-close-panel {
  align-self: flex-end;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 18px;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;
  z-index: 1;
}

.btn-close-panel:hover {
  background: rgba(255, 255, 255, 0.18);
  transform: scale(1.06);
}

.chat-panel {
  width: 600px;
  max-height: 80vh;
  background: #1a1f2e;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-agent-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.chat-avatar-mini {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid rgba(59, 130, 246, 0.5);
}

.chat-avatar-mini img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-agent-info h4 {
  margin: 0;
  font-size: 18px;
}

.chat-agent-info p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
}

.btn-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.chat-messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.message {
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 12px;
  max-width: 80%;
}

.agent-message {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.chat-input {
  display: flex;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-input input {
  flex: 1;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
}

.chat-input input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.btn-send {
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

/* ANALYTICS VIEW */
.analytics-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.stat-card {
  background: var(--zeus-surface);
  border: 1px solid var(--zeus-border);
  border-radius: var(--zeus-radius);
  padding: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  box-shadow: var(--zeus-shadow-sm);
}

.stat-icon {
  font-size: 32px;
  background: var(--zeus-accent-soft);
  padding: 12px;
  border-radius: var(--zeus-radius);
}

.stat-content h3 {
  font-size: 14px;
  color: var(--zeus-text-secondary);
  margin: 0 0 8px;
  font-weight: 500;
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  color: var(--zeus-text);
}

.stat-change {
  font-size: 13px;
  margin-top: 4px;
  display: inline-block;
}

.stat-change.positive {
  color: #0d9668;
}

.chart-placeholder {
  background: var(--zeus-surface);
  border: 1px solid var(--zeus-border);
  border-radius: var(--zeus-radius);
  padding: 32px;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--zeus-shadow-sm);
}

.chart-placeholder h3 {
  margin: 0 0 24px;
  font-size: 20px;
  color: var(--zeus-text);
}

.placeholder-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.icon-large {
  font-size: 64px;
  opacity: 0.4;
}

.placeholder-content p {
  color: var(--zeus-text-muted);
  font-size: 16px;
}

/* SETTINGS VIEW */
.settings-view {
  max-width: 1000px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.settings-card {
  background: var(--zeus-surface);
  border: 1px solid var(--zeus-border);
  border-radius: var(--zeus-radius);
  padding: 24px;
  box-shadow: var(--zeus-shadow-sm);
}

.settings-card h3 {
  margin: 0 0 20px;
  font-size: 18px;
  color: var(--zeus-text);
}

.settings-embed-hint {
  margin: 0 0 16px;
  font-size: 14px;
  color: var(--zeus-text-secondary);
  line-height: 1.45;
}

.settings-link {
  color: var(--zeus-accent);
  text-decoration: underline;
  cursor: pointer;
}

.settings-link:hover {
  color: var(--zeus-accent-hover);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--zeus-border);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  color: var(--zeus-text);
  font-size: 14px;
}

.setting-item input[type="checkbox"] {
  width: 44px;
  height: 24px;
  cursor: pointer;
}

.setting-item select {
  background: var(--zeus-surface);
  border: 1px solid var(--zeus-border);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--zeus-text);
  font-size: 14px;
  cursor: pointer;
}

.setting-item select option {
  background: var(--zeus-surface);
}

.btn-secondary {
  padding: 8px 16px;
  background: var(--zeus-accent-soft);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 6px;
  color: var(--zeus-accent);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(59, 130, 246, 0.4);
}

/* Mobile-only executive dashboard (≤768px) */
@media (max-width: 768px) {
  .main-content--dashboard {
    padding: 8px;
    padding-bottom: 20px;
    overflow-y: auto;
    overflow-x: hidden;
    flex: none;
    min-height: 0;
  }

  .dashboard-executive-root {
    height: 100vh;
    min-height: 100vh;
    overflow-y: auto;
    overflow-x: hidden;
    padding-bottom: 20px;
  }

  .zeus-dashboard,
  .dashboard-executive {
    height: auto;
    min-height: auto;
    overflow: visible;
    flex: none;
    gap: 8px;
    padding-bottom: 8px;
  }

  .executive-section--kpi,
  .executive-section--zeus {
    flex: none;
    max-height: none;
  }

  .executive-section--kpi {
    min-height: 80px;
    padding-top: 72px;
  }

  .agents-grid,
  .executive-agents-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: auto;
    gap: 10px;
    height: auto;
    flex: none;
    min-height: 0;
  }

  .agent-card,
  .agent-card--executive {
    height: auto;
    min-height: 160px;
    max-height: 220px;
    padding: 10px;
    border-radius: 12px;
    overflow: hidden;
  }

  .agent-card--executive .avatar-container,
  .agent-card .avatar-container {
    width: 60px;
    height: 60px;
    margin: 4px auto;
  }

  .agent-card--executive .agent-name,
  .agent-card .agent-name {
    font-size: 13px;
    margin: 4px 0;
  }

  .agent-card--executive .agent-role,
  .agent-card .agent-role {
    font-size: 10px;
    margin: 0 0 4px;
  }

  .agent-card--executive .agent-stats {
    margin-bottom: 4px;
    gap: 8px;
  }

  .agent-card--executive .btn-interact,
  .agent-card .btn-interact {
    font-size: 11px;
    height: 30px;
    min-height: 30px;
    padding: 0 10px;
  }

  .agent-card--executive .agent-info {
    gap: 2px;
  }

  .zeus-core-card {
    padding: 10px;
  }

  .zeus-core-avatar {
    width: 60px;
    height: 60px;
  }

  .zeus-core-name {
    font-size: 15px;
  }
}
</style>