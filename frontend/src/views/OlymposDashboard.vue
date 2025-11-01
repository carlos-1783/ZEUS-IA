<template>
  <div class="olympos-dashboard">
    <!-- Fondo del Olimpo con columnas y cielo divino -->
    <div class="olympos-background">
      <!-- Luz celestial circular superior -->
      <div class="divine-light">
        <div class="light-ring ring-1"></div>
        <div class="light-ring ring-2"></div>
        <div class="light-ring ring-3"></div>
        <div class="light-core"></div>
      </div>

      <!-- Columnas del templo -->
      <div class="columns-layer">
        <div class="column column-left-1"></div>
        <div class="column column-left-2"></div>
        <div class="column column-right-1"></div>
        <div class="column column-right-2"></div>
      </div>

      <!-- Nubes base -->
      <div class="clouds-layer">
        <div class="cloud cloud-1"></div>
        <div class="cloud cloud-2"></div>
        <div class="cloud cloud-3"></div>
      </div>
    </div>

    <!-- Zeus Central - Figura Divina -->
    <div class="zeus-central">
      <div class="zeus-figure">
        <!-- Aura dorada de Zeus -->
        <div class="zeus-aura"></div>
        
        <!-- Imagen de Zeus -->
        <img 
          src="/images/zues-3d-main.png" 
          alt="Zeus - Dios del Olimpo"
          class="zeus-statue"
        />
        
        <!-- Ojos brillantes -->
        <div class="zeus-eyes">
          <div class="eye eye-left"></div>
          <div class="eye eye-right"></div>
        </div>
        
        <!-- Rayos emanando de las manos -->
        <div class="zeus-lightning left-hand">
          <div class="lightning-bolt bolt-1"></div>
          <div class="lightning-bolt bolt-2"></div>
          <div class="lightning-bolt bolt-3"></div>
        </div>
        
        <div class="zeus-lightning right-hand">
          <div class="lightning-bolt bolt-1"></div>
          <div class="lightning-bolt bolt-2"></div>
        </div>
      </div>
    </div>

    <!-- Panel de Control - Agentes del Olimpo -->
    <div class="agents-panel" :class="{ 'panel-visible': showAgents }">
      <button @click="toggleAgentsPanel" class="panel-toggle">
        {{ showAgents ? '⚡ OCULTAR AGENTES' : '⚡ INVOCAR AGENTES' }}
      </button>

      <transition name="agents-fade">
        <div v-if="showAgents" class="agents-grid">
          <div 
            v-for="agent in olymposAgents" 
            :key="agent.id"
            @click="activateAgent(agent)"
            class="agent-card"
            :class="{ 'agent-active': agent.active }"
          >
            <div class="agent-hologram">
              <div class="hologram-effect"></div>
              <img 
                v-if="agent.image" 
                :src="agent.image" 
                :alt="agent.name"
                class="agent-avatar-3d"
              />
              <div v-else class="agent-icon">{{ agent.icon }}</div>
            </div>
            <div class="agent-name">{{ agent.name }}</div>
            <div class="agent-status" :class="agent.active ? 'status-active' : 'status-idle'">
              {{ agent.active ? 'ACTIVO' : 'LISTO' }}
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- Métricas Flotantes -->
    <div class="metrics-olympos" v-if="showMetrics">
      <div 
        v-for="(metric, index) in metrics" 
        :key="metric.id"
        class="metric-hologram"
        :style="{ '--index': index }"
      >
        <div class="metric-hologram-border"></div>
        <div class="metric-content">
          <div class="metric-icon">{{ metric.icon }}</div>
          <div class="metric-value">{{ metric.value }}</div>
          <div class="metric-label">{{ metric.label }}</div>
        </div>
      </div>
    </div>

    <!-- Toggle Métricas -->
    <button @click="showMetrics = !showMetrics" class="metrics-toggle">
      {{ showMetrics ? '📊 OCULTAR' : '📊 MÉTRICAS' }}
    </button>

    <!-- Notificaciones Divinas -->
    <div class="divine-notifications">
      <transition-group name="notification-slide">
        <div 
          v-for="notification in notifications" 
          :key="notification.id"
          class="divine-notification"
          :class="notification.type"
        >
          <div class="notification-glow"></div>
          {{ notification.message }}
        </div>
      </transition-group>
    </div>

    <!-- Indicador de Versión (debug - removible después) -->
    <div class="version-indicator">
      🏛️ OLIMPO v1.0
    </div>

    <!-- Comandos de Voz Zeus (simulado) -->
    <div class="zeus-voice-commands" v-if="activeAgent">
      <div class="voice-wave"></div>
      <div class="voice-text">
        {{ activeAgent.name }} está operativo. ¿Qué deseas que haga?
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// Estado
const showAgents = ref(true)  // Mostrar agentes por defecto
const showMetrics = ref(true)
const activeAgent = ref(null)
const notifications = ref([])

