<template>
  <div class="control-horario-container">
    <!-- Botón de vuelta al Dashboard -->
    <button @click="goToDashboard" class="back-to-dashboard-btn fixed-top-left">
      <span class="btn-icon">📊</span>
      <span class="btn-label">{{ $t('controlHorario.backToDashboard') }}</span>
    </button>

    <!-- Header del Control Horario -->
    <div class="control-horario-header">
      <div class="control-horario-title-section">
        <h1 class="control-horario-title">⏰ {{ $t('controlHorario.title') }}</h1>
        <p class="control-horario-subtitle">{{ $t('controlHorario.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <button @click="checkStatus" class="header-btn">
          🔄 {{ $t('controlHorario.refresh') }}
        </button>
        <div v-if="businessProfile" class="business-profile-badge">
          🏢 {{ getBusinessProfileLabel(businessProfile) }}
        </div>
      </div>
    </div>

    <!-- Interfaz Principal -->
    <div class="control-horario-main-interface" v-if="!loading && !error">
      
      <!-- Panel de Check-In/Check-Out Principal -->
      <div class="check-in-out-panel">
        <div class="method-selector">
          <h3>{{ $t('controlHorario.selectMethod') }}</h3>
          <div class="methods-grid">
            <button
              v-for="method in availableMethods"
              :key="method.id"
              @click="selectedMethod = method.id"
              class="method-btn"
              :class="{ active: selectedMethod === method.id }"
              :disabled="!isMethodEnabled(method.id)"
            >
              <span class="method-icon">{{ method.icon }}</span>
              <span class="method-label">{{ method.label }}</span>
            </button>
          </div>
        </div>

        <!-- Formulario de Fichaje -->
        <div class="check-form">
          <div class="employee-selector">
            <label>{{ $t('controlHorario.employee') }}</label>
            <select v-model="selectedEmployee" class="employee-select">
              <option value="">{{ $t('controlHorario.selectEmployee') }}</option>
              <option v-for="employee in employees" :key="employee.id" :value="employee.id">
                {{ employee.name }}
              </option>
            </select>
          </div>

          <div v-if="selectedMethod === 'location' && config.gps_required" class="location-info">
            <p>📍 {{ $t('controlHorario.gpsRequired') }}</p>
            <button @click="getCurrentLocation" class="btn-location">
              📍 {{ $t('controlHorario.getLocation') }}
            </button>
          </div>

          <div class="check-buttons">
            <button
              @click="handleCheckIn"
              :disabled="!selectedEmployee || !selectedMethod || checking"
              class="btn-check-in"
            >
              ✅ {{ $t('controlHorario.checkIn') }}
            </button>
            <button
              @click="handleCheckOut"
              :disabled="!selectedEmployee || checking"
              class="btn-check-out"
            >
              🚪 {{ $t('controlHorario.checkOut') }}
            </button>
            <button
              type="button"
              @click="handleBreakStart"
              :disabled="!selectedEmployee || checking"
              class="btn-break-start"
            >
              ☕ {{ $t('controlHorario.breakStart') }}
            </button>
            <button
              type="button"
              @click="handleBreakEnd"
              :disabled="!selectedEmployee || checking"
              class="btn-break-end"
            >
              ▶️ {{ $t('controlHorario.breakEnd') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="smartAlerts.length" class="alerts-panel">
        <h3>{{ $t('controlHorario.smartAlerts') }}</h3>
        <ul class="alerts-list">
          <li v-for="a in smartAlerts" :key="a.id" :class="'sev-' + (a.severity || 'warning')">
            <span class="alert-kind">{{ a.kind }}</span>
            {{ a.message }}
          </li>
        </ul>
      </div>

      <div v-if="smartTpv && smartTpv.ok" class="tpv-hint-panel">
        <h3>{{ $t('controlHorario.tpvStaffing') }}</h3>
        <p class="tpv-hint-text">
          {{ $t('controlHorario.tpvWindow') }}: {{ smartTpv.window_sales_total }} € —
          {{ staffingHintLabel(smartTpv.staffing_hint) }}
        </p>
      </div>

      <!-- Panel de Estado Actual -->
      <div class="status-panel">
        <h3>{{ $t('controlHorario.currentStatus') }}</h3>
        
        <!-- Lista de Empleados -->
        <div class="employees-status-list">
          <div
            v-for="employee in employees"
            :key="employee.id"
            class="employee-status-card"
            :class="{
              'status-inside': employee.status === 'inside',
              'status-outside': employee.status === 'outside',
              'status-break': employee.status === 'on_break'
            }"
          >
            <div class="employee-avatar">
              <span>{{ getInitials(employee.name) }}</span>
            </div>
            <div class="employee-info">
              <h4>{{ employee.name }}</h4>
              <p class="employee-id">ID: {{ employee.id }}</p>
            </div>
            <div class="employee-status">
              <span v-if="employee.status === 'inside'" class="status-badge inside">
                ✅ {{ $t('controlHorario.inside') }}
              </span>
              <span v-else-if="employee.status === 'on_break'" class="status-badge break">
                ☕ {{ $t('controlHorario.onBreak') }}
              </span>
              <span v-else class="status-badge outside">
                🚪 {{ $t('controlHorario.outside') }}
              </span>
              <p v-if="employee.check_in_time" class="check-in-time">
                {{ formatTime(employee.check_in_time) }}
              </p>
              <p v-if="todayHoursFor(employee.id) != null" class="today-hours">
                {{ $t('controlHorario.completedToday') }}: {{ todayHoursFor(employee.id) }}h
              </p>
            </div>
          </div>
          
          <div v-if="employees.length === 0" class="no-employees">
            <p>👥 {{ $t('controlHorario.noEmployees') }}</p>
          </div>
        </div>
      </div>

      <!-- Panel de Historial del Día -->
      <div class="history-panel">
        <h3>{{ $t('controlHorario.todayHistory') }}</h3>
        <div class="history-list">
          <div
            v-for="record in todayRecords"
            :key="record.id"
            class="history-item"
          >
            <div class="history-icon">
              <span v-if="record.type === 'check-in'">✅</span>
              <span v-else-if="record.type === 'check-out'">🚪</span>
              <span v-else-if="record.type === 'break-start'">☕</span>
              <span v-else-if="record.type === 'break-end'">▶️</span>
              <span v-else>📋</span>
            </div>
            <div class="history-info">
              <p class="history-employee">{{ getEmployeeName(record.employee_id) }}</p>
              <p class="history-type">{{ historyTypeLabel(record.type) }}</p>
              <p class="history-time">{{ formatTime(record.time) }}</p>
            </div>
            <div class="history-method">
              <span>{{ getMethodLabel(record.method) }}</span>
            </div>
          </div>
          
          <div v-if="todayRecords.length === 0" class="no-history">
            <p>{{ $t('controlHorario.noRecordsToday') }}</p>
          </div>
        </div>
      </div>

      <!-- Panel de Métricas -->
      <div class="metrics-panel">
        <div class="metric-card">
          <div class="metric-icon">👥</div>
          <div class="metric-content">
            <h4>{{ $t('controlHorario.totalEmployees') }}</h4>
            <p class="metric-value">{{ employees.length }}</p>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon">✅</div>
          <div class="metric-content">
            <h4>{{ $t('controlHorario.insideNow') }}</h4>
            <p class="metric-value">{{ employeesInside }}</p>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon">📊</div>
          <div class="metric-content">
            <h4>{{ $t('controlHorario.attendanceRate') }}</h4>
            <p class="metric-value">{{ attendanceRate }}%</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>{{ $t('controlHorario.loading') }}</p>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-state">
      <p>❌ {{ error }}</p>
      <button @click="checkStatus" class="retry-btn">{{ $t('controlHorario.retry') }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

// Estado
const loading = ref(false)
const error = ref(null)
const checking = ref(false)
const businessProfile = ref(null)
const config = ref({})
const employees = ref([])
const selectedEmployee = ref('')
const selectedMethod = ref('qr')
const todayRecords = ref([])
const currentLocation = ref({ latitude: null, longitude: null })
const smartAlerts = ref([])
const smartTpv = ref(null)
const todayHoursByEmployee = ref({})
let refreshTimer = null

// Métodos disponibles
const availableMethods = computed(() => [
  { id: 'face', icon: '📷', label: t('controlHorario.methods.face') },
  { id: 'qr', icon: '📱', label: t('controlHorario.methods.qr') },
  { id: 'code', icon: '🔢', label: t('controlHorario.methods.code') },
  { id: 'location', icon: '📍', label: t('controlHorario.methods.location') },
  { id: 'remote', icon: '💻', label: t('controlHorario.methods.remote') }
])

// Computed
const employeesInside = computed(() => {
  return employees.value.filter(
    (emp) => emp.status === 'inside' || emp.status === 'on_break'
  ).length
})

const attendanceRate = computed(() => {
  if (employees.value.length === 0) return 0
  return Math.round((employeesInside.value / employees.value.length) * 100)
})

const isMethodEnabled = (methodId) => {
  const enabled = Array.isArray(config.value?.methods_enabled) ? config.value.methods_enabled : []
  if (enabled.includes(methodId)) return true
  // Compatibilidad backend: on_site equivale a location en UI.
  if (methodId === 'location' && enabled.includes('on_site')) return true
  return false
}

// Métodos
const goToDashboard = () => {
  router.push('/dashboard')
}

const checkStatus = async () => {
  loading.value = true
  error.value = null
  
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }

    // Carga inicial optimizada: evita 3 requests secuenciales.
    const api = (await import('@/services/api')).default
    const bootstrap = await api.get('/api/v1/control-horario/bootstrap', token)
    const infoData = bootstrap?.info || {}
    const statusData = bootstrap?.status || {}
    const employeesData = Array.isArray(bootstrap?.employees) ? bootstrap.employees : []
    const employeesSource = bootstrap?.employees_source || 'memory'
    const recordsData = Array.isArray(bootstrap?.today_records) ? bootstrap.today_records : []

    businessProfile.value = infoData.business_profile
    config.value = infoData.config || {}
    if (!isMethodEnabled(selectedMethod.value)) {
      const enabled = Array.isArray(config.value?.methods_enabled) ? config.value.methods_enabled : []
      const normalized = enabled.includes('on_site')
        ? enabled.map((m) => (m === 'on_site' ? 'location' : m))
        : enabled
      selectedMethod.value = normalized[0] || 'qr'
    }

    // Actualizar empleados con estado
    const employeesMap = {}
    if (employeesData.length > 0) {
      employeesData.forEach((emp) => {
        const empId = String(emp.id)
        employeesMap[empId] = {
          id: empId,
          name: emp.name || empId, // fallback de compatibilidad
          status: emp.status || 'outside',
          check_in_time: emp.check_in_time
        }
      })
    }
    
    // En producción no usar empleados demo: mostrar vacío para forzar configuración real.
    const isProd = import.meta.env.PROD
    if (Object.keys(employeesMap).length === 0) {
      if (employeesSource === 'database' || isProd) {
        employees.value = []
      } else {
        employees.value = [
          { id: 'emp1', name: 'Empleado 1', status: 'outside' },
          { id: 'emp2', name: 'Empleado 2', status: 'outside' }
        ]
      }
    } else {
      employees.value = Object.values(employeesMap)
    }
    
    // Sincronizar con status del servicio (misma forma que devuelve get_current_status)
    const statusEmployees = statusData?.employees
    if (statusEmployees && typeof statusEmployees === 'object' && !Array.isArray(statusEmployees)) {
      Object.keys(statusEmployees).forEach(empId => {
        const emp = employees.value.find(e => e.id === empId)
        if (emp) {
          emp.status = statusEmployees[empId].status
          emp.check_in_time = statusEmployees[empId].check_in_time
        }
      })
    }

    todayRecords.value = recordsData

    const smart = bootstrap?.smart || {}
    smartAlerts.value = Array.isArray(smart.alerts) ? smart.alerts : []
    smartTpv.value = smart.tpv && typeof smart.tpv === 'object' ? smart.tpv : null
    todayHoursByEmployee.value =
      smart.today_completed_hours_by_employee && typeof smart.today_completed_hours_by_employee === 'object'
        ? smart.today_completed_hours_by_employee
        : {}
    
  } catch (err) {
    console.error('Error cargando estado:', err)
    error.value = err.message || 'Error al cargar el estado'
  } finally {
    loading.value = false
  }
}

const handleCheckIn = async () => {
  if (!selectedEmployee.value || !selectedMethod.value) return
  
  checking.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) throw new Error('No hay token')
    
    const api = (await import('@/services/api')).default
    const data = await api.post('/api/v1/control-horario/check-in', {
      employee_id: selectedEmployee.value,
      method: selectedMethod.value,
      location: currentLocation.value.latitude ? 'GPS Location' : null,
      latitude: currentLocation.value.latitude,
      longitude: currentLocation.value.longitude
    }, token)
    
    alert(`✅ ${data.message || 'Entrada registrada correctamente'}`)
    
    // Actualizar estado
    await checkStatus()
    selectedEmployee.value = ''
    
  } catch (err) {
    console.error('Error en check-in:', err)
    alert(`❌ ${err.message}`)
  } finally {
    checking.value = false
  }
}

const todayHoursFor = (empId) => {
  const v = todayHoursByEmployee.value[String(empId)]
  if (v == null || Number.isNaN(Number(v))) return null
  return Math.round(Number(v) * 100) / 100
}

const staffingHintLabel = (hint) => {
  if (hint === 'increase_staffing') return t('controlHorario.tpvHintIncrease')
  if (hint === 'reduce_staffing') return t('controlHorario.tpvHintReduce')
  return t('controlHorario.tpvHintSteady')
}

const historyTypeLabel = (type) => {
  if (type === 'check-in') return t('controlHorario.checkIn')
  if (type === 'check-out') return t('controlHorario.checkOut')
  if (type === 'break-start') return t('controlHorario.breakStart')
  if (type === 'break-end') return t('controlHorario.breakEnd')
  return type || ''
}

const handleBreakStart = async () => {
  if (!selectedEmployee.value) return
  checking.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) throw new Error('No hay token')
    const api = (await import('@/services/api')).default
    const data = await api.post(
      '/api/v1/control-horario/break-start',
      {
        employee_id: selectedEmployee.value,
        location: currentLocation.value.latitude ? 'GPS Location' : null,
        latitude: currentLocation.value.latitude,
        longitude: currentLocation.value.longitude
      },
      token
    )
    alert(`✅ ${data.message || 'OK'}`)
    await checkStatus()
  } catch (err) {
    console.error(err)
    alert(`❌ ${err.message}`)
  } finally {
    checking.value = false
  }
}

