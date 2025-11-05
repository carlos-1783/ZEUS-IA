<template>
  <div class="thalos-workspace">
    <div class="workspace-header">
      <h3>🛡️ Espacio de Trabajo - THALOS</h3>
      <div class="tabs">
        <button :class="{ active: activeTab === 'alerts' }" @click="activeTab = 'alerts'">
          🚨 Alertas
        </button>
        <button :class="{ active: activeTab === 'scans' }" @click="activeTab = 'scans'">
          🔍 Escaneos
        </button>
        <button :class="{ active: activeTab === 'threats' }" @click="activeTab = 'threats'">
          ⚔️ Amenazas
        </button>
        <button :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'">
          📋 Logs
        </button>
      </div>
    </div>

    <!-- Alertas -->
    <div v-if="activeTab === 'alerts'" class="alerts-section">
      <div class="section-header">
        <h4>Alertas de Seguridad en Tiempo Real</h4>
        <div class="alert-filters">
          <button :class="{ active: alertFilter === 'all' }" @click="alertFilter = 'all'">
            Todas
          </button>
          <button :class="{ active: alertFilter === 'critical' }" @click="alertFilter = 'critical'">
            Críticas
          </button>
          <button :class="{ active: alertFilter === 'high' }" @click="alertFilter = 'high'">
            Altas
          </button>
        </div>
      </div>

      <div class="alerts-list">
        <div v-for="alert in filteredAlerts" :key="alert.id" class="alert-card" :class="alert.severity">
          <div class="alert-icon">{{ getAlertIcon(alert.severity) }}</div>
          <div class="alert-content">
            <div class="alert-header">
              <h4>{{ alert.title }}</h4>
              <span class="alert-severity" :class="alert.severity">{{ alert.severity.toUpperCase() }}</span>
            </div>
            <p class="alert-description">{{ alert.description }}</p>
            <div class="alert-details">
              <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
              <span class="alert-source">{{ alert.source }}</span>
            </div>
          </div>
          <div class="alert-actions">
            <button @click="resolveAlert(alert.id)" class="btn-resolve">✓ Resolver</button>
            <button @click="viewDetails(alert.id)" class="btn-details">Ver detalles</button>
          </div>
        </div>

        <div v-if="filteredAlerts.length === 0" class="empty-state">
          <p>✅ No hay alertas {{ alertFilter !== 'all' ? `de nivel ${alertFilter}` : '' }}</p>
        </div>
      </div>
    </div>

    <!-- Escaneos -->
    <div v-if="activeTab === 'scans'" class="scans-section">
      <div class="section-header">
        <h4>Historial de Escaneos</h4>
        <button @click="startNewScan" class="btn-new-scan">🔍 Nuevo Escaneo</button>
      </div>

      <div class="scan-progress" v-if="isScanning">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: scanProgress + '%' }"></div>
        </div>
        <p>Escaneando sistema... {{ scanProgress }}%</p>
      </div>

      <div class="scans-list">
        <div v-for="scan in scans" :key="scan.id" class="scan-card">
          <div class="scan-header">
            <h4>{{ scan.type }}</h4>
            <span class="scan-status" :class="scan.status">{{ scan.status }}</span>
          </div>
          <div class="scan-stats">
            <div class="stat">
              <span class="stat-label">Archivos:</span>
              <span class="stat-value">{{ scan.files_scanned.toLocaleString() }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Amenazas:</span>
              <span class="stat-value" :class="{ danger: scan.threats_found > 0 }">{{ scan.threats_found }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Duración:</span>
              <span class="stat-value">{{ scan.duration }}</span>
            </div>
          </div>
          <div class="scan-meta">
            <span>{{ formatDateTime(scan.timestamp) }}</span>
          </div>
          <div class="scan-actions">
            <button @click="viewScanReport(scan.id)" class="btn-view">📄 Ver Reporte</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Amenazas -->
    <div v-if="activeTab === 'threats'" class="threats-section">
      <div class="section-header">
        <h4>Amenazas Detectadas y Bloqueadas</h4>
      </div>

      <div class="threats-stats">
        <div class="threat-stat-card">
          <div class="stat-icon">🛡️</div>
          <div class="stat-content">
            <h3>{{ totalThreatsBlocked }}</h3>
            <p>Amenazas Bloqueadas (30 días)</p>
          </div>
        </div>
        <div class="threat-stat-card">
          <div class="stat-icon">⚔️</div>
          <div class="stat-content">
            <h3>{{ activeThreats }}</h3>
            <p>Amenazas Activas</p>
          </div>
        </div>
        <div class="threat-stat-card">
          <div class="stat-icon">✅</div>
          <div class="stat-content">
            <h3>{{ threatSuccessRate }}%</h3>
            <p>Tasa de Bloqueo</p>
          </div>
        </div>
      </div>

      <div class="threats-list">
        <div v-for="threat in threats" :key="threat.id" class="threat-card">
          <div class="threat-type">
            <span class="threat-icon">{{ getThreatIcon(threat.type) }}</span>
            <div>
              <h4>{{ threat.type }}</h4>
              <p class="threat-description">{{ threat.description }}</p>
            </div>
          </div>
          <div class="threat-info">
            <div class="info-item">
              <span class="label">IP Origen:</span>
              <span class="value">{{ threat.source_ip }}</span>
            </div>
            <div class="info-item">
              <span class="label">Intentos:</span>
              <span class="value">{{ threat.attempts }}</span>
            </div>
            <div class="info-item">
              <span class="label">Estado:</span>
              <span class="value" :class="threat.status">{{ threat.status }}</span>
            </div>
          </div>
          <div class="threat-meta">
            <span>{{ formatDateTime(threat.detected_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Logs -->
    <div v-if="activeTab === 'logs'" class="logs-section">
      <div class="section-header">
        <h4>Logs de Seguridad</h4>
        <div class="log-filters">
          <select v-model="logFilter">
            <option value="all">Todos</option>
            <option value="error">Errores</option>
            <option value="warning">Advertencias</option>
            <option value="info">Info</option>
          </select>
          <button @click="exportLogs" class="btn-export">📥 Exportar</button>
        </div>
      </div>

      <div class="logs-container">
        <div v-for="log in filteredLogs" :key="log.id" class="log-entry" :class="log.level">
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-level" :class="log.level">{{ log.level.toUpperCase() }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const activeTab = ref('alerts')
const alertFilter = ref('all')
const logFilter = ref('all')
const isScanning = ref(false)
const scanProgress = ref(0)

// Datos de ejemplo
const alerts = ref([
  {
    id: 1,
    severity: 'critical',
    title: 'Intento de acceso no autorizado detectado',
    description: 'Se detectaron múltiples intentos de login fallidos desde IP sospechosa',
    source: 'Firewall',
    timestamp: new Date(Date.now() - 1000 * 60 * 5)
  },
  {
    id: 2,
    severity: 'high',
    title: 'Vulnerabilidad detectada en dependencia',
    description: 'Actualización de seguridad disponible para paquete npm',
    source: 'Dependency Scanner',
    timestamp: new Date(Date.now() - 1000 * 60 * 30)
  },
  {
    id: 3,
    severity: 'medium',
    title: 'Certificado SSL próximo a expirar',
    description: 'El certificado SSL expira en 15 días',
    source: 'SSL Monitor',
    timestamp: new Date(Date.now() - 1000 * 3600 * 2)
  }
])

const scans = ref([
  {
    id: 1,
    type: 'Escaneo Completo del Sistema',
    status: 'completed',
    files_scanned: 45230,
    threats_found: 0,
    duration: '15m 23s',
    timestamp: new Date(Date.now() - 1000 * 3600 * 6)
  },
  {
    id: 2,
    type: 'Escaneo Rápido',
    status: 'completed',
    files_scanned: 8920,
    threats_found: 2,
    duration: '3m 45s',
    timestamp: new Date(Date.now() - 1000 * 3600 * 24)
  }
])

const threats = ref([
  {
    id: 1,
    type: 'SQL Injection Attempt',
    description: 'Intento de inyección SQL en endpoint /api/users',
    source_ip: '185.234.219.XXX',
    attempts: 15,
    status: 'blocked',
    detected_at: new Date(Date.now() - 1000 * 3600 * 3)
  },
  {
    id: 2,
    type: 'Brute Force Attack',
    description: 'Ataque de fuerza bruta en login',
    source_ip: '192.168.1.XXX',
    attempts: 47,
    status: 'blocked',
    detected_at: new Date(Date.now() - 1000 * 3600 * 12)
  }
])

const logs = ref([
  { id: 1, level: 'error', message: 'Failed authentication attempt from 185.234.219.XXX', timestamp: new Date() },
  { id: 2, level: 'warning', message: 'SSL certificate expires in 15 days', timestamp: new Date() },
  { id: 3, level: 'info', message: 'Security scan completed successfully', timestamp: new Date() }
])

const totalThreatsBlocked = computed(() => 247)
const activeThreats = computed(() => threats.value.filter(t => t.status === 'active').length)
const threatSuccessRate = computed(() => 99.8)

const filteredAlerts = computed(() => {
  if (alertFilter.value === 'all') return alerts.value
  return alerts.value.filter(a => a.severity === alertFilter.value)
})

const filteredLogs = computed(() => {
  if (logFilter.value === 'all') return logs.value
  return logs.value.filter(l => l.level === logFilter.value)
})

function getAlertIcon(severity) {
  const icons = {
    critical: '🔴',
    high: '🟠',
    medium: '🟡',
    low: '🟢'
  }
  return icons[severity] || '⚪'
}

function getThreatIcon(type) {
  if (type.includes('SQL')) return '💉'
  if (type.includes('Brute')) return '🔨'
  if (type.includes('DDoS')) return '💥'
  return '⚔️'
}

function formatTime(date) {
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  
  if (minutes < 60) return `Hace ${minutes}m`
  if (hours < 24) return `Hace ${hours}h`
  return date.toLocaleDateString('es-ES')
}

function formatDateTime(date) {
  return date.toLocaleString('es-ES', { 
    day: '2-digit', 
    month: '2-digit', 
    year: 'numeric',
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

function resolveAlert(id) {
  const index = alerts.value.findIndex(a => a.id === id)
  if (index !== -1) {
    alerts.value.splice(index, 1)
  }
}

function viewDetails(id) {
  console.log('Ver detalles de alerta:', id)
}

function startNewScan() {
  isScanning.value = true
  scanProgress.value = 0
  
  const interval = setInterval(() => {
    scanProgress.value += 10
    if (scanProgress.value >= 100) {
      clearInterval(interval)
      setTimeout(() => {
        isScanning.value = false
        scanProgress.value = 0
      }, 500)
    }
  }, 300)
}

function viewScanReport(id) {
  console.log('Ver reporte de escaneo:', id)
}

function exportLogs() {
  console.log('Exportar logs')
}
</script>

<style scoped>
.thalos-workspace {
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

.alert-filters,
.log-filters {
  display: flex;
  gap: 10px;
  align-items: center;
}

.alert-filters button {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.alert-filters button.active {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.alerts-list,
.scans-list,
.threats-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.alert-card {
  display: flex;
  gap: 15px;
  padding: 20px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  background: white;
  transition: all 0.2s;
}

.alert-card.critical {
  border-color: #ef4444;
  background: #fef2f2;
}

.alert-card.high {
  border-color: #f97316;
  background: #fff7ed;
}

.alert-card.medium {
  border-color: #eab308;
  background: #fefce8;
}

.alert-icon {
  font-size: 32px;
}

.alert-content {
  flex: 1;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.alert-header h4 {
  font-size: 16px;
  margin: 0;
  color: #1f2937;
}

.alert-severity {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}

.alert-severity.critical {
  background: #ef4444;
  color: white;
}

.alert-severity.high {
  background: #f97316;
  color: white;
}

.alert-severity.medium {
  background: #eab308;
  color: white;
}

.alert-description {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 10px;
}

.alert-details {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #6b7280;
}

.alert-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-actions button {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
  transition: all 0.2s;
}

.btn-resolve {
  background: #10b981;
  color: white;
}

.btn-resolve:hover {
  background: #059669;
}

.btn-details {
  background: #3b82f6;
  color: white;
}

.btn-details:hover {
  background: #2563eb;
}

.btn-new-scan,
.btn-export {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.scan-progress {
  margin-bottom: 30px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  transition: width 0.3s;
}

.scan-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
}

.scan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.scan-header h4 {
  font-size: 16px;
  margin: 0;
}

.scan-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.scan-status.completed {
  background: #d1fae5;
  color: #065f46;
}

.scan-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin-bottom: 15px;
}

.stat {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.stat-value.danger {
  color: #ef4444;
}

.scan-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 15px;
}

.scan-actions,
.threat-actions {
  display: flex;
  gap: 10px;
}

.btn-view {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.threats-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.threat-stat-card {
  display: flex;
  gap: 15px;
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: white;
}

.stat-icon {
  font-size: 40px;
}

.stat-content h3 {
  font-size: 32px;
  margin: 0 0 5px;
  color: #1f2937;
}

.stat-content p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.threat-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background: white;
}

.threat-type {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
}

.threat-icon {
  font-size: 32px;
}

.threat-type h4 {
  font-size: 16px;
  margin: 0 0 5px;
  color: #1f2937;
}

.threat-description {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.threat-info {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin-bottom: 15px;
}

.info-item {
  display: flex;
  flex-direction: column;
  font-size: 13px;
}

.info-item .label {
  color: #6b7280;
  margin-bottom: 4px;
}

.info-item .value {
  font-weight: 600;
  color: #1f2937;
}

.info-item .value.blocked {
  color: #10b981;
}

.threat-meta {
  font-size: 12px;
  color: #6b7280;
}

.log-filters select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.logs-container {
  background: #0a0e1a;
  border-radius: 8px;
  padding: 20px;
  font-family: 'Courier New', monospace;
  max-height: 500px;
  overflow-y: auto;
}

.log-entry {
  display: flex;
  gap: 15px;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.log-time {
  color: #6b7280;
  min-width: 80px;
}

.log-level {
  min-width: 70px;
  font-weight: 700;
}

.log-level.error {
  color: #ef4444;
}

.log-level.warning {
  color: #eab308;
}

.log-level.info {
  color: #3b82f6;
}

.log-message {
  color: #e5e7eb;
  flex: 1;
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: #6b7280;
  font-size: 16px;
}
</style>