// Agentes del Olimpo - SIEMPRE VISIBLES CON IMÁGENES 3D
const olymposAgents = ref([
  { 
    id: 1, 
    name: 'ZEUS CORE', 
    icon: '⚡', 
    image: '/images/zues-3d-main.png',
    active: false, 
    description: 'Orquestador Supremo', 
    status: 'online' 
  },
  { 
    id: 2, 
    name: 'PERSEO', 
    icon: '🎯', 
    image: '/images/avatars/perseo-avatar.jpg',
    active: false, 
    description: 'Estratega de Crecimiento', 
    status: 'online' 
  },
  { 
    id: 3, 
    name: 'RAFAEL', 
    icon: '📊', 
    image: '/images/avatars/perseo-avatar.jpg',
    active: false, 
    description: 'Guardián Fiscal', 
    status: 'online' 
  },
  { 
    id: 4, 
    name: 'THALOS', 
    icon: '🛡️', 
    image: '/images/avatars/perseo-avatar.jpg',
    active: false, 
    description: 'Defensor Cibernético', 
    status: 'online' 
  },
  { 
    id: 5, 
    name: 'JUSTICIA', 
    icon: '⚖️', 
    image: '/images/avatars/perseo-avatar.jpg',
    active: false, 
    description: 'Asesora Legal y GDPR', 
    status: 'online' 
  }
])

// Actualizar estado desde el backend (sin bloquear la UI)
const updateAgentsFromBackend = async () => {
  try {
    const response = await fetch('/api/v1/agents/status')
    if (response.ok) {
      const data = await response.json()
      console.log('✅ Backend respondió:', data)
      
      // Actualizar solo el estado si el backend responde
      Object.entries(data.agents || {}).forEach(([name, info]) => {
        const agent = olymposAgents.value.find(a => a.name === name)
        if (agent) {
          agent.status = info.status || 'online'
          agent.description = info.role || agent.description
        }
      })
    }
  } catch (error) {
    console.log('⚠️ Backend no disponible, usando datos por defecto')
  }
}

// Cargar estado desde backend en segundo plano
onMounted(() => {
  updateAgentsFromBackend()
  // Actualizar cada 30 segundos
  setInterval(updateAgentsFromBackend, 30000)
})

// Métricas
const metrics = ref([
  { id: 1, icon: '💰', value: '1,245', label: 'Ventas Hoy' },
  { id: 2, icon: '💵', value: '$12,548', label: 'Ingresos' },
  { id: 3, icon: '👥', value: '24', label: 'Clientes' },
  { id: 4, icon: '📦', value: '156', label: 'Órdenes' }
])

// Toggle panel de agentes
const toggleAgentsPanel = () => {
  showAgents.value = !showAgents.value
  if (showAgents.value) {
    showNotification('info', '⚡ Panel de agentes invocado')
  }
}

// Activar agente
const activateAgent = (agent) => {
  // Desactivar todos
  olymposAgents.value.forEach(a => a.active = false)
  
  // Activar el seleccionado
  agent.active = true
  activeAgent.value = agent
  
  showNotification('success', `${agent.icon} ${agent.name} activado: ${agent.description}`)
  
  // Auto-desactivar después de 5 segundos
  setTimeout(() => {
    agent.active = false
    if (activeAgent.value?.id === agent.id) {
      activeAgent.value = null
    }
  }, 5000)
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
  }, 4000)
}

