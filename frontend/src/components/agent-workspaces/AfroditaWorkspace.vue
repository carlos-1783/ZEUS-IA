<template>
  <div class="afrodita-workspace">
    <div class="workspace-header">
      <h3>👥 Espacio de Trabajo - AFRODITA</h3>
      <div class="tabs">
        <button :class="{ active: activeTab === 'employees' }" @click="activeTab = 'employees'">
          👤 Empleados
        </button>
        <button :class="{ active: activeTab === 'schedules' }" @click="activeTab = 'schedules'">
          🕐 Horarios
        </button>
        <button :class="{ active: activeTab === 'routes' }" @click="activeTab = 'routes'">
          🚚 Rutas
        </button>
        <button :class="{ active: activeTab === 'vacations' }" @click="activeTab = 'vacations'">
          🏖️ Vacaciones
        </button>
      </div>
    </div>

    <!-- Empleados -->
    <div v-if="activeTab === 'employees'" class="employees-section">
      <div class="section-header">
        <h4>Equipo ({{ employees.length }} empleados)</h4>
        <button @click="addEmployee" class="btn-add">+ Añadir Empleado</button>
      </div>

      <div class="employees-grid">
        <div v-for="emp in employees" :key="emp.id" class="employee-card">
          <div class="employee-avatar">
            <img v-if="emp.avatar" :src="emp.avatar" :alt="emp.name" />
            <div v-else class="avatar-placeholder">{{ emp.name.charAt(0) }}</div>
          </div>
          <div class="employee-info">
            <h4>{{ emp.name }}</h4>
            <span class="employee-role">{{ emp.role }}</span>
            <span class="employee-department">{{ emp.department }}</span>
          </div>
          <div class="employee-status">
            <span :class="['status-badge', emp.status]">{{ emp.status_text }}</span>
          </div>
          <div class="employee-actions">
            <button @click="viewEmployee(emp.id)" class="btn-view">Ver Perfil</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Horarios y Fichajes -->
    <div v-if="activeTab === 'schedules'" class="schedules-section">
      <div class="date-selector">
        <button @click="changeWeek(-1)">←</button>
        <span class="current-week">{{ currentWeekText }}</span>
        <button @click="changeWeek(1)">→</button>
      </div>

      <div class="schedule-table">
        <div class="schedule-header">
          <div class="header-cell employee-col">Empleado</div>
          <div class="header-cell" v-for="day in weekDays" :key="day">{{ day }}</div>
          <div class="header-cell">Total</div>
        </div>
        <div v-for="emp in employees" :key="emp.id" class="schedule-row">
          <div class="employee-col">
            <span>{{ emp.name }}</span>
          </div>
          <div class="day-cell" v-for="day in 5" :key="day">
            <div class="time-entry">08:00 - 17:00</div>
            <div class="hours">8h</div>
          </div>
          <div class="total-cell">
            <strong>40h</strong>
          </div>
        </div>
      </div>

      <div class="pending-approvals">
        <h4>Fichajes Pendientes de Aprobación</h4>
        <div v-if="pendingTimeEntries.length === 0" class="empty-state">
          ✅ No hay fichajes pendientes
        </div>
        <div v-else class="approvals-list">
          <div v-for="entry in pendingTimeEntries" :key="entry.id" class="approval-item">
            <div class="approval-info">
              <strong>{{ entry.employee_name }}</strong>
              <span>{{ formatDate(entry.date) }} - {{ entry.type }}</span>
              <span class="approval-reason">{{ entry.reason }}</span>
            </div>
            <div class="approval-actions">
              <button @click="approveTimeEntry(entry.id)" class="btn-approve">✅</button>
              <button @click="rejectTimeEntry(entry.id)" class="btn-reject">❌</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Rutas y Logística -->
    <div v-if="activeTab === 'routes'" class="routes-section">
      <div class="section-header">
        <h4>Rutas de Hoy ({{ routes.length }})</h4>
        <button @click="createRoute" class="btn-add">+ Nueva Ruta</button>
      </div>

      <div class="routes-grid">
        <div v-for="route in routes" :key="route.id" class="route-card">
          <div class="route-header">
            <h4>{{ route.name }}</h4>
            <span :class="['route-status', route.status]">{{ route.status_text }}</span>
          </div>
          <div class="route-info">
            <div class="info-item">
              <span class="info-label">Conductor:</span>
              <span>{{ route.driver }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Vehículo:</span>
              <span>{{ route.vehicle }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Paradas:</span>
              <span>{{ route.stops }} entregas</span>
            </div>
            <div class="info-item">
              <span class="info-label">Distancia:</span>
              <span>{{ route.distance_km }} km</span>
            </div>
            <div class="info-item">
              <span class="info-label">Tiempo estimado:</span>
              <span>{{ route.estimated_time }}</span>
            </div>
          </div>
          <div class="route-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: route.progress + '%' }"></div>
            </div>
            <span class="progress-text">{{ route.completed }}/{{ route.stops }} completadas</span>
          </div>
          <div class="route-actions">
            <button @click="viewRoute(route.id)" class="btn-view">📍 Ver Mapa</button>
            <button @click="optimizeRoute(route.id)" class="btn-optimize">⚡ Optimizar</button>
          </div>
        </div>
      </div>

      <div class="fleet-status">
        <h4>Estado de la Flota</h4>
        <div class="vehicles-list">
          <div v-for="vehicle in vehicles" :key="vehicle.id" class="vehicle-item">
            <div class="vehicle-icon">🚚</div>
            <div class="vehicle-info">
              <strong>{{ vehicle.name }}</strong>
              <span>{{ vehicle.plate }}</span>
            </div>
            <div class="vehicle-status">
              <span :class="['vehicle-badge', vehicle.status]">{{ vehicle.status_text }}</span>
            </div>
            <div class="vehicle-metrics">
              <span>{{ vehicle.km_today }} km hoy</span>
              <span>Combustible: {{ vehicle.fuel }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Vacaciones -->
    <div v-if="activeTab === 'vacations'" class="vacations-section">
      <div class="vacation-calendar">
        <h4>Calendario de Ausencias</h4>
        <div class="calendar-grid">
          <!-- TODO: Implementar calendario visual -->
          <p class="calendar-placeholder">📅 Calendario próximamente</p>
        </div>
      </div>

      <div class="vacation-requests">
        <h4>Solicitudes Pendientes</h4>
        <div v-if="vacationRequests.length === 0" class="empty-state">
          ✅ No hay solicitudes pendientes
        </div>
        <div v-else class="requests-list">
          <div v-for="request in vacationRequests" :key="request.id" class="request-card">
            <div class="request-header">
              <strong>{{ request.employee_name }}</strong>
              <span class="request-type">{{ request.type }}</span>
            </div>
            <div class="request-dates">
              <span>Desde: {{ formatDate(request.from) }}</span>
              <span>Hasta: {{ formatDate(request.to) }}</span>
              <span class="request-days">{{ request.days }} días</span>
            </div>
            <div class="request-reason">
              <em>"{{ request.reason }}"</em>
            </div>
            <div class="request-actions">
              <button @click="approveVacation(request.id)" class="btn-approve">✅ Aprobar</button>
              <button @click="rejectVacation(request.id)" class="btn-reject">❌ Rechazar</button>
            </div>
          </div>
        </div>
      </div>

      <div class="vacation-summary">
        <h4>Resumen del Equipo</h4>
        <div class="summary-grid">
          <div v-for="emp in employees" :key="emp.id" class="summary-item">
            <span class="summary-name">{{ emp.name }}</span>
            <span class="summary-days">{{ emp.vacation_days_remaining }} días disponibles</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const activeTab = ref('employees')
const currentWeek = ref(new Date())

const weekDays = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie']

const employees = ref([
  {
    id: 1,
    name: 'Juan Pérez',
    role: 'Comercial',
    department: 'Ventas',
    status: 'active',
    status_text: 'Activo',
    avatar: null,
    vacation_days_remaining: 15
  },
  {
    id: 2,
    name: 'María García',
    role: 'Marketing Manager',
    department: 'Marketing',
    status: 'active',
    status_text: 'Activo',
    avatar: null,
    vacation_days_remaining: 22
  },
  {
    id: 3,
    name: 'Pablo Rodríguez',
    role: 'Repartidor',
    department: 'Logística',
    status: 'onleave',
    status_text: 'De baja',
    avatar: null,
    vacation_days_remaining: 10
  }
])

const pendingTimeEntries = ref([
  {
    id: 1,
    employee_name: 'Juan Pérez',
    date: '2024-11-04',
    type: 'Hora extra',
    reason: '2 horas extra por proyecto urgente'
  }
])

const routes = ref([
  {
    id: 1,
    name: 'Ruta Norte - Mañana',
    driver: 'Pablo Rodríguez',
    vehicle: 'Furgoneta V-001',
    stops: 12,
    distance_km: 45,
    estimated_time: '3h 20min',
    status: 'in_progress',
    status_text: 'En curso',
    progress: 60,
    completed: 7
  },
  {
    id: 2,
    name: 'Ruta Centro - Tarde',
    driver: 'Ana López',
    vehicle: 'Furgoneta V-002',
    stops: 8,
    distance_km: 32,
    estimated_time: '2h 15min',
    status: 'pending',
    status_text: 'Pendiente',
    progress: 0,
    completed: 0
  }
])

const vehicles = ref([
  {
    id: 1,
    name: 'Furgoneta V-001',
    plate: '1234-ABC',
    status: 'active',
    status_text: 'En ruta',
    km_today: 28,
    fuel: 65
  },
  {
    id: 2,
    name: 'Furgoneta V-002',
    plate: '5678-DEF',
    status: 'idle',
    status_text: 'Disponible',
    km_today: 0,
    fuel: 92
  }
])

const vacationRequests = ref([
  {
    id: 1,
    employee_name: 'María García',
    type: 'Vacaciones',
    from: '2024-11-20',
    to: '2024-11-24',
    days: 5,
    reason: 'Viaje familiar'
  }
])

const currentWeekText = computed(() => {
  const start = new Date(currentWeek.value)
  start.setDate(start.getDate() - start.getDay() + 1)
  const end = new Date(start)
  end.setDate(start.getDate() + 4)
  
  return `${start.getDate()}/${start.getMonth() + 1} - ${end.getDate()}/${end.getMonth() + 1}`
})

function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function changeWeek(direction) {
  const newDate = new Date(currentWeek.value)
  newDate.setDate(newDate.getDate() + (direction * 7))
  currentWeek.value = newDate
}

function addEmployee() {
  console.log('Añadir empleado')
}

function viewEmployee(id) {
  console.log('Ver empleado:', id)
}

function approveTimeEntry(id) {
  console.log('Aprobar fichaje:', id)
}

function rejectTimeEntry(id) {
  console.log('Rechazar fichaje:', id)
}

function createRoute() {
  console.log('Crear nueva ruta')
}

function viewRoute(id) {
  console.log('Ver ruta en mapa:', id)
}

function optimizeRoute(id) {
  console.log('Optimizar ruta:', id)
}

function approveVacation(id) {
  if (confirm('¿Aprobar esta solicitud de vacaciones?')) {
    console.log('Aprobar vacaciones:', id)
  }
}

function rejectVacation(id) {
  const reason = prompt('¿Motivo del rechazo?')
  if (reason) {
    console.log('Rechazar vacaciones:', id, reason)
  }
}
</script>

<style scoped>
.afrodita-workspace {
  padding: 20px;
}

.workspace-header h3 {
  font-size: 24px;
  margin-bottom: 15px;
  color: #1f2937;
}

.tabs {
  display: flex;
  gap: 10px;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 30px;
}

.tabs button {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  transition: all 0.3s;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tabs button.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h4 {
  font-size: 18px;
  color: #1f2937;
}

.btn-add,
.btn-approve,
.btn-reject {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-add {
  background: #3b82f6;
  color: white;
}

.btn-add:hover {
  background: #2563eb;
}

.employees-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.employee-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.employee-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 auto;
}

.employee-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 32px;
  font-weight: 700;
}

.employee-info {
  text-align: center;
}

.employee-info h4 {
  font-size: 18px;
  margin-bottom: 5px;
}

.employee-role {
  display: block;
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 3px;
}

.employee-department {
  display: block;
  font-size: 12px;
  color: #9ca3af;
}

.employee-status {
  text-align: center;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.active {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.onleave {
  background: #fef3c7;
  color: #92400e;
}

.employee-actions {
  text-align: center;
}

.btn-view {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.date-selector {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  margin-bottom: 30px;
}

.date-selector button {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 18px;
}

.current-week {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.schedule-table {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 30px;
}

.schedule-header,
.schedule-row {
  display: grid;
  grid-template-columns: 200px repeat(5, 1fr) 100px;
  border-bottom: 1px solid #e5e7eb;
}

.schedule-header {
  background: #f9fafb;
  font-weight: 600;
}

.header-cell,
.employee-col,
.day-cell,
.total-cell {
  padding: 15px;
  text-align: center;
  border-right: 1px solid #e5e7eb;
}

.employee-col {
  text-align: left;
  font-weight: 500;
}

.time-entry {
  font-size: 13px;
  color: #374151;
}

.hours {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.total-cell strong {
  color: #059669;
}

.pending-approvals {
  margin-top: 30px;
}

.pending-approvals h4 {
  font-size: 18px;
  margin-bottom: 15px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.approvals-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.approval-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.approval-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.approval-reason {
  font-size: 13px;
  color: #6b7280;
}

.approval-actions {
  display: flex;
  gap: 10px;
}

.btn-approve {
  background: #10b981;
  color: white;
}

.btn-reject {
  background: #ef4444;
  color: white;
}

.routes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.route-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.route-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.route-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.route-status.in_progress {
  background: #dbeafe;
  color: #1e40af;
}

.route-status.pending {
  background: #fef3c7;
  color: #92400e;
}

.route-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 15px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.info-label {
  color: #6b7280;
}

.route-progress {
  margin-bottom: 15px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 5px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  transition: width 0.3s;
}

.progress-text {
  font-size: 12px;
  color: #6b7280;
}

.route-actions {
  display: flex;
  gap: 10px;
}

.route-actions button {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.fleet-status h4 {
  font-size: 18px;
  margin-bottom: 15px;
}

.vehicles-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vehicle-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.vehicle-icon {
  font-size: 32px;
}

.vehicle-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.vehicle-badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.vehicle-badge.active {
  background: #dbeafe;
  color: #1e40af;
}

.vehicle-badge.idle {
  background: #d1fae5;
  color: #065f46;
}

.vehicle-metrics {
  display: flex;
  gap: 15px;
  font-size: 13px;
  color: #6b7280;
}

.vacation-calendar,
.vacation-requests,
.vacation-summary {
  margin-bottom: 30px;
}

.vacation-calendar h4,
.vacation-requests h4,
.vacation-summary h4 {
  font-size: 18px;
  margin-bottom: 15px;
}

.calendar-placeholder {
  text-align: center;
  padding: 60px;
  font-size: 18px;
  color: #9ca3af;
}

.requests-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.request-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
}

.request-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.request-type {
  padding: 4px 12px;
  background: #dbeafe;
  color: #1e40af;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.request-dates {
  display: flex;
  gap: 15px;
  margin-bottom: 10px;
  font-size: 14px;
  color: #6b7280;
}

.request-days {
  color: #059669;
  font-weight: 600;
}

.request-reason {
  margin-bottom: 15px;
  font-size: 14px;
  color: #4b5563;
}

.request-actions {
  display: flex;
  gap: 10px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 15px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  padding: 15px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.summary-days {
  color: #059669;
  font-weight: 600;
}
</style>

