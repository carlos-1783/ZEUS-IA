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
              <span class="status-dot" :class="{ active: integrationStatus.stripe }"></span>
            </div>
            <div class="integration-item">
              <span>📱 WhatsApp (Twilio)</span>
              <span class="status-dot" :class="{ active: integrationStatus.whatsapp }"></span>
            </div>
            <div class="integration-item">
              <span>📧 Email (SendGrid)</span>
              <span class="status-dot" :class="{ active: integrationStatus.email }"></span>
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
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Chart, registerables } from 'chart.js'

// Registrar componentes de Chart.js
Chart.register(...registerables)

const router = useRouter()
const authStore = useAuthStore()

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
const loading = ref(false)
const error = ref(null)

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

    const response = await fetch('/api/v1/admin/stats', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      if (response.status === 403) {
        throw new Error('Acceso denegado. Solo superusuarios pueden acceder al panel de admin.')
      }
      throw new Error(`Error ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    
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

    const response = await fetch('/api/v1/admin/customers', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      if (response.status === 403) {
        return // Silenciar error 403, solo mostrar si es necesario
      }
      throw new Error(`Error ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    
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

    const response = await fetch('/api/v1/integrations/status', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      return
    }

    const data = await response.json()
    
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
    const response = await fetch('/api/v1/admin/revenue-chart?months=12', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    console.log('[Chart] Respuesta recibida:', response.status, response.statusText)

    if (!response.ok) {
      if (response.status === 403) {
        console.warn('[Chart] Acceso denegado - solo superusuarios')
        error.value = 'Acceso denegado. Solo superusuarios pueden ver el gráfico.'
        // Renderizar gráfico vacío con mensaje
        renderEmptyChart('Acceso denegado')
        return
      }
      const errorText = await response.text()
      console.error('[Chart] Error en respuesta:', errorText)
      throw new Error(`Error ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
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

const viewCustomer = async (customer) => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const response = await fetch(`/api/v1/admin/customers/${customer.id}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      // Mostrar modal con detalles (por ahora alert, se puede mejorar con componente modal)
      alert(`📋 Detalles del Cliente\n\nEmpresa: ${data.company_name || customer.company_name}\nEmail: ${data.email || customer.email}\nPlan: ${data.plan || customer.plan}\nEmpleados: ${data.employees || customer.employees}\nEstado: ${data.status || customer.status}\nFecha registro: ${data.created_at || 'N/A'}`)
    } else if (response.status === 404) {
      // Si no existe endpoint, mostrar datos disponibles
      alert(`📋 Detalles del Cliente\n\nEmpresa: ${customer.company_name}\nEmail: ${customer.email}\nPlan: ${customer.plan}\nEmpleados: ${customer.employees}\nEstado: ${customer.status}\nPróximo pago: ${formatDate(customer.next_payment)}`)
    } else {
      alert('⚠️ No se pudieron cargar los detalles completos')
    }
  } catch (error) {
    console.error('Error cargando detalles del cliente:', error)
    // Fallback a datos disponibles
    alert(`📋 Detalles del Cliente\n\nEmpresa: ${customer.company_name}\nEmail: ${customer.email}\nPlan: ${customer.plan}\nEmpleados: ${customer.employees}\nEstado: ${customer.status}`)
  }
}

const toggleCustomerStatus = async (customer) => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const newStatus = customer.status === 'active' ? 'inactive' : 'active'
    const response = await fetch(`/api/v1/admin/customers/${customer.id}/toggle-status`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ status: newStatus })
    })
    
    if (response.ok) {
      // Actualizar estado local
      customer.status = newStatus
      alert(`✅ Cliente ${newStatus === 'active' ? 'activado' : 'desactivado'} correctamente`)
      // Recargar lista
      await loadCustomers()
    } else {
      // Si no existe endpoint, actualizar solo localmente (temporal)
      customer.status = newStatus
      alert(`⚠️ Estado cambiado localmente. Endpoint no disponible aún.`)
    }
  } catch (error) {
    console.error('Error cambiando estado del cliente:', error)
    alert('⚠️ No se pudo cambiar el estado. Endpoint no disponible aún.')
  }
}

const saveSettings = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      alert('Error: No hay token de autenticación')
      return
    }
    
    const response = await fetch('/api/v1/admin/settings', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        notifications: {
          email_on_new_customer: settings.value.emailOnNewCustomer,
          email_on_payment_failed: settings.value.emailOnPaymentFailed
        }
      })
    })
    
    if (response.ok) {
      alert('✅ Configuración guardada correctamente')
    } else {
      // Si no existe endpoint, guardar en localStorage temporalmente
      localStorage.setItem('zeus_admin_settings', JSON.stringify(settings.value))
      alert('✅ Configuración guardada localmente. Endpoint no disponible aún.')
    }
  } catch (error) {
    console.error('Error guardando configuración:', error)
    // Fallback a localStorage
    localStorage.setItem('zeus_admin_settings', JSON.stringify(settings.value))
    alert('✅ Configuración guardada localmente')
  }
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

