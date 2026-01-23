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
              :disabled="!config.methods_enabled || !config.methods_enabled.includes(method.id)"
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
          </div>
        </div>
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
            :class="{ 'status-inside': employee.status === 'inside', 'status-outside': employee.status === 'outside' }"
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
              <span v-else class="status-badge outside">
                🚪 {{ $t('controlHorario.outside') }}
              </span>
              <p v-if="employee.check_in_time" class="check-in-time">
                {{ formatTime(employee.check_in_time) }}
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
              <span v-else>🚪</span>
            </div>
            <div class="history-info">
              <p class="history-employee">{{ getEmployeeName(record.employee_id) }}</p>
              <p class="history-type">{{ record.type === 'check-in' ? $t('controlHorario.checkIn') : $t('controlHorario.checkOut') }}</p>
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
import { ref, computed, onMounted } from 'vue'
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
  return employees.value.filter(emp => emp.status === 'inside').length
})

const attendanceRate = computed(() => {
  if (employees.value.length === 0) return 0
  return Math.round((employeesInside.value / employees.value.length) * 100)
})

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

    // Obtener información del sistema
    const api = (await import('@/services/api')).default
    const infoData = await api.get('/api/v1/control-horario', token)
    
    businessProfile.value = infoData.business_profile
    config.value = infoData.config || {}
    
    // Obtener estado de empleados
    const statusData = await api.get('/api/v1/control-horario/status', token)
    
    // Obtener lista de empleados
    const employeesData = await api.get('/api/v1/control-horario/employees', token)
    
    // Actualizar empleados con estado
    const employeesMap = {}
    if (employeesData.employees) {
      Object.keys(employeesData.employees).forEach(empId => {
        employeesMap[empId] = {
          id: empId,
          name: empId, // En producción, buscaría el nombre real
          status: employeesData.employees[empId].status || 'outside',
          check_in_time: employeesData.employees[empId].check_in_time
        }
      })
    }
    
    // Por ahora, usar lista básica si no hay empleados
    if (Object.keys(employeesMap).length === 0) {
      employees.value = [
        { id: 'emp1', name: 'Empleado 1', status: 'outside' },
        { id: 'emp2', name: 'Empleado 2', status: 'outside' }
      ]
    } else {
      employees.value = Object.values(employeesMap)
    }
    
    // Actualizar estado según status
    if (statusData.status && statusData.status.employees) {
      Object.keys(statusData.status.employees).forEach(empId => {
        const emp = employees.value.find(e => e.id === empId)
        if (emp) {
          emp.status = statusData.status.employees[empId].status
          emp.check_in_time = statusData.status.employees[empId].check_in_time
        }
      })
    }
    
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.btn-check-in,
.btn-check-out {
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

.btn-check-in:disabled,
.btn-check-out:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
    grid-template-columns: 1fr;
  }
}
</style>