const handleBreakEnd = async () => {
  if (!selectedEmployee.value) return
  checking.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) throw new Error('No hay token')
    const api = (await import('@/services/api')).default
    const data = await api.post(
      '/api/v1/control-horario/break-end',
      {
        employee_id: selectedEmployee.value,
        location: currentLocation.value.latitude ? 'GPS Location' : null,
        latitude: currentLocation.value.latitude,
        longitude: currentLocation.value.longitude
      },
      token
    )
    alert(`✅ ${data.message || 'OK'}`)
    await checkStatus()
  } catch (err) {
    console.error(err)
    alert(`❌ ${err.message}`)
  } finally {
    checking.value = false
  }
}

const handleCheckOut = async () => {
  if (!selectedEmployee.value) return
  
  checking.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) throw new Error('No hay token')
    
    const api = (await import('@/services/api')).default
    const data = await api.post('/api/v1/control-horario/check-out', {
      employee_id: selectedEmployee.value,
      method: selectedMethod.value || 'code',
      location: currentLocation.value.latitude ? 'GPS Location' : null,
      latitude: currentLocation.value.latitude,
      longitude: currentLocation.value.longitude
    }, token)
    
    const hours = data.hours_worked || 0
    alert(`✅ ${data.message || 'Salida registrada correctamente'}\n⏰ Horas trabajadas: ${hours}h`)
    
    // Actualizar estado
    await checkStatus()
    selectedEmployee.value = ''
    
  } catch (err) {
    console.error('Error en check-out:', err)
    alert(`❌ ${err.message}`)
  } finally {
    checking.value = false
  }
}

