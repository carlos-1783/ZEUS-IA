<template>
  <div class="holographic-dashboard">
    <!-- Fondo 3D Holográfico con Zeus -->
    <div class="hologram-background">
      <ZeusHologram3D 
        ref="hologram3D"
        :width="windowWidth"
        :height="windowHeight"
        @agent-activated="onAgentActivated"
        @command-executed="onCommandExecuted"
      />
    </div>

    <!-- HUD Overlay - Métricas que aparecen/desaparecen -->
    <div class="hud-overlay" :class="{ 'hud-visible': showHUD }">
      <!-- Toggle HUD -->
      <button 
        @click="toggleHUD" 
        class="hud-toggle"
        title="Mostrar/Ocultar métricas"
      >
        {{ showHUD ? '👁️' : '📊' }}
      </button>

      <!-- Panel de Métricas Holográficas -->
      <transition name="fade-slide">
        <div v-if="showHUD" class="metrics-panel">
          <div class="metric-card" v-for="metric in metrics" :key="metric.title">
            <div class="metric-icon">{{ metric.icon }}</div>
            <div class="metric-content">
              <div class="metric-label">{{ metric.title }}</div>
              <div class="metric-value">{{ metric.value }}</div>
              <div class="metric-trend" :class="metric.trend">
                {{ metric.trend === 'up' ? '↗' : '↘' }} {{ metric.trendValue }}
              </div>
            </div>
          </div>
        </div>
      </transition>

      <!-- Panel de Comandos Rápidos -->
      <transition name="fade-slide">
        <div v-if="showHUD" class="commands-panel">
          <div class="command-title">🎮 Comandos ZEUS</div>
          <button 
            v-for="cmd in quickCommands" 
            :key="cmd.name"
            @click="executeCommand(cmd.command)"
            class="command-btn"
          >
            {{ cmd.icon }} {{ cmd.name }}
          </button>
        </div>
      </transition>

      <!-- Panel de Actividad Reciente -->
      <transition name="fade-slide">
        <div v-if="showHUD" class="activity-panel">
          <div class="activity-title">⚡ Actividad Reciente</div>
          <div class="activity-item" v-for="activity in recentActivities.slice(0, 3)" :key="activity.id">
            <span class="activity-icon">{{ getActivityIcon(activity.type) }}</span>
            <span class="activity-text">{{ activity.title }}</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- Notificaciones Flotantes -->
    <div class="notifications-container">
      <div 
        v-for="notification in notifications" 
        :key="notification.id"
        class="holographic-notification"
        :class="notification.type"
      >
        {{ notification.message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ZeusHologram3D from '@/components/ZeusHologram3D.vue'

const router = useRouter()
const authStore = useAuthStore()

// Estado
const hologram3D = ref(null)
const showHUD = ref(true)
const windowWidth = ref(window.innerWidth)
const windowHeight = ref(window.innerHeight)
const notifications = ref([])

// Métricas (datos simulados)
const metrics = ref([
  { title: 'Ventas Hoy', value: '1,245', icon: '💰', trend: 'up', trendValue: '12%' },
  { title: 'Ingresos', value: '$12,548', icon: '💵', trend: 'up', trendValue: '3%' },
  { title: 'Clientes', value: '24', icon: '👥', trend: 'up', trendValue: '8%' },
  { title: 'Órdenes', value: '156', icon: '📦', trend: 'up', trendValue: '5%' }
])

// Comandos rápidos
const quickCommands = ref([
  { name: 'ZEUS', icon: '⚡', command: 'ZEUS.ACTIVAR' },
  { name: 'PERSEO', icon: '🎯', command: 'PERSEO.FUNNEL' },
  { name: 'THALOS', icon: '🛡️', command: 'THALOS.SHIELD' },
  { name: 'ANÁLISIS', icon: '📊', command: 'ANALISIS.PROCESAR' }
])

// Actividades recientes
const recentActivities = ref([
  { id: 1, type: 'order', title: 'Nueva orden #1001' },
  { id: 2, type: 'customer', title: 'Nuevo cliente registrado' },
  { id: 3, type: 'payment', title: 'Pago procesado $125.75' }
])

// Toggle HUD
const toggleHUD = () => {
  showHUD.value = !showHUD.value
}

// Ejecutar comando
const executeCommand = (command) => {
  console.log('⚡ Ejecutando comando:', command)
  showNotification('info', `Comando ${command} ejecutado`)
}

// Handlers de eventos del holograma
const onAgentActivated = (agent) => {
  console.log('⚡ Agente activado:', agent.name)
  showNotification('success', `${agent.name} está operativo`)
}

const onCommandExecuted = (result) => {
  console.log('✅ Comando ejecutado:', result)
  showNotification('success', result.message || 'Comando exitoso')
}

// Mostrar notificación
const showNotification = (type, message) => {
  const notification = {
    id: Date.now(),
    type,
    message
  }
  
  notifications.value.push(notification)
  
  setTimeout(() => {
    notifications.value = notifications.value.filter(n => n.id !== notification.id)
  }, 3000)
}

// Obtener icono de actividad
const getActivityIcon = (type) => {
  const icons = {
    order: '🛒',
    customer: '👤',
    payment: '💳',
    error: '❌'
  }
  return icons[type] || 'ℹ️'
}

// Resize handler
const handleResize = () => {
  windowWidth.value = window.innerWidth
  windowHeight.value = window.innerHeight
}

// Lifecycle
onMounted(() => {
  window.addEventListener('resize', handleResize)
  showNotification('success', '⚡ Dashboard holográfico activado')
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.holographic-dashboard {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #000;
  overflow: hidden;
}

.hologram-background {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.hud-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
}

.hud-overlay > * {
  pointer-events: auto;
}

/* Toggle HUD Button */
.hud-toggle {
  position: fixed;
  top: 20px;
  right: 20px;
  width: 60px;
  height: 60px;
  background: rgba(10, 35, 66, 0.9);
  border: 2px solid rgba(59, 130, 246, 0.5);
  border-radius: 50%;
  color: #ffd700;
  font-size: 1.8rem;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
}

.hud-toggle:hover {
  background: rgba(59, 130, 246, 0.9);
  transform: scale(1.1) rotate(180deg);
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.6);
}

/* Metrics Panel - Estilo Jarvis */
.metrics-panel {
  position: fixed;
  top: 100px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  max-width: 300px;
}

.metric-card {
  background: rgba(10, 35, 66, 0.85);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 15px;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.2);
  animation: float 3s ease-in-out infinite;
}

.metric-card:nth-child(2) { animation-delay: 0.5s; }
.metric-card:nth-child(3) { animation-delay: 1s; }
.metric-card:nth-child(4) { animation-delay: 1.5s; }

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.metric-icon {
  font-size: 2rem;
  filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.5));
}

