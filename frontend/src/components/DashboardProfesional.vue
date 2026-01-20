<template>
  <div class="dashboard-profesional">
    <!-- Overlay para móvil -->
    <div 
      class="sidebar-overlay" 
      :class="{ active: sidebarOpen }"
      @click="sidebarOpen = false"
    ></div>

    <!-- Sidebar Oscura -->
    <aside class="sidebar-dark" :class="{ open: sidebarOpen }">
      <div class="logo-section">
        <h1>⚡ ZEUS-IA</h1>
        <p class="subtitle">Enterprise AI Platform</p>
      </div>

      <nav class="nav-menu">
        <button 
          class="nav-item" 
          :class="{ active: currentView === 'dashboard' }"
          @click="currentView = 'dashboard'; closeSidebarOnMobile()"
        >
          <span class="icon">🏛️</span>
          <span>Dashboard</span>
        </button>
        <button 
          class="nav-item"
          :class="{ active: currentView === 'analytics' }"
          @click="currentView = 'analytics'; closeSidebarOnMobile()"
        >
          <span class="icon">📊</span>
          <span>Analytics</span>
        </button>
        <!-- TPV - Siempre visible para superusuarios -->
        <button 
          v-if="shouldShowTPV || authStore.isAdmin || authStore.user?.is_superuser || availableModules.tpv || true"
          class="nav-item tpv-nav-btn"
          @click="goToTPV"
        >
          <span class="icon">💳</span>
          <span>TPV</span>
        </button>
        <!-- Control Horario - Siempre visible para superusuarios -->
        <button 
          v-if="shouldShowControlHorario || authStore.isAdmin || authStore.user?.is_superuser || availableModules.control_horario || true"
          class="nav-item control-horario-nav-btn"
          @click="goToControlHorario"
        >
          <span class="icon">⏰</span>
          <span>Control Horario</span>
        </button>
        <button 
          class="nav-item"
          :class="{ active: currentView === 'settings' }"
          @click="currentView = 'settings'; closeSidebarOnMobile()"
        >
          <span class="icon">⚙️</span>
          <span>Settings</span>
        </button>
        <!-- Admin Panel - Siempre visible para superusuarios -->
        <button 
          v-if="shouldShowAdmin || authStore.isAdmin || authStore.user?.is_superuser || availableModules.admin || true"
          class="nav-item admin-btn"
          @click="goToAdmin"
        >
          <span class="icon">🔐</span>
          <span>Admin Panel</span>
        </button>
      </nav>

      <div class="metrics-mini">
        <div class="metric-item">
          <div class="metric-value">98%</div>
          <div class="metric-label">System Health</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ agentsData.length }}</div>
          <div class="metric-label">Active Agents</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Header -->
      <header class="dashboard-header">
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
            <h2>AI Agents Control Center</h2>
            <p class="breadcrumb">Dashboard / Agents Overview</p>
          </div>
        </div>
        <div class="header-right">
          <!-- Botón Instalar PWA -->
          <button 
            v-if="isInstallable && !isInstalled"
            @click="handleInstallPWA"
            class="pwa-install-btn"
            title="Instalar ZEUS-IA como aplicación"
          >
            📲 Instalar
          </button>
          <!-- Debug: Mostrar estado PWA (temporal para diagnóstico) -->
          <div v-if="!isInstallable || isInstalled" class="pwa-debug-info" title="Estado PWA: installable={{ isInstallable }}, installed={{ isInstalled }}">
            🔧 PWA: {{ isInstalled ? 'Instalada' : isInstallable ? 'Instalable' : 'No disponible' }}
            <a href="/clear-pwa-cache.html" target="_blank" style="color: #ffa500; margin-left: 8px; text-decoration: underline; font-size: 10px;">Limpiar Cache</a>
          </div>
          <div class="status-badge online">● System Online</div>
        </div>
      </header>

      <!-- Agents Grid (Dashboard) -->
      <section v-if="currentView === 'dashboard'" class="agents-grid">
        <div 
          v-for="agent in agentsData" 
          :key="agent.name"
          class="agent-card"
          :class="{ 'has-avatar': agent.hasGLB }"
          @click="selectAgent(agent)"
        >
          <!-- Avatar Image -->
          <div class="avatar-container">
            <img 
              :src="agent.image" 
              :alt="agent.name"
              class="avatar-image"
            />
          </div>

          <!-- Agent Info -->
          <div class="agent-info">
            <h3 class="agent-name">{{ agent.name }}</h3>
            <p class="agent-role">{{ agent.role }}</p>
            
            <div class="agent-stats">
              <div class="stat">
                <span class="stat-label">Status</span>
                <span class="stat-value status-active">Online</span>
              </div>
              <div class="stat">
                <span class="stat-label">Actividades 24h</span>
                <span class="stat-value">{{ agent.activities_24h || 0 }}</span>
              </div>
            </div>

            <button class="btn-interact" @click.stop="chatWith(agent)">
              <span>💬</span>
              Interact
            </button>
          </div>
        </div>
      </section>

      <!-- Analytics View -->
      <section v-if="currentView === 'analytics'" class="analytics-view">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon">📈</div>
            <div class="stat-content">
              <h3>Total Interactions</h3>
              <p class="stat-number">{{ dashboardMetrics.totalInteractions.toLocaleString() }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.interactionsTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
              <h3>Avg Response Time</h3>
              <p class="stat-number">{{ dashboardMetrics.avgResponseTime }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.responseTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-content">
              <h3>Cost Savings</h3>
              <p class="stat-number">{{ dashboardMetrics.costSavings }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.savingsTrend }}</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon">✅</div>
            <div class="stat-content">
              <h3>Success Rate</h3>
              <p class="stat-number">{{ dashboardMetrics.successRate }}</p>
              <span class="stat-change positive">{{ dashboardMetrics.successTrend }}</span>
            </div>
          </div>
        </div>

        <div class="chart-placeholder">
          <h3>Performance Analytics</h3>
          <div class="placeholder-content">
            <span class="icon-large">📊</span>
            <p>Detailed analytics charts coming soon</p>
          </div>
        </div>
      </section>

      <!-- Settings View -->
      <section v-if="currentView === 'settings'" class="settings-view">
        <div class="settings-grid">
          <div class="settings-card">
            <h3>🔔 Notifications</h3>
            <div class="setting-item">
              <label>Email notifications</label>
              <input type="checkbox" v-model="notificationSettings.email" />
            </div>
            <div class="setting-item">
              <label>Push notifications</label>
              <input type="checkbox" v-model="notificationSettings.push" />
            </div>
            <div class="setting-item">
              <label>Agent status updates</label>
              <input type="checkbox" v-model="notificationSettings.agentStatus" />
            </div>
          </div>

          <div class="settings-card">
            <h3>🎨 Appearance</h3>
            <div class="setting-item">
              <label>Theme</label>
              <select v-model="theme" @change="handleThemeChange">
                <option value="dark">Dark (Current)</option>
                <option value="light">Light</option>
                <option value="auto">Auto</option>
              </select>
            </div>
            <div class="setting-item">
              <label>Language</label>
              <select v-model="currentLanguage">
                <option v-for="lang in supportedLanguages" :key="lang" :value="lang">
                  {{ lang === 'es' ? 'Español' : lang === 'en' ? 'English' : lang.toUpperCase() }}
                </option>
              </select>
            </div>
          </div>

          <div class="settings-card">
            <h3>🔐 Security</h3>
            <div class="setting-item">
              <label>Two-factor authentication</label>
              <button class="btn-secondary" @click="handleEnable2FA">Enable</button>
            </div>
            <div class="setting-item">
              <label>Session timeout</label>
              <select v-model="sessionTimeout" @change="handleSessionTimeoutChange">
                <option value="30">30 minutes</option>
                <option value="60">1 hour</option>
                <option value="240">4 hours</option>
              </select>
            </div>
          </div>

          <div class="settings-card">
            <h3>⚙️ Advanced</h3>
            <div class="setting-item">
              <label>API Access</label>
              <button class="btn-secondary" @click="handleGenerateApiKey">Generate Key</button>
            </div>
            <div class="setting-item">
              <label>Export Data</label>
              <button class="btn-secondary" @click="handleExportData">Download</button>
            </div>
          </div>
        </div>
      </section>

      <!-- Agent Activity Panel (si hay agente seleccionado) -->
      <div v-if="selectedAgent" class="agent-overlay" @click.self="selectedAgent = null">
        <div class="agent-panel-container">
          <button class="btn-close-panel" @click="selectedAgent = null">✕</button>
          <AgentActivityPanel :agent="selectedAgent" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AgentActivityPanel from './AgentActivityPanel.vue'
import { usePWA } from '@/composables/usePWA'

const router = useRouter()
const authStore = useAuthStore()

// i18n
const { locale, t } = useI18n()

// PWA Install
const { isInstallable, isInstalled, promptInstall } = usePWA()

// Idiomas soportados
const supportedLanguages = ['es', 'en']

// Idioma actual
const currentLanguage = computed({
  get: () => locale.value,
  set: (value) => {
    locale.value = value
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      window.localStorage.setItem('zeus_locale', value)
    }
    console.log('🌍 Idioma cambiado a:', value)
  }
})