const getCurrentLocation = () => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        currentLocation.value = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        }
      },
      (err) => {
        alert(`Error obteniendo ubicación: ${err.message}`)
      }
    )
  } else {
    alert('Geolocalización no disponible en tu navegador')
  }
}

const getBusinessProfileLabel = (profile) => {
  const labels = {
    'oficina': 'Oficina',
    'restaurante': 'Restaurante',
    'tienda': 'Tienda',
    'externo': 'Externo',
    'remoto': 'Remoto',
    'turnos': 'Turnos',
    'logística': 'Logística',
    'producción': 'Producción',
    'comercial': 'Comercial',
    'servicios': 'Servicios',
    'otros': 'Otros'
  }
  return labels[profile] || profile
}

const getInitials = (name) => {
  if (!name) return '?'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  try {
    const date = new Date(timeStr)
    return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return timeStr
  }
}

const getEmployeeName = (employeeId) => {
  const emp = employees.value.find(e => e.id === employeeId)
  return emp ? emp.name : employeeId
}

const getMethodLabel = (method) => {
  const labels = {
    'face': '📷 Facial',
    'qr': '📱 QR',
    'code': '🔢 Código',
    'location': '📍 GPS',
    'remote': '💻 Remoto'
  }
  return labels[method] || method
}

