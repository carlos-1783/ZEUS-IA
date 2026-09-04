<template>
  <div class="control-horario-container">
    <!-- Botón de vuelta al Dashboard: en flujo normal (antes position:fixed
         en la esquina superior izquierda, exactamente sobre el título
         "Control Horario Universal" -> se solapaban en todos los anchos
         de pantalla, no solo móvil). Mismo patrón que el resto de vistas
         (Seguros, Ajustes, /agents): un enlace/botón "volver" en flujo,
         antes de la cabecera. -->
    <button @click="goToDashboard" class="back-to-dashboard-btn">
      <span class="btn-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M4 20h16"/></svg></span>
      <span class="btn-label">{{ $t('controlHorario.backToDashboard') }}</span>
    </button>

    <!-- Header del Control Horario -->
    <div class="control-horario-header">
      <div class="control-horario-title-section">
        <h1 class="control-horario-title">
          <span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg></span>
          {{ $t('controlHorario.title') }}
        </h1>
        <p class="control-horario-subtitle">{{ $t('controlHorario.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <button @click="checkStatus" class="header-btn">
          <span class="header-btn-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 1 3 6.7"/><path d="M3 21v-5h5"/></svg></span>
          {{ $t('controlHorario.refresh') }}
        </button>
        <div v-if="businessProfile" class="business-profile-badge">
          <span class="header-btn-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1M10 21v-4h4v4"/></svg></span>
          {{ getBusinessProfileLabel(businessProfile) }}
        </div>
      </div>
    </div>

    <!-- Interfaz Principal -->
    <div class="control-horario-main-interface" v-if="!loading && !error">
      
      <!-- Empleado: jornada = login/logout (sin fichaje manual en pantalla) -->
      <div v-if="authStore.isEmployee" class="jornada-employee-panel">
        <p class="jornada-intro">{{ $t('controlHorario.jornadaEmployeeIntro') }}</p>
        <div class="jornada-status" :class="{ active: jornadaActiva }">
          <span class="jornada-dot" aria-hidden="true" />
          <strong>{{ jornadaActiva ? $t('controlHorario.enTurno') : $t('controlHorario.fueraTurno') }}</strong>
          <span v-if="jornadaActiva && entradaLabel" class="jornada-time">{{ $t('controlHorario.entrada') }}: {{ entradaLabel }}</span>
        </div>
        <button type="button" class="btn-close-shift" @click="cerrarJornada">{{ $t('controlHorario.closeShift') }}</button>
      </div>

      <!-- Panel de fichaje manual (dueño / administrador) -->
      <div v-if="!authStore.isEmployee" class="check-in-out-panel">
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
              <span class="method-icon" aria-hidden="true">
                <svg v-if="method.id === 'face'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8a2 2 0 0 1 2-2h1.5l1-1.5h7l1 1.5H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8Z"/><circle cx="12" cy="13" r="3.5"/></svg>
                <svg v-else-if="method.id === 'qr'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="6" height="6" rx="1"/><rect x="14.5" y="3.5" width="6" height="6" rx="1"/><rect x="3.5" y="14.5" width="6" height="6" rx="1"/><path d="M14.5 14.5h2.5v2.5h-2.5zM19.5 19.5h1v1h-1zM14.5 19.5v2M19.5 14.5h2"/></svg>
                <svg v-else-if="method.id === 'code'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4 7 20M17 4l-2 16M4 9h16M3 15h16"/></svg>
                <svg v-else-if="method.id === 'location'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6.5 7-11.5A7 7 0 0 0 5 9.5C5 14.5 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/></svg>
                <svg v-else-if="method.id === 'remote'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="11" rx="1.5"/><path d="M2 19h20M9 19l1-3h4l1 3"/></svg>
              </span>
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
          <div class="employee-selector">
            <label>{{ $t('controlHorario.employeePhone') }}</label>
            <input
              v-model="employeePhone"
              type="tel"
              class="employee-select"
              :placeholder="$t('controlHorario.employeePhonePlaceholder')"
            />
          </div>
          <div v-if="selectedMethod === 'code'" class="employee-selector">
            <label>PIN empleado</label>
            <input
              v-model="employeePin"
              type="password"
              class="employee-select"
              placeholder="PIN TPV"
              autocomplete="off"
            />
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
            <span class="alert-kind">{{ alertKindLabel(a.kind) }}</span>
            {{ a.message }}
          </li>
        </ul>
      </div>

      <div v-if="costEngine && costEngine.company_id" class="cost-engine-panel">
        <h3>💶 Coste laboral (tiempo real)</h3>
        <div class="metrics-panel cost-metrics-inline">
          <div class="metric-card">
            <div class="metric-icon">⏱️</div>
            <div class="metric-content">
              <h4>Horas hoy</h4>
              <p class="metric-value">{{ hoursWorkedToday != null ? hoursWorkedToday + 'h' : '—' }}</p>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">💰</div>
            <div class="metric-content">
              <h4>Coste hoy</h4>
              <p class="metric-value">{{ realTimeCostTotal != null ? realTimeCostTotal + ' €' : '—' }}</p>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">👷</div>
            <div class="metric-content">
              <h4>Sesiones activas</h4>
              <p class="metric-value">{{ costEngine.active_employees ?? activeCostSessions.length }}</p>
            </div>
          </div>
        </div>
        <ul v-if="activeCostSessions.length" class="active-sessions-list">
          <li v-for="s in activeCostSessions" :key="s.session_id">
            <strong>{{ s.employee_name || s.employee_id }}</strong>
            — {{ s.hours }}h · {{ s.real_time_cost_eur }} €
          </li>
        </ul>
        <p v-else class="no-active-sessions">Sin sesiones activas con coste calculado.</p>
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
const employeePhone = ref('')
const selectedMethod = ref('qr')
const todayRecords = ref([])
const currentLocation = ref({ latitude: null, longitude: null })
const smartAlerts = ref([])
const smartTpv = ref(null)
const todayHoursByEmployee = ref({})
const costEngine = ref(null)
const employeePin = ref('')
let refreshTimer = null

const V1_METHOD_MAP = { qr: 'qr', code: 'pin', location: 'geo', remote: 'device', face: 'device' }

// Traduce el código crudo de alerta (backend: smart_time_control_service.py,
// alert_kind en minúsculas, mostrado en mayúsculas por CSS text-transform)
// a una etiqueta corta en español. Mismo criterio que ya se aplicó a los
// badges UNKNOWN/CONTROLLED_UNTRUSTED — nunca se muestra el código crudo.
const ALERT_KIND_LABELS = {
  empleado_no_ficha: 'Sin fichar',
  exceso_horas: 'Exceso de horas',
  turno_sin_cubrir: 'Turno sin cubrir',
}
function alertKindLabel(kind) {
  if (!kind) return ''
  const key = String(kind).toLowerCase()
  return ALERT_KIND_LABELS[key] || key.replace(/_/g, ' ')
}

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

const activeCostSessions = computed(() => {
  const sessions = costEngine.value?.active_sessions
  return Array.isArray(sessions) ? sessions : []
})

const realTimeCostTotal = computed(() => {
  const v = costEngine.value?.total_cost_today
  if (v == null || Number.isNaN(Number(v))) return null
  return Math.round(Number(v) * 100) / 100
})

const hoursWorkedToday = computed(() => {
  const v = costEngine.value?.total_hours_today
  if (v == null || Number.isNaN(Number(v))) return null
  return Math.round(Number(v) * 100) / 100
})

const jornadaActiva = computed(() => !!(authStore.user && authStore.user.jornada && authStore.user.jornada.in_turno))

const entradaLabel = computed(() => {
  const j = authStore.user?.jornada
  if (!j?.check_in_time) return ''
  try {
    return new Date(j.check_in_time).toLocaleString()
  } catch {
    return ''
  }
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

const refreshProfileFromMe = async () => {
  try {
    const api = (await import('@/api/index')).default
    const data = await api.getCurrentUser()
    if (data && authStore.user) {
      Object.assign(authStore.user, {
        jornada: data.jornada,
        company_employee: data.company_employee,
      })
    }
  } catch (_) {
    /* mantener perfil actual */
  }
}

const cerrarJornada = async () => {
  await authStore.logout()
  router.push(`/login?redirect=${encodeURIComponent('/control-horario')}`)
}

const checkStatus = async () => {
  loading.value = true
  error.value = null
  
  try {
    await refreshProfileFromMe()
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

    costEngine.value = bootstrap?.cost_engine?.company_id ? bootstrap.cost_engine : null
    
  } catch (err) {
    console.error('Error cargando estado:', err)
    error.value = err.message || 'Error al cargar el estado'
  } finally {
    loading.value = false
  }
}

const postCheckinV1 = async (type) => {
  const token = authStore.getToken ? authStore.getToken() : authStore.token
  if (!token) throw new Error('No hay token')
  const cid = costEngine.value?.company_id
  if (!cid) throw new Error('No hay empresa asociada. Configura la empresa antes de fichar.')
  const method = V1_METHOD_MAP[selectedMethod.value] || 'device'
  const body = {
    company_id: cid,
    employee_id: selectedEmployee.value,
    type,
    method
  }
  if (method === 'qr') {
    body.qr_token = `ui-${selectedEmployee.value}-${Date.now()}`
  }
  if (method === 'pin') {
    const pin = (employeePin.value || '').trim()
    if (!pin) throw new Error('PIN requerido para fichaje por código.')
    body.pin = pin
  }
  if (method === 'geo') {
    body.lat = currentLocation.value.latitude
    body.lng = currentLocation.value.longitude
  }
  if (method === 'device') {
    body.device_id = (navigator.userAgent || 'browser').slice(0, 128)
  }
  const api = (await import('@/services/api')).default
  return api.post('/api/v1/checkin', body, token)
}

const handleCheckIn = async () => {
  if (!selectedEmployee.value || !selectedMethod.value) return
  
  checking.value = true
  try {
    const data = await postCheckinV1('entrada')
    alert(`✅ Entrada registrada — coste parcial: ${data.cost_eur ?? '—'} €`)
    await checkStatus()
    selectedEmployee.value = ''
    employeePin.value = ''
    
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
    const data = await postCheckinV1('pausa_inicio')
    alert(`✅ ${data.success ? 'Pausa iniciada' : 'OK'}`)
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
    const data = await postCheckinV1('pausa_fin')
    alert(`✅ ${data.success ? 'Pausa finalizada' : 'OK'}`)
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
    const data = await postCheckinV1('salida')
    alert(`✅ Salida registrada — ${data.hours ?? '—'}h · ${data.cost_eur ?? '—'} €`)
    await checkStatus()
    selectedEmployee.value = ''
    employeePin.value = ''
    
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

const onBeforeUnloadJornada = (e) => {
  if (authStore.isEmployee && jornadaActiva.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  checkStatus()
  window.addEventListener('beforeunload', onBeforeUnloadJornada)
  refreshTimer = window.setInterval(() => {
    if (!loading.value && !checking.value) checkStatus()
  }, 45000)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnloadJornada)
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.control-horario-container {
  min-height: 100vh;
  background-image: var(--zeus-bg);
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  padding: 20px;
  position: relative;
}

.control-horario-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}

.control-horario-container > * {
  position: relative;
}

.back-to-dashboard-btn {
  /* En flujo normal (bug: antes position:fixed en (20,20), exactamente
     donde arranca el título del header -> se solapaban en TODOS los
     anchos, no solo móvil). margin-bottom la separa del header. */
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px 20px;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  border: 1px solid #D1D5DB;
  border-radius: var(--zeus-radius-sm, 8px);
  cursor: pointer;
  font-weight: 600;
  box-shadow: var(--zeus-shadow-btn, 0 2px 4px rgba(0, 0, 0, 0.15));
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.back-to-dashboard-btn:hover {
  border-color: #9aa2af;
  transform: translateY(-1px);
}

.back-to-dashboard-btn:active {
  box-shadow: var(--zeus-shadow-btn-active, 0 1px 1px rgba(0, 0, 0, 0.1));
  transform: translateY(0);
}

.control-horario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: 20px;
  background: var(--zeus-surface, white);
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0,0,0,0.1));
}

.control-horario-title {
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 32px;
  color: var(--zeus-text, #1f2937);
}

.title-icon {
  display: inline-flex;
  flex-shrink: 0;
  margin-top: 4px;
  color: var(--zeus-accent, #4f46e5);
}

.title-icon svg {
  width: 30px;
  height: 30px;
}

.btn-icon svg {
  width: 16px;
  height: 16px;
}

.header-btn-icon {
  display: inline-flex;
  vertical-align: -4px;
  margin-right: 4px;
}

.header-btn-icon svg {
  width: 16px;
  height: 16px;
}

.control-horario-subtitle {
  margin: 8px 0 0;
  color: var(--zeus-text-secondary, #6b7280);
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* Pendiente señalado en la Ronda 3 ("botón verde plano, tercera
   variante fuera de la regla de dos estados") — "Actualizar" es una
   utilidad repetible, no la acción de mayor jerarquía de esta vista
   (esa es fichar entrada/salida) -> secundario blanco/borde. */
.header-btn {
  padding: 10px 20px;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  border: 1px solid #D1D5DB;
  border-radius: var(--zeus-radius-sm, 8px);
  cursor: pointer;
  font-weight: 600;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.header-btn:hover {
  border-color: #9aa2af;
}

.business-profile-badge {
  padding: 10px 20px;
  background: var(--zeus-bg-subtle, #f3f4f6);
  border-radius: var(--zeus-radius-sm, 8px);
  font-weight: 600;
  color: var(--zeus-text-secondary, #374151);
}

.control-horario-main-interface {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  /* Bug real: .status-panel y .history-panel comparten fila (sin
     grid-column propio) y CSS Grid las estira por defecto (align-items:
     stretch) a la altura de la más alta de las dos -> cuando una lista
     es mucho más corta que la otra (p.ej. pocos/ningún empleado dentro
     vs historial con varios registros), la tarjeta corta queda con un
     hueco en blanco al final, del tamaño de la diferencia. align-items:
     start hace que cada tarjeta ocupe solo su altura de contenido real. */
  align-items: start;
}

.check-in-out-panel {
  background: var(--zeus-surface, white);
  padding: 24px;
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0,0,0,0.1));
  grid-column: 1 / -1;
}

.method-selector h3 {
  margin: 0 0 16px;
  color: var(--zeus-text, #1f2937);
}

.methods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.method-btn {
  position: relative;
  padding: 16px;
  background: var(--zeus-bg-flat, #f9fafb);
  border: 2px solid var(--zeus-border, #e5e7eb);
  border-radius: var(--zeus-radius-sm, 8px);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.method-btn:hover:not(:disabled) {
  border-color: var(--zeus-accent, #3b82f6);
  background: var(--zeus-accent-soft, #eff6ff);
}

/* Selector de metodo de fichaje: es seleccion DENTRO de un grupo (5
   metodos), no la accion principal de la vista -> sin gradiente, solo
   borde+fondo con tinte, segun la regla ya establecida en rondas
   anteriores ("seleccion dentro de un grupo: gradiente retirado, solo
   negrita y/o cambio de borde"). Antes llevaba una barra ::after con el
   gradiente de 4 paradas CON naranja (valor obsoleto de Ronda 1, ni
   siquiera coincidia con el --zeus-accent-gradient de 3 paradas actual)
   — corregido al pasar por este bloque para los iconos SVG. */
.method-btn.active {
  border-color: var(--zeus-accent, #3b82f6);
  background: var(--zeus-accent-soft, #dbeafe);
  font-weight: 600;
}

.method-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.method-icon {
  display: inline-flex;
  color: var(--zeus-text-secondary, #52607a);
}

.method-btn.active .method-icon {
  color: var(--zeus-accent, #4f46e5);
}

.method-icon svg {
  width: 28px;
  height: 28px;
}

.check-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.employee-selector label {
  font-weight: 600;
  color: var(--zeus-text-secondary, #374151);
  margin-bottom: 8px;
  display: block;
}

.employee-select {
  width: 100%;
  padding: 12px;
  border: 2px solid var(--zeus-border, #e5e7eb);
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: 16px;
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  color: var(--zeus-text, #0f172a);
  background: var(--zeus-surface, #fff);
}

@media (prefers-reduced-motion: reduce) {
  .method-btn {
    transition-duration: 1ms;
  }
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
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  color: var(--zeus-text-on-accent, white);
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.btn-check-in {
  background: var(--zeus-success, #10b981);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 10px rgba(16, 185, 129, 0.2);
}

.btn-check-in:hover:not(:disabled) {
  background: #059669;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.08), 0 8px 18px rgba(16, 185, 129, 0.28);
  transform: translateY(-1px);
}

.btn-check-out {
  background: var(--zeus-danger, #ef4444);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 10px rgba(239, 68, 68, 0.2);
}

.btn-check-out:hover:not(:disabled) {
  background: #dc2626;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.08), 0 8px 18px rgba(239, 68, 68, 0.28);
  transform: translateY(-1px);
}

.btn-break-start {
  background: var(--zeus-warning, #f59e0b);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 10px rgba(245, 158, 11, 0.2);
}

.btn-break-start:hover:not(:disabled) {
  background: #d97706;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.08), 0 8px 18px rgba(245, 158, 11, 0.28);
  transform: translateY(-1px);
}

.btn-break-end {
  background: var(--zeus-accent-2, #6366f1);
  box-shadow: var(--zeus-shadow-btn, 0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 10px rgba(79, 70, 229, 0.2));
}

.btn-break-end:hover:not(:disabled) {
  background: var(--zeus-accent, #4f46e5);
  box-shadow: var(--zeus-shadow-btn-hover, 0 2px 4px rgba(15, 23, 42, 0.08), 0 8px 18px rgba(79, 70, 229, 0.28));
  transform: translateY(-1px);
}

.btn-check-in:disabled,
.btn-check-out:disabled,
.btn-break-start:disabled,
.btn-break-end:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (prefers-reduced-motion: reduce) {
  .btn-check-in:hover:not(:disabled),
  .btn-check-out:hover:not(:disabled),
  .btn-break-start:hover:not(:disabled),
  .btn-break-end:hover:not(:disabled) {
    transform: none;
  }
}

.alerts-panel,
.tpv-hint-panel {
  grid-column: 1 / -1;
  background: var(--zeus-surface, white);
  padding: 20px 24px;
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0, 0, 0, 0.08));
}

.alerts-panel h3,
.tpv-hint-panel h3 {
  margin: 0 0 12px;
  color: var(--zeus-text, #1f2937);
}

.alerts-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.alerts-list li {
  padding: 10px 12px;
  border-radius: var(--zeus-radius-sm, 8px);
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--zeus-text-secondary, #374151);
}

.alerts-list li.sev-critical {
  background: var(--zeus-danger-soft, #fef2f2);
  border-left: 4px solid var(--zeus-danger, #dc2626);
}

.alerts-list li.sev-warning {
  background: var(--zeus-warning-soft, #fffbeb);
  border-left: 4px solid var(--zeus-warning, #f59e0b);
}

.alerts-list li.sev-info {
  background: var(--zeus-info-soft, #eff6ff);
  border-left: 4px solid var(--zeus-info, #3b82f6);
}

.alert-kind {
  display: inline-block;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--zeus-text-muted, #6b7280);
  margin-right: 8px;
}

.tpv-hint-text {
  margin: 0;
  color: var(--zeus-text-secondary, #4b5563);
  font-size: 15px;
}

.status-panel,
.history-panel {
  background: var(--zeus-surface, white);
  padding: 24px;
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0,0,0,0.1));
}

.status-panel h3,
.history-panel h3 {
  margin: 0 0 16px;
  color: var(--zeus-text, #1f2937);
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
  border: 2px solid var(--zeus-border, #e5e7eb);
  border-radius: var(--zeus-radius-sm, 8px);
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.employee-status-card.status-inside {
  border-color: var(--zeus-success, #10b981);
  background: var(--zeus-success-soft, #f0fdf4);
}

.employee-status-card.status-outside {
  border-color: var(--zeus-border, #e5e7eb);
}

.employee-status-card.status-break {
  border-color: var(--zeus-warning, #f59e0b);
  background: var(--zeus-warning-soft, #fffbeb);
}

.today-hours {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--zeus-text-secondary, #6b7280);
}

.employee-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--zeus-radius-full, 50%);
  background: var(--zeus-accent, #3b82f6);
  color: var(--zeus-text-on-accent, white);
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
  color: var(--zeus-text, #1f2937);
}

.employee-id {
  margin: 4px 0 0;
  color: var(--zeus-text-secondary, #6b7280);
  font-size: 14px;
}

.status-badge {
  padding: 6px 12px;
  border-radius: var(--zeus-radius-full, 20px);
  font-size: 14px;
  font-weight: 600;
}

.status-badge.inside {
  background: var(--zeus-success-soft, #d1fae5);
  color: #065f46;
}

.status-badge.outside {
  background: var(--zeus-danger-soft, #fee2e2);
  color: #991b1b;
}

.status-badge.break {
  background: var(--zeus-warning-soft, #fef3c7);
  color: #92400e;
}

.check-in-time {
  margin: 4px 0 0;
  color: var(--zeus-text-secondary, #6b7280);
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
  background: var(--zeus-bg-flat, #f9fafb);
  border-radius: var(--zeus-radius-sm, 8px);
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
  color: var(--zeus-text, #1f2937);
}

.history-type,
.history-time {
  margin: 4px 0 0;
  color: var(--zeus-text-secondary, #6b7280);
  font-size: 14px;
}

.metrics-panel {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  grid-column: 1 / -1;
}

.cost-engine-panel {
  grid-column: 1 / -1;
  background: var(--zeus-surface, white);
  padding: 20px 24px;
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0,0,0,0.1));
}

.cost-engine-panel h3 {
  margin: 0 0 16px;
  color: var(--zeus-text, #1f2937);
}

.cost-metrics-inline {
  grid-column: auto;
  margin-bottom: 12px;
}

.active-sessions-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.active-sessions-list li {
  padding: 8px 0;
  border-top: 1px solid var(--zeus-border, #e5e7eb);
  color: var(--zeus-text-secondary, #374151);
}

.no-active-sessions {
  margin: 0;
  color: var(--zeus-text-secondary, #6b7280);
  font-size: 14px;
}

.metric-card {
  background: var(--zeus-surface, white);
  padding: 24px;
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0,0,0,0.1));
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
  color: var(--zeus-accent, #3b82f6);
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
  border: 4px solid var(--zeus-border, #e5e7eb);
  border-top-color: var(--zeus-accent, #3b82f6);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 1.5s;
  }
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

.jornada-employee-panel {
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, transparent);
  border-radius: var(--zeus-radius, 12px);
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: var(--zeus-shadow, 0 2px 4px rgba(0, 0, 0, 0.08));
}

.jornada-intro {
  margin: 0 0 12px;
  color: var(--zeus-text-secondary, #475569);
  font-size: 0.95rem;
}

.jornada-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

/* Estado "en turno" del propio empleado: usa el color semantico de
   estado (verde = presente), coherente con el resto de indicadores de
   presencia de la pantalla (status-badge.inside, employee-status-card). */
.jornada-status.active .jornada-dot {
  background: var(--zeus-success, #10b981);
  box-shadow: 0 0 0 3px var(--zeus-success-soft, #e9faf3);
}

.jornada-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--zeus-text-muted, #94a3b8);
  transition: background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.jornada-time {
  font-size: 0.9rem;
  color: var(--zeus-text-secondary, #64748b);
}

.btn-close-shift {
  padding: 10px 18px;
  border-radius: var(--zeus-radius-sm, 8px);
  border: 1px solid var(--zeus-border-strong, #cbd5e1);
  background: var(--zeus-bg-flat, #f8fafc);
  color: var(--zeus-text, #0f172a);
  cursor: pointer;
  font-weight: 600;
  transition: background-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.btn-close-shift:hover {
  background: var(--zeus-border, #e2e8f0);
  box-shadow: var(--zeus-shadow-btn-ghost-hover, 0 3px 8px rgba(15, 23, 42, 0.08));
}
</style>