// Lifecycle
onMounted(() => {
  showNotification('success', '⚡ Bienvenido al Olimpo')
})
</script>

<style scoped>
.olympos-dashboard {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: linear-gradient(180deg, #0a1628 0%, #1a2f4a 50%, #2a4560 100%);
  overflow: hidden;
  perspective: 1000px;
}

/* ========== FONDO DEL OLIMPO ========== */
.olympos-background {
  position: absolute;
  inset: 0;
  z-index: 1;
}

/* Luz Divina Celestial (círculo superior) */
.divine-light {
  position: absolute;
  top: -150px;
  left: 50%;
  transform: translateX(-50%);
  width: 500px;
  height: 500px;
  z-index: 2;
}

.light-core {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 150px;
  height: 150px;
  background: radial-gradient(circle, #fff 0%, #ffd700 50%, transparent 70%);
  border-radius: 50%;
  animation: divine-pulse 3s ease-in-out infinite;
  filter: blur(20px);
}

.light-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border: 2px solid rgba(255, 215, 0, 0.3);
  border-radius: 50%;
  animation: ring-expand 4s ease-in-out infinite;
}

.ring-1 { width: 200px; height: 200px; }
.ring-2 { width: 300px; height: 300px; animation-delay: 0.5s; }
.ring-3 { width: 400px; height: 400px; animation-delay: 1s; }

@keyframes divine-pulse {
  0%, 100% { opacity: 0.8; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1.2); }
}

@keyframes ring-expand {
  0%, 100% { opacity: 0.3; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.6; transform: translate(-50%, -50%) scale(1.1); }
}

/* Columnas del Templo */
.columns-layer {
  position: absolute;
  inset: 0;
  z-index: 3;
}

.column {
  position: absolute;
  bottom: 0;
  width: 80px;
  height: 100%;
  background: linear-gradient(
    180deg,
    rgba(255, 215, 0, 0.1) 0%,
    rgba(255, 255, 255, 0.2) 20%,
    rgba(255, 255, 255, 0.3) 50%,
    rgba(255, 215, 0, 0.2) 100%
  );
  border-left: 2px solid rgba(255, 215, 0, 0.3);
  border-right: 2px solid rgba(255, 215, 0, 0.3);
  opacity: 0.6;
  animation: column-glow 5s ease-in-out infinite;
}

.column::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  height: 40px;
  background: rgba(255, 215, 0, 0.4);
  clip-path: polygon(0 100%, 15% 0, 85% 0, 100% 100%);
}

.column-left-1 { left: 5%; animation-delay: 0s; }
.column-left-2 { left: 20%; animation-delay: 1s; }
.column-right-1 { right: 20%; animation-delay: 2s; }
.column-right-2 { right: 5%; animation-delay: 3s; }

@keyframes column-glow {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.7; }
}

/* Nubes Base */
.clouds-layer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 200px;
  z-index: 4;
}

.cloud {
  position: absolute;
  bottom: 0;
  height: 150px;
  background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.3) 0%, transparent 70%);
  border-radius: 50%;
  animation: cloud-float 10s ease-in-out infinite;
  filter: blur(30px);
}

.cloud-1 { left: 10%; width: 300px; animation-delay: 0s; }
.cloud-2 { left: 40%; width: 400px; animation-delay: 2s; }
.cloud-3 { left: 70%; width: 350px; animation-delay: 4s; }

@keyframes cloud-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

/* ========== ZEUS CENTRAL ========== */
.zeus-central {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}

.zeus-figure {
  position: relative;
  width: 400px;
  height: 600px;
}

.zeus-aura {
  position: absolute;
  inset: -50px;
  background: radial-gradient(circle, rgba(255, 215, 0, 0.4) 0%, transparent 70%);
  border-radius: 50%;
  animation: aura-pulse 3s ease-in-out infinite;
  filter: blur(40px);
}

@keyframes aura-pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.2); }
}

