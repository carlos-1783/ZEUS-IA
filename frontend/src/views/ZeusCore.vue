<template>
  <div class="zeus-core-container">
    <!-- Header holográfico -->
    <header class="zeus-header">
      <div class="zeus-logo">
        <div class="logo-icon">⚡</div>
        <h1>NÚCLEO ZEUS-IA</h1>
        <div class="status-indicator" :class="systemStatus">
          {{ systemStatus.toUpperCase() }}
        </div>
      </div>
      
      <div class="user-info">
        <span class="user-name">{{ userEmail }}</span>
        <button @click="logout" class="logout-btn">SALIR</button>
      </div>
    </header>
    
    <!-- Panel principal holográfico -->
    <main class="zeus-main">
      <!-- Componente 3D de hologramas -->
      <ZeusHologram3D 
        ref="hologram3D"
        :width="hologramWidth"
        :height="hologramHeight"
        @agent-activated="onAgentActivated"
        @command-executed="onCommandExecuted"
      />
      
      <!-- Panel de información lateral -->
      <aside class="info-panel">
        <div class="panel-section">
          <h3>ESTADO DEL SISTEMA</h3>
          <div class="system-metrics">
            <div class="metric">
              <span class="metric-label">Agentes Activos:</span>
              <span class="metric-value">{{ activeAgents }}/6</span>
            </div>
            <div class="metric">
              <span class="metric-label">Comandos Ejecutados:</span>
              <span class="metric-value">{{ commandsExecuted }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Tiempo de Actividad:</span>
              <span class="metric-value">{{ uptime }}</span>
            </div>
          </div>
        </div>
        
        <div class="panel-section">
          <h3>COMANDOS DISPONIBLES</h3>
          <div class="command-list">
            <div 
              v-for="command in availableCommands" 
              :key="command"
              class="command-item"
              @click="executeQuickCommand(command)"
            >
              {{ command }}
            </div>
          </div>
        </div>
        
        <div class="panel-section">
          <h3>LOGS DEL SISTEMA</h3>
          <div class="logs-container">
            <div 
              v-for="log in systemLogs.slice(-5)" 
              :key="log.id"
              class="log-entry"
              :class="log.type"
            >
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </aside>
    </main>
    
    <!-- Notificaciones holográficas -->
    <div class="notifications-container">
      <div 
        v-for="notification in notifications" 
        :key="notification.id"
        class="notification"
        :class="notification.type"
        @click="removeNotification(notification.id)"
      >
        <div class="notification-icon">
          {{ getNotificationIcon(notification.type) }}
        </div>
        <div class="notification-content">
          <h4>{{ notification.title }}</h4>
          <p>{{ notification.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ZeusHologram3D from '@/components/ZeusHologram3D.vue'

// Router y store
const router = useRouter()
const authStore = useAuthStore()

// Refs
const hologram3D = ref(null)
const systemStatus = ref('inactive')
const activeAgents = ref(0)
const commandsExecuted = ref(0)
const systemLogs = ref([])
const notifications = ref([])
const startTime = ref(new Date())

// Performance: Guardar IDs de intervalos para cleanup
let statusUpdateInterval = null
let logsUpdateInterval = null

// Computed
const userEmail = computed(() => authStore.user?.email || 'Usuario')
const hologramWidth = computed(() => window.innerWidth - 300)
const hologramHeight = computed(() => window.innerHeight - 100)
const uptime = computed(() => {
  const now = new Date()
  const diff = now - startTime.value
  const minutes = Math.floor(diff / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

// Comandos disponibles con especializaciones reales
const availableCommands = ref([
  'ZEUS.ACTIVAR',
  'ZEUS.ANALIZAR',
  'PERSEO.FUNNEL',
  'PERSEO.SEO',
  'PERSEO.COPY',
  'THALOS.SHIELD',
  'THALOS.SCAN',
  'JUSTICIA.CONTRATO',
  'JUSTICIA.RGPD',
  'RAFAEL.IVA',
  'RAFAEL.IRPF',
  'RAFAEL.IS',
  'ANALISIS.PROCESAR',
  'IA.PROCESAR'
])

// ========================================
// LIFECYCLE
// ========================================

onMounted(async () => {
  console.log('🚀 Iniciando Núcleo ZEUS-IA...')
  
  // Verificar autenticación
  if (!authStore.isAuthenticated) {
    router.push('/auth/login')
    return
  }
  
  // Inicializar sistema
  await initializeZeusSystem()
  
  // Configurar actualizaciones periódicas
  setupPeriodicUpdates()
  
  addSystemLog('info', 'Núcleo ZEUS-IA inicializado correctamente')
  showNotification('success', 'Sistema Activado', 'Núcleo ZEUS-IA operativo')
})

onUnmounted(() => {
  console.log('🛑 Cerrando Núcleo ZEUS-IA...')
  
  // Performance: Limpiar intervalos
  if (statusUpdateInterval) {
    clearInterval(statusUpdateInterval)
    statusUpdateInterval = null
  }
  if (logsUpdateInterval) {
    clearInterval(logsUpdateInterval)
    logsUpdateInterval = null
  }
})

// ========================================
// INICIALIZACIÓN
// ========================================

async function initializeZeusSystem() {
  try {
    // Activar sistema ZEUS
    const response = await fetch('/api/v1/zeus/activate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const result = await response.json()
      systemStatus.value = 'active'
      activeAgents.value = result.data?.agents ? Object.keys(result.data.agents).length : 0
      
      addSystemLog('success', 'Sistema ZEUS activado correctamente')
      showNotification('success', 'ZEUS Activado', 'Todos los agentes están operativos')
    } else {
      throw new Error('Error activando sistema ZEUS')
    }
    
  } catch (error) {
    console.error('Error inicializando ZEUS:', error)
    addSystemLog('error', `Error inicializando sistema: ${error.message}`)
    showNotification('error', 'Error de Inicialización', error.message)
  }
}

function setupPeriodicUpdates() {
  // Performance: Actualizar estado cada 30 segundos (optimizado sin requestAnimationFrame)
  statusUpdateInterval = setInterval(async () => {
    try {
      await updateSystemStatus()
    } catch (error) {
      console.error('Error actualizando estado:', error)
    }
  }, 30000)
  
  // Performance: Actualizar logs cada 10 segundos (optimizado sin requestAnimationFrame)
  logsUpdateInterval = setInterval(() => {
    try {
      updateSystemLogs()
    } catch (error) {
      console.error('Error actualizando logs:', error)
    }
  }, 10000)
}

// ========================================
// FUNCIONES DEL SISTEMA
// ========================================

// Performance: Variable para evitar múltiples requests simultáneos
let isUpdatingStatus = false

async function updateSystemStatus() {
  // Performance: Skip si ya hay un update en progreso
  if (isUpdatingStatus) {
    console.log('⏩ Skipping status update - already in progress')
    return
  }
  
  isUpdatingStatus = true
  
  try {
    // Performance: Timeout reducido de 5s a 3s
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 3000)
    
    const response = await fetch('/api/v1/zeus/status', {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      signal: controller.signal
    })
    
    clearTimeout(timeoutId)
    
    if (response.ok) {
      const result = await response.json()
      const status = result.data
      
      systemStatus.value = status.system_status
      activeAgents.value = status.active_agents || 0
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.warn('⏱️ Timeout actualizando estado del sistema')
    } else {
      console.error('❌ Error actualizando estado:', error)
    }
  } finally {
    isUpdatingStatus = false
  }
}

function updateSystemLogs() {
  // Performance: Reducir probabilidad de 30% a 10% para menos operaciones
  if (Math.random() > 0.9) {
    // Performance: Usar array estático pre-definido
    const logTypes = ['info', 'success', 'warning', 'error']
    const messages = [
      'Sistema funcionando normalmente',
      'Agente THALOS ejecutando verificación de seguridad',
      'Análisis de datos completado',
      'Usuario interactuando con el sistema',
      'Comando ejecutado exitosamente'
    ]
    
    const type = logTypes[Math.floor(Math.random() * logTypes.length)]
    const message = messages[Math.floor(Math.random() * messages.length)]
    addSystemLog(type, message)
  }
}

function onAgentActivated(agent) {
  console.log(`Agente activado: ${agent.name}`)
  addSystemLog('success', `Agente ${agent.name} activado`)
  showNotification('info', 'Agente Activado', `${agent.name} está operativo`)
}

function onCommandExecuted(result) {
  commandsExecuted.value++
  addSystemLog('info', `Comando ejecutado: ${result.command}`)
  
  if (result.status === 'success') {
    showNotification('success', 'Comando Exitoso', result.message)
  } else {
    showNotification('error', 'Error en Comando', result.message)
  }
}

async function executeQuickCommand(command) {
  try {
    // Timeout de 10 segundos para comandos
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 10000)
    
    const response = await fetch('/api/v1/zeus/execute', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        command: command,
        data: {}
      }),
      signal: controller.signal
    })
    
    clearTimeout(timeoutId)
    
    if (response.ok) {
      const result = await response.json()
      onCommandExecuted(result)
    } else {
      throw new Error('Error ejecutando comando')
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.warn(`Timeout ejecutando comando: ${command}`)
      addSystemLog('warning', `Timeout ejecutando ${command}`)
      showNotification('warning', 'Timeout de Comando', `El comando ${command} tardó demasiado`)
    } else {
      console.error('Error ejecutando comando rápido:', error)
      addSystemLog('error', `Error ejecutando ${command}: ${error.message}`)
      showNotification('error', 'Error de Comando', error.message)
    }
  }
}

// ========================================
// UTILIDADES
// ========================================

function addSystemLog(type, message) {
  const log = {
    id: Date.now(),
    type,
    message,
    timestamp: new Date().toISOString()
  }
  
  systemLogs.value.push(log)
  
  // Performance: Mantener solo los últimos 50 logs (optimizado con shift)
  if (systemLogs.value.length > 50) {
    systemLogs.value.shift()  // ✅ Más eficiente que slice
  }
}

function showNotification(type, title, message) {
  const notification = {
    id: Date.now(),
    type,
    title,
    message,
    timestamp: new Date().toISOString()
  }
  
  notifications.value.push(notification)
  
  // Auto-remover después de 5 segundos
  setTimeout(() => {
    removeNotification(notification.id)
  }, 5000)
}

function removeNotification(id) {
  const index = notifications.value.findIndex(n => n.id === id)
  if (index > -1) {
    notifications.value.splice(index, 1)
  }
}

function getNotificationIcon(type) {
  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  }
  return icons[type] || 'ℹ️'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function logout() {
  authStore.logout()
  router.push('/auth/login')
}
</script>

<style scoped>
.zeus-core-container {
  width: 100%;
  height: 100vh;
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
  color: #ffffff;
  font-family: 'Courier New', monospace;
  overflow: hidden;
}

.zeus-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.8);
  border-bottom: 1px solid rgba(0, 255, 255, 0.3);
  backdrop-filter: blur(10px);
}