onMounted(() => {
  checkStatus()
  refreshTimer = window.setInterval(() => {
    if (!loading.value && !checking.value) checkStatus()
  }, 45000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.control-horario-container {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 20px;
  position: relative;
}

.back-to-dashboard-btn {
  position: fixed;
  top: 20px;
  left: 20px;
  padding: 12px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 100;
  font-weight: 600;
}

.control-horario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.control-horario-title {
  margin: 0;
  font-size: 32px;
  color: #1f2937;
}

.control-horario-subtitle {
  margin: 8px 0 0;
  color: #6b7280;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-btn {
  padding: 10px 20px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.business-profile-badge {
  padding: 10px 20px;
  background: #f3f4f6;
  border-radius: 8px;
  font-weight: 600;
  color: #374151;
}

.control-horario-main-interface {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.check-in-out-panel {
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  grid-column: 1 / -1;
}

.method-selector h3 {
  margin: 0 0 16px;
  color: #1f2937;
}

.methods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.method-btn {
  padding: 16px;
  background: #f9fafb;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.method-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  background: #eff6ff;
}

.method-btn.active {
  border-color: #3b82f6;
  background: #dbeafe;
}

.method-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.method-icon {
  font-size: 32px;
}

.check-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.employee-selector label {
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
  display: block;
}

.employee-select {
  width: 100%;
  padding: 12px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 16px;
}

.check-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.check-buttons > button {
  flex: 1 1 42%;
  min-width: 140px;
}

.btn-check-in,
.btn-check-out,
.btn-break-start,
.btn-break-end {
  padding: 16px;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-check-in {
  background: #10b981;
  color: white;
}

.btn-check-in:hover:not(:disabled) {
  background: #059669;
}

.btn-check-out {
  background: #ef4444;
  color: white;
}

.btn-check-out:hover:not(:disabled) {
  background: #dc2626;
}

.btn-break-start {
  background: #f59e0b;
  color: white;
}

.btn-break-start:hover:not(:disabled) {
  background: #d97706;
}

.btn-break-end {
  background: #6366f1;
  color: white;
}

.btn-break-end:hover:not(:disabled) {
  background: #4f46e5;
}

.btn-check-in:disabled,
.btn-check-out:disabled,
.btn-break-start:disabled,
.btn-break-end:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.alerts-panel,
.tpv-hint-panel {
  grid-column: 1 / -1;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.alerts-panel h3,
.tpv-hint-panel h3 {
  margin: 0 0 12px;
  color: #1f2937;
}

.alerts-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.alerts-list li {
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 14px;
  color: #374151;
}

.alerts-list li.sev-critical {
  background: #fef2f2;
  border-left: 4px solid #dc2626;
}

.alerts-list li.sev-warning {
  background: #fffbeb;
  border-left: 4px solid #f59e0b;
}

.alerts-list li.sev-info {
  background: #eff6ff;
  border-left: 4px solid #3b82f6;
}

.alert-kind {
  display: inline-block;
  font-size: 11px;
  text-transform: uppercase;
  color: #6b7280;
  margin-right: 8px;
}

.tpv-hint-text {
  margin: 0;
  color: #4b5563;
  font-size: 15px;
}

.status-panel,
.history-panel {
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.status-panel h3,
.history-panel h3 {
  margin: 0 0 16px;
  color: #1f2937;
}

.employees-status-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.employee-status-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  transition: all 0.2s;
}

.employee-status-card.status-inside {
  border-color: #10b981;
  background: #f0fdf4;
}

.employee-status-card.status-outside {
  border-color: #e5e7eb;
}

.employee-status-card.status-break {
  border-color: #f59e0b;
  background: #fffbeb;
}

.today-hours {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.employee-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.employee-info {
  flex: 1;
}

.employee-info h4 {
  margin: 0;
  color: #1f2937;
}

.employee-id {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 14px;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}

.status-badge.inside {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.outside {
  background: #fee2e2;
  color: #991b1b;
}

.status-badge.break {
  background: #fef3c7;
  color: #92400e;
}

.check-in-time {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 12px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.history-icon {
  font-size: 24px;
}

.history-info {
  flex: 1;
}

.history-employee {
  margin: 0;
  font-weight: 600;
  color: #1f2937;
}

.history-type,
.history-time {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 14px;
}

.metrics-panel {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  grid-column: 1 / -1;
}

.metric-card {
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 16px;
}

.metric-icon {
  font-size: 48px;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: #3b82f6;
  margin: 8px 0 0;
}

.loading-state,
.error-state {
  text-align: center;
  padding: 60px 20px;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .control-horario-main-interface {
    grid-template-columns: 1fr;
  }
  
  .metrics-panel {
    grid-template-columns: 1fr;
  }
  
  .check-buttons {
    flex-direction: column;
  }
  .check-buttons > button {
    flex: 1 1 100%;
  }
}
</style>