.zeus-statue {
  position: relative;
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: drop-shadow(0 0 40px rgba(255, 215, 0, 0.6));
  animation: zeus-breathe 4s ease-in-out infinite;
}

@keyframes zeus-breathe {
  0%, 100% { transform: scale(1) translateY(0); }
  50% { transform: scale(1.05) translateY(-10px); }
}

/* Ojos brillantes de Zeus */
.zeus-eyes {
  position: absolute;
  top: 25%;
  left: 50%;
  transform: translateX(-50%);
  width: 100px;
  z-index: 20;
}

.eye {
  position: absolute;
  width: 15px;
  height: 15px;
  background: radial-gradient(circle, #00d4ff 0%, #0080ff 50%, transparent 70%);
  border-radius: 50%;
  animation: eye-glow 2s ease-in-out infinite;
  filter: blur(3px);
}

.eye-left { left: 20px; }
.eye-right { right: 20px; }

@keyframes eye-glow {
  0%, 100% { opacity: 0.8; box-shadow: 0 0 20px #00d4ff; }
  50% { opacity: 1; box-shadow: 0 0 40px #00d4ff, 0 0 60px #0080ff; }
}

/* Rayos de Zeus */
.zeus-lightning {
  position: absolute;
  width: 150px;
  height: 200px;
}

.left-hand {
  left: -80px;
  top: 50%;
}

.right-hand {
  right: -80px;
  top: 50%;
}

.lightning-bolt {
  position: absolute;
  width: 4px;
  height: 100px;
  background: linear-gradient(180deg, #00d4ff 0%, #0080ff 50%, transparent 100%);
  box-shadow: 0 0 20px #00d4ff;
  animation: lightning-strike 1.5s ease-in-out infinite;
  transform-origin: top center;
}

.bolt-1 { left: 20px; animation-delay: 0s; }
.bolt-2 { left: 40px; animation-delay: 0.3s; }
.bolt-3 { left: 60px; animation-delay: 0.6s; }

@keyframes lightning-strike {
  0%, 100% { opacity: 0; transform: scaleY(0); }
  10%, 30% { opacity: 1; transform: scaleY(1); }
  35% { opacity: 0; transform: scaleY(0); }
}

/* ========== PANEL DE AGENTES ========== */
.agents-panel {
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
}

.panel-toggle {
  display: block;
  margin: 0 auto 20px;
  padding: 15px 40px;
  background: linear-gradient(135deg, rgba(10, 35, 66, 0.9), rgba(59, 130, 246, 0.6));
  border: 2px solid rgba(255, 215, 0, 0.5);
  border-radius: 50px;
  color: #ffd700;
  font-weight: bold;
  font-size: 1.1rem;
  cursor: pointer;
  backdrop-filter: blur(10px);
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
  transition: all 0.3s ease;
}

.panel-toggle:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.9), rgba(10, 35, 66, 0.9));
  transform: scale(1.05);
  box-shadow: 0 0 50px rgba(255, 215, 0, 0.6);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 20px;
  padding: 20px;
  background: rgba(10, 35, 66, 0.8);
  backdrop-filter: blur(15px);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 20px;
  box-shadow: 0 0 40px rgba(59, 130, 246, 0.3);
}

.agent-card {
  position: relative;
  padding: 20px;
  background: rgba(10, 35, 66, 0.6);
  border: 2px solid rgba(59, 130, 246, 0.4);
  border-radius: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
}

.agent-card:hover {
  border-color: rgba(255, 215, 0, 0.6);
  transform: translateY(-10px);
  box-shadow: 0 10px 30px rgba(59, 130, 246, 0.5);
}

.agent-card.agent-active {
  border-color: #ffd700;
  background: rgba(59, 130, 246, 0.4);
  box-shadow: 0 0 40px rgba(255, 215, 0, 0.6);
  animation: agent-pulse 1s ease-in-out infinite;
}

@keyframes agent-pulse {
  0%, 100% { transform: translateY(-10px) scale(1); }
  50% { transform: translateY(-10px) scale(1.05); }
}

.agent-hologram {
  position: relative;
  width: 80px;
  height: 80px;
  margin: 0 auto 10px;
}

.hologram-effect {
  position: absolute;
  inset: -10px;
  background: linear-gradient(180deg, transparent, rgba(59, 130, 246, 0.2), transparent);
  border-radius: 50%;
  animation: hologram-scan 2s linear infinite;
}

@keyframes hologram-scan {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}

.agent-icon {
  font-size: 3rem;
  filter: drop-shadow(0 0 10px rgba(59, 130, 246, 0.8));
}

/* Avatar 3D de agente con efectos holográficos */
.agent-avatar-3d {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid rgba(59, 130, 246, 0.6);
  box-shadow: 
    0 0 20px rgba(59, 130, 246, 0.8),
    0 0 40px rgba(59, 130, 246, 0.4),
    inset 0 0 20px rgba(59, 130, 246, 0.2);
  animation: avatar-pulse 2s ease-in-out infinite;
  transition: all 0.3s ease;
  filter: brightness(1.1) saturate(1.2);
}

.agent-card:hover .agent-avatar-3d {
  transform: scale(1.15) rotateY(15deg);
  box-shadow: 
    0 0 30px rgba(59, 130, 246, 1),
    0 0 60px rgba(59, 130, 246, 0.6),
    inset 0 0 30px rgba(59, 130, 246, 0.3);
  border-color: rgba(255, 215, 0, 0.8);
  filter: brightness(1.3) saturate(1.4);
}

.agent-active .agent-avatar-3d {
  border-color: rgba(16, 185, 129, 0.8);
  box-shadow: 
    0 0 40px rgba(16, 185, 129, 1),
    0 0 80px rgba(16, 185, 129, 0.6),
    inset 0 0 40px rgba(16, 185, 129, 0.4);
  animation: avatar-pulse-active 1.5s ease-in-out infinite;
}

@keyframes avatar-pulse {
  0%, 100% { 
    transform: scale(1);
    box-shadow: 
      0 0 20px rgba(59, 130, 246, 0.8),
      0 0 40px rgba(59, 130, 246, 0.4),
      inset 0 0 20px rgba(59, 130, 246, 0.2);
  }
  50% { 
    transform: scale(1.05);
    box-shadow: 
      0 0 30px rgba(59, 130, 246, 1),
      0 0 60px rgba(59, 130, 246, 0.6),
      inset 0 0 30px rgba(59, 130, 246, 0.3);
  }
}

@keyframes avatar-pulse-active {
  0%, 100% { 
    transform: scale(1.05) rotate(0deg);
    box-shadow: 
      0 0 40px rgba(16, 185, 129, 1),
      0 0 80px rgba(16, 185, 129, 0.6),
      inset 0 0 40px rgba(16, 185, 129, 0.4);
  }
  50% { 
    transform: scale(1.1) rotate(5deg);
    box-shadow: 
      0 0 50px rgba(16, 185, 129, 1),
      0 0 100px rgba(16, 185, 129, 0.8),
      inset 0 0 50px rgba(16, 185, 129, 0.5);
  }
}

.agent-name {
  color: #ffd700;
  font-weight: bold;
  font-size: 1rem;
  margin-bottom: 5px;
}

.agent-status {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.status-active {
  color: #10b981;
}

.status-idle {
  color: rgba(255, 255, 255, 0.6);
}

/* ========== MÉTRICAS FLOTANTES ========== */
.metrics-olympos {
  position: fixed;
  top: 100px;
  right: 30px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.metric-hologram {
  position: relative;
  padding: 20px;
  background: rgba(10, 35, 66, 0.8);
  backdrop-filter: blur(15px);
  border: 2px solid rgba(59, 130, 246, 0.4);
  border-radius: 15px;
  min-width: 200px;
  animation: metric-float 3s ease-in-out infinite;
  animation-delay: calc(var(--index) * 0.3s);
}

@keyframes metric-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-15px); }
}