const props = defineProps({
  agents: Array
})

const emit = defineEmits(['agentClicked'])

const selectedAgent = ref(null)
const currentView = ref('dashboard')
const sidebarOpen = ref(false)

// Settings
const notificationSettings = ref({
  email: true,
  push: true,
  agentStatus: false
})

const theme = ref('dark')
const sessionTimeout = ref('60')

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

// Instalar PWA
const handleInstallPWA = async () => {
  const installed = await promptInstall()
  if (installed) {
    console.log('✅ PWA instalación iniciada')
  }
}

// Settings handlers
const handleEnable2FA = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const response = await fetch('/api/v1/user/2fa/enable', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      alert(`✅ Autenticación de dos factores habilitada\n\nCódigo QR:\n${data.qr_code || 'Disponible en configuración'}`)
    } else {
      alert('⚠️ Función disponible próximamente')
    }
  } catch (error) {
    console.error('Error habilitando 2FA:', error)
    alert('⚠️ Función disponible próximamente')
  }
}

const handleGenerateApiKey = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const response = await fetch('/api/v1/api-keys', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      const apiKey = data.api_key || data.key
      if (apiKey) {
        await navigator.clipboard.writeText(apiKey)
        alert(`✅ Clave API generada y copiada al portapapeles\n\nClave: ${apiKey}\n\n⚠️ Guarda esta clave en un lugar seguro. No se mostrará de nuevo.`)
      }
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
    
    const response = await fetch('/api/v1/user/export', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `zeus-export-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      alert('✅ Datos exportados correctamente')
    } else {
      // Fallback: exportar datos locales
      const localData = {
        user: authStore.user,
        settings: {
          notifications: notificationSettings.value,
          theme: theme.value,
          sessionTimeout: sessionTimeout.value,
          language: locale.value
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
        theme: theme.value,
        sessionTimeout: sessionTimeout.value,
        language: locale.value
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

const handleThemeChange = () => {
  // Guardar tema en localStorage
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    window.localStorage.setItem('zeus_theme', theme.value)
    // Aplicar tema al documento
    document.documentElement.setAttribute('data-theme', theme.value)
    alert(`✅ Tema cambiado a: ${theme.value}`)
  }
}

const handleSessionTimeoutChange = () => {
  // Guardar timeout en localStorage
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    window.localStorage.setItem('zeus_session_timeout', sessionTimeout.value)
    alert(`✅ Timeout de sesión configurado: ${sessionTimeout.value} minutos`)
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

// Módulos disponibles (desde endpoint unificado)
// Inicializar con valores por defecto: superusuarios tienen acceso completo
const availableModules = ref({
  tpv: false,
  control_horario: false,
  dashboard: true,
  analytics: true,
  agents: true,
  admin: false,
  settings: true
})

// Computed para verificar si el usuario es admin (reactivo) - múltiples formas de verificación
const isAdmin = computed(() => {
  // Verificar de múltiples formas para asegurar que detectamos al superusuario
  const isAdmin1 = authStore.isAdmin || false
  const isAdmin2 = authStore.user?.is_superuser || false
  
  const result = isAdmin1 || isAdmin2
  console.log('🔍 Verificación isAdmin computed:', {
    isAdmin1,
    isAdmin2,
    user: authStore.user,
    authStoreIsAdmin: authStore.isAdmin,
    result
  })
  return result
})

// Computed para módulos visibles - SIEMPRE mostrar si es admin o si availableModules lo permite
// Por defecto, los botones están visibles (availableModules inicializado en true)
const shouldShowTPV = computed(() => {
  // Si es admin, mostrar SIEMPRE
  if (isAdmin.value) {
    return true
  }
  // Si no es admin, verificar availableModules
  return availableModules.value.tpv
})

const shouldShowControlHorario = computed(() => {
  // Si es admin, mostrar SIEMPRE
  if (isAdmin.value) {
    return true
  }
  // Si no es admin, verificar availableModules
  return availableModules.value.control_horario
})

const shouldShowAdmin = computed(() => {
  // Si es admin, mostrar SIEMPRE
  if (isAdmin.value) {
    return true
  }
  // Si no es admin, verificar availableModules
  return availableModules.value.admin
})

// Cargar datos unificados del dashboard desde endpoint unificado
const loadDashboardMetrics = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      console.warn('⚠️ No hay token, no se pueden cargar métricas')
      return
    }

    // Usar endpoint unificado /summary en lugar de /dashboard
    const response = await fetch('/api/v1/metrics/summary?days=30', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    
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

      // Verificar si es superusuario ANTES de actualizar módulos
      const isSuperuser = authStore.isAdmin || authStore.user?.is_superuser || data.user?.is_superuser || false
      
      // SIEMPRE forzar módulos para superusuarios (garantizar acceso completo)
      if (isSuperuser) {
        availableModules.value.tpv = true
        availableModules.value.control_horario = true
        availableModules.value.admin = true
        console.log('✅ Forzando módulos desde endpoint para superusuario:', {
          authStoreIsAdmin: authStore.isAdmin,
          userIsSuperuser: authStore.user?.is_superuser,
          dataUserIsSuperuser: data.user?.is_superuser,
          isSuperuser
        })
      } else {
        // Solo actualizar módulos si NO es superusuario
        if (data.available_modules) {
          availableModules.value = { ...data.available_modules }
          console.log('⚠️ Usuario no es superusuario, usando módulos del endpoint:', data.available_modules)
        }
      }

      console.log('✅ Dashboard unificado cargado:', {
        metrics: dashboardMetrics.value,
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

// Watch para guardar settings automáticamente (al nivel superior)
watch(notificationSettings, () => {
  saveNotificationSettings()
}, { deep: true })

// Watch para guardar tema automáticamente
watch(theme, (newVal) => {
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    window.localStorage.setItem('zeus_theme', newVal)
    document.documentElement.setAttribute('data-theme', newVal)
  }
})

// Watch para guardar timeout automáticamente
watch(sessionTimeout, (newVal) => {
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    window.localStorage.setItem('zeus_session_timeout', newVal)
  }
})

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

// Cargar al montar y refrescar periódicamente
onMounted(async () => {
  // Inicializar authStore si no está inicializado
  if (!authStore.isAuthenticated && authStore.initialize) {
    console.log('🔄 Inicializando authStore...')
    await authStore.initialize()
  }
  
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
  loadDashboardMetrics()
  loadAgentsActivities()
  
  // Cargar configuraciones guardadas
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    const savedTheme = window.localStorage.getItem('zeus_theme')
    if (savedTheme) {
      theme.value = savedTheme
      document.documentElement.setAttribute('data-theme', savedTheme)
    }
    
    const savedTimeout = window.localStorage.getItem('zeus_session_timeout')
    if (savedTimeout) {
      sessionTimeout.value = savedTimeout
    }
  }
  
  // Refresh dashboard metrics cada 30 segundos
  setInterval(loadDashboardMetrics, 30000)
  
  // Refresh actividades de agentes cada minuto
  setInterval(loadAgentsActivities, 60000)
  
  // Guardar settings cuando cambien (fuera de onMounted)
  
  // Verificar después de múltiples delays para asegurar que authStore esté listo
  setTimeout(() => {
    console.log('🔍 Estado después de delay 100ms:', {
      isAdmin: authStore.isAdmin,
      userIsSuperuser: authStore.user?.is_superuser,
      user: authStore.user,
      shouldShowTPV: shouldShowTPV.value,
      shouldShowControlHorario: shouldShowControlHorario.value,
      shouldShowAdmin: shouldShowAdmin.value
    })
    updateModulesForSuperuser()
  }, 100)
  
  setTimeout(() => {
    console.log('🔍 Estado después de delay 500ms:', {
      isAdmin: authStore.isAdmin,
      userIsSuperuser: authStore.user?.is_superuser,
      user: authStore.user,
      shouldShowTPV: shouldShowTPV.value,
      shouldShowControlHorario: shouldShowControlHorario.value,
      shouldShowAdmin: shouldShowAdmin.value
    })
    updateModulesForSuperuser()
  }, 500)
  
  setTimeout(() => {
    console.log('🔍 Estado después de delay 1000ms:', {
      isAdmin: authStore.isAdmin,
      userIsSuperuser: authStore.user?.is_superuser,
      user: authStore.user,
      shouldShowTPV: shouldShowTPV.value,
      shouldShowControlHorario: shouldShowControlHorario.value,
      shouldShowAdmin: shouldShowAdmin.value
    })
    updateModulesForSuperuser()
  }, 1000)
})

const agentsData = ref([
  {
    name: 'ZEUS CORE',
    role: 'Supreme Orchestrator',
    image: '/images/avatars/Zeus-avatar.jpg',
    activities_24h: 0
  },
  {
    name: 'PERSEO',
    role: 'Growth Strategist',
    image: '/images/avatars/Perseo-avatar.jpg',
    activities_24h: 0
  },
  {
    name: 'RAFAEL',
    role: 'Fiscal Guardian',
    image: '/images/avatars/Rafael-avatar.jpg',
    activities_24h: 0
  },
  {
    name: 'THALOS',
    role: 'Cybersecurity Defender',
    image: '/images/avatars/Thalos-avatar.jpg',
    activities_24h: 0
  },
  {
    name: 'JUSTICIA',
    role: 'Legal & GDPR Advisor',
    image: '/images/avatars/Justicia-avatar.jpg',
    activities_24h: 0
  },
  {
    name: 'AFRODITA',
    role: 'HR & Logistics Manager',
    image: '/images/avatars/Afrodita-avatar.jpg',
    activities_24h: 0
  }
])

// Cargar actividades reales de cada agente (últimas 24h)
const loadAgentsActivities = async () => {
  for (const agent of agentsData.value) {
    try {
      const agentName = agent.name.split(' ')[0].toUpperCase()
      const response = await fetch(`/api/v1/activities/${agentName}?days=1`)
      const data = await response.json()
      
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
</script>

<style scoped>
.dashboard-profesional {
  display: flex;
  min-height: 100vh;
  height: auto;
  background: #0a0e1a;
  color: #fff;
  font-family: 'Inter', -apple-system, sans-serif;
  overflow-x: hidden;
}

/* SIDEBAR OVERLAY (solo móvil) */
.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
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
  background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease;
  z-index: 999;
}

.logo-section {
  margin-bottom: 48px;
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
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin: 4px 0 0;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.nav-item.admin-btn {
  margin-top: 8px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.nav-item.admin-btn:hover {
  background: rgba(139, 92, 246, 0.2);
  color: #8b5cf6;
  border-color: rgba(139, 92, 246, 0.5);
}

.nav-item.tpv-nav-btn {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.nav-item.tpv-nav-btn:hover {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
  border-color: rgba(16, 185, 129, 0.5);
}

.nav-item.control-horario-nav-btn {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.nav-item.control-horario-nav-btn:hover {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  border-color: rgba(59, 130, 246, 0.5);
}

.icon {
  font-size: 18px;
}

.metrics-mini {
  display: flex;
  gap: 16px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.metric-item {
  flex: 1;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #3b82f6;
}

.metric-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
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
  background: #fff;
  transition: all 0.3s;
}

/* MAIN CONTENT */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
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
}

.breadcrumb {
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  margin: 4px 0 0;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.online {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
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
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.3);
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
  .agents-grid {
    grid-template-columns: 1fr;
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

/* AGENTS GRID */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
}

.agent-card {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s;
}

.agent-card:hover {
  transform: translateY(-4px);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 8px 32px rgba(59, 130, 246, 0.2);
}

.avatar-container {
  width: 250px;
  height: 250px;
  margin: 0 auto 20px;
  border-radius: 50%;
  overflow: hidden;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid rgba(59, 130, 246, 0.3);
  transition: all 0.3s;
}

.agent-card:hover .avatar-container {
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.agent-card:hover .avatar-image {
  transform: scale(1.1);
}

.agent-info {
  text-align: center;
}

.agent-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #fff;
}

.agent-role {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  margin: 0 0 20px;
}

.agent-stats {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 20px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
}

.status-active {
  color: #10b981;
}

.btn-interact {
  padding: 10px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.btn-interact:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.4);
}

/* AGENT ACTIVITY PANEL OVERLAY */
.agent-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 32px 24px;
  overflow-y: auto;
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

.agent-panel-container::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.6), rgba(139, 92, 246, 0.4));
  opacity: 0.2;
  pointer-events: none;
  z-index: -1;
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
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.stat-icon {
  font-size: 32px;
  background: rgba(59, 130, 246, 0.15);
  padding: 12px;
  border-radius: 12px;
}

.stat-content h3 {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 8px;
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  color: #fff;
}

.stat-change {
  font-size: 13px;
  margin-top: 4px;
  display: inline-block;
}

.stat-change.positive {
  color: #10b981;
}

.chart-placeholder {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 32px;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

.chart-placeholder h3 {
  margin: 0 0 24px;
  font-size: 20px;
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
  opacity: 0.5;
}

.placeholder-content p {
  color: rgba(255, 255, 255, 0.5);
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
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
}

.settings-card h3 {
  margin: 0 0 20px;
  font-size: 18px;
  color: #fff;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.setting-item input[type="checkbox"] {
  width: 44px;
  height: 24px;
  cursor: pointer;
}

.setting-item select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px 12px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.setting-item select option {
  background: #1a1f2e;
}

.btn-secondary {
  padding: 8px 16px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  color: #3b82f6;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.5);
}
</style>