.zeus-logo {
  display: flex;
  align-items: center;
  gap: 15px;
}

.logo-icon {
  font-size: 32px;
  color: #ff6b00;
  text-shadow: 0 0 20px currentColor;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.zeus-logo h1 {
  margin: 0;
  color: #00ffff;
  text-shadow: 0 0 10px currentColor;
  font-size: 24px;
}

.status-indicator {
  padding: 5px 10px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: bold;
  text-transform: uppercase;
}

.status-indicator.active {
  background: rgba(0, 255, 0, 0.3);
  color: #00ff00;
  border: 1px solid #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
}

.status-indicator.inactive {
  background: rgba(255, 0, 0, 0.3);
  color: #ff0000;
  border: 1px solid #ff0000;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-name {
  color: #00ffff;
  font-weight: bold;
}

.logout-btn {
  background: linear-gradient(45deg, #ff0066, #ff3366);
  border: none;
  border-radius: 5px;
  padding: 8px 16px;
  color: white;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: linear-gradient(45deg, #ff3366, #ff6699);
  box-shadow: 0 0 15px rgba(255, 0, 102, 0.5);
}

.zeus-main {
  display: flex;
  height: calc(100vh - 80px);
}

.info-panel {
  width: 300px;
  background: rgba(0, 0, 0, 0.8);
  border-left: 1px solid rgba(0, 255, 255, 0.3);
  padding: 20px;
  overflow-y: auto;
  backdrop-filter: blur(10px);
}

.panel-section {
  margin-bottom: 30px;
}

.panel-section h3 {
  color: #00ffff;
  margin: 0 0 15px 0;
  font-size: 14px;
  text-transform: uppercase;
  text-shadow: 0 0 5px currentColor;
  border-bottom: 1px solid rgba(0, 255, 255, 0.3);
  padding-bottom: 5px;
}

.system-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(0, 255, 255, 0.1);
  border-radius: 5px;
  border: 1px solid rgba(0, 255, 255, 0.2);
}

.metric-label {
  color: #cccccc;
  font-size: 12px;
}

.metric-value {
  color: #00ffff;
  font-weight: bold;
  font-size: 12px;
}

.command-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.command-item {
  padding: 8px 12px;
  background: rgba(0, 255, 255, 0.1);
  border: 1px solid rgba(0, 255, 255, 0.2);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 12px;
  color: #00ffff;
}

.command-item:hover {
  background: rgba(0, 255, 255, 0.2);
  border-color: rgba(0, 255, 255, 0.4);
  transform: translateX(5px);
}

.logs-container {
  max-height: 200px;
  overflow-y: auto;
}

.log-entry {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  margin-bottom: 5px;
  border-radius: 3px;
  font-size: 11px;
}

.log-entry.success {
  background: rgba(0, 255, 0, 0.1);
  border-left: 3px solid #00ff00;
}

.log-entry.error {
  background: rgba(255, 0, 0, 0.1);
  border-left: 3px solid #ff0000;
}

.log-entry.warning {
  background: rgba(255, 255, 0, 0.1);
  border-left: 3px solid #ffff00;
}

.log-entry.info {
  background: rgba(0, 255, 255, 0.1);
  border-left: 3px solid #00ffff;
}

.log-time {
  color: #888888;
  font-size: 10px;
}

.log-message {
  color: #ffffff;
}

.notifications-container {
  position: fixed;
  top: 100px;
  right: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background: rgba(0, 0, 0, 0.9);
  border: 1px solid rgba(0, 255, 255, 0.3);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  min-width: 300px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.notification:hover {
  background: rgba(0, 0, 0, 0.95);
  border-color: rgba(0, 255, 255, 0.6);
}

.notification.success {
  border-color: rgba(0, 255, 0, 0.3);
}

.notification.error {
  border-color: rgba(255, 0, 0, 0.3);
}

.notification.warning {
  border-color: rgba(255, 255, 0, 0.3);
}

.notification-icon {
  font-size: 20px;
}

.notification-content h4 {
  margin: 0 0 5px 0;
  color: #00ffff;
  font-size: 14px;
}

.notification-content p {
  margin: 0;
  color: #cccccc;
  font-size: 12px;
}
</style>