.metric-hologram-border {
  position: absolute;
  inset: -2px;
  background: linear-gradient(135deg, transparent, rgba(59, 130, 246, 0.3), transparent);
  border-radius: 15px;
  z-index: -1;
  animation: border-rotate 3s linear infinite;
}

@keyframes border-rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.metric-content {
  display: flex;
  align-items: center;
  gap: 15px;
  color: #fff;
}

.metric-icon {
  font-size: 2rem;
  filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.6));
}

.metric-value {
  font-size: 1.8rem;
  font-weight: bold;
  color: #ffd700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
}

.metric-label {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.metrics-toggle {
  position: fixed;
  top: 30px;
  right: 30px;
  padding: 12px 25px;
  background: rgba(10, 35, 66, 0.9);
  border: 2px solid rgba(59, 130, 246, 0.4);
  border-radius: 50px;
  color: #ffd700;
  font-weight: bold;
  cursor: pointer;
  backdrop-filter: blur(10px);
  z-index: 60;
  transition: all 0.3s ease;
}

.metrics-toggle:hover {
  background: rgba(59, 130, 246, 0.6);
  transform: scale(1.05);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
}

/* ========== NOTIFICACIONES DIVINAS ========== */
.divine-notifications {
  position: fixed;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.divine-notification {
  position: relative;
  padding: 20px 40px;
  background: rgba(10, 35, 66, 0.95);
  backdrop-filter: blur(15px);
  border: 2px solid rgba(59, 130, 246, 0.5);
  border-radius: 15px;
  color: #fff;
  font-size: 1.1rem;
  text-align: center;
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
}

.divine-notification.success {
  border-color: rgba(16, 185, 129, 0.6);
  box-shadow: 0 0 30px rgba(16, 185, 129, 0.4);
}

.notification-glow {
  position: absolute;
  inset: -5px;
  background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.3), transparent);
  border-radius: 15px;
  z-index: -1;
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* ========== VOZ DE ZEUS ========== */
.zeus-voice-commands {
  position: fixed;
  bottom: 150px;
  left: 50%;
  transform: translateX(-50%);
  padding: 20px 40px;
  background: rgba(10, 35, 66, 0.9);
  border: 2px solid rgba(255, 215, 0, 0.6);
  border-radius: 20px;
  backdrop-filter: blur(15px);
  z-index: 70;
  box-shadow: 0 0 40px rgba(255, 215, 0, 0.5);
}

.voice-wave {
  width: 100px;
  height: 4px;
  margin: 0 auto 10px;
  background: linear-gradient(90deg, transparent, #ffd700, transparent);
  animation: voice-wave 1.5s ease-in-out infinite;
}

@keyframes voice-wave {
  0%, 100% { transform: scaleX(0.5); }
  50% { transform: scaleX(1); }
}

.voice-text {
  color: #ffd700;
  font-size: 1.1rem;
  font-weight: bold;
  text-align: center;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
}

/* ========== TRANSICIONES ========== */
.agents-fade-enter-active,
.agents-fade-leave-active {
  transition: all 0.5s ease;
}

.agents-fade-enter-from,
.agents-fade-leave-to {
  opacity: 0;
  transform: translateY(30px);
}

.notification-slide-enter-active,
.notification-slide-leave-active {
  transition: all 0.4s ease;
}

.notification-slide-enter-from {
  opacity: 0;
  transform: translateY(-30px);
}

.notification-slide-leave-to {
  opacity: 0;
  transform: translateY(30px);
}

/* ========== VERSION INDICATOR ========== */
.version-indicator {
  position: fixed;
  bottom: 10px;
  left: 10px;
  padding: 8px 15px;
  background: rgba(10, 35, 66, 0.9);
  border: 1px solid rgba(255, 215, 0, 0.4);
  border-radius: 20px;
  color: #ffd700;
  font-size: 0.85rem;
  font-weight: bold;
  z-index: 9999;
  backdrop-filter: blur(10px);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.3);
}

/* ========== RESPONSIVE ========== */
@media (max-width: 1200px) {
  .agents-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .agents-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .column {
    width: 50px;
  }
  
  .zeus-figure {
    width: 300px;
    height: 450px;
  }
  
  .metrics-olympos {
    right: 10px;
    top: 80px;
  }
  
  .metric-hologram {
    min-width: 150px;
    padding: 15px;
  }
}
</style>