.metric-content {
  flex: 1;
  color: #fff;
}

.metric-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.metric-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #ffd700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
}

.metric-trend {
  font-size: 0.85rem;
  margin-top: 4px;
}

.metric-trend.up {
  color: #10b981;
}

.metric-trend.down {
  color: #ef4444;
}

/* Commands Panel */
.commands-panel {
  position: fixed;
  bottom: 20px;
  left: 20px;
  background: rgba(10, 35, 66, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 20px;
  max-width: 250px;
}

.command-title {
  color: #ffd700;
  font-weight: bold;
  margin-bottom: 15px;
  text-align: center;
  font-size: 1.1rem;
}

.command-btn {
  width: 100%;
  padding: 12px;
  margin-bottom: 10px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 0.95rem;
}

.command-btn:hover {
  background: rgba(59, 130, 246, 0.4);
  transform: translateX(5px);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
}

/* Activity Panel */
.activity-panel {
  position: fixed;
  top: 100px;
  left: 20px;
  background: rgba(10, 35, 66, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 20px;
  max-width: 300px;
}

.activity-title {
  color: #ffd700;
  font-weight: bold;
  margin-bottom: 15px;
  font-size: 1.1rem;
}

.activity-item {
  padding: 10px;
  margin-bottom: 8px;
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid rgba(59, 130, 246, 0.6);
  border-radius: 4px;
  color: #fff;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 10px;
}

.activity-icon {
  font-size: 1.2rem;
}

/* Notificaciones Flotantes */
.notifications-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.holographic-notification {
  background: rgba(10, 35, 66, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 8px;
  padding: 15px 25px;
  color: #fff;
  box-shadow: 0 0 25px rgba(59, 130, 246, 0.4);
  animation: notification-appear 0.5s ease-out, notification-pulse 2s ease-in-out infinite;
}

.holographic-notification.success {
  border-color: rgba(16, 185, 129, 0.5);
  box-shadow: 0 0 25px rgba(16, 185, 129, 0.4);
}

.holographic-notification.error {
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 25px rgba(239, 68, 68, 0.4);
}

@keyframes notification-appear {
  from { 
    opacity: 0;
    transform: translateY(-20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes notification-pulse {
  0%, 100% { box-shadow: 0 0 25px rgba(59, 130, 246, 0.4); }
  50% { box-shadow: 0 0 35px rgba(59, 130, 246, 0.6); }
}

/* Transiciones */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Responsive */
@media (max-width: 768px) {
  .metrics-panel,
  .commands-panel,
  .activity-panel {
    max-width: 90vw;
  }
  
  .metrics-panel {
    right: 10px;
  }
  
  .commands-panel,
  .activity-panel {
    left: 10px;
  }
}
</style>

