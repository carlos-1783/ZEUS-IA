<template>
  <!-- Dashboard Profesional Corporativo -->
  <DashboardProfesional 
    v-if="firstPersonMode"
    :agents="olymposAgents"
    @agentClicked="summonAgent"
  />
  
  <!-- Modo Dashboard 2D -->
  <div v-else class="olympos-dashboard">
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

    <!-- Agentes paseando por el Olimpo (solo los 4 subordinados) -->
    <div class="olympos-wandering-agents">
      <div 
        v-for="agent in olymposAgents.filter(a => a.id !== 1)" 
        :key="agent.id"
        @click="summonAgent(agent)"
        class="wandering-agent"
        :class="{ 
          'summoned': agent.active,
          'idle': !agent.active
        }"
        :style="getAgentPosition(agent.id)"
      >
        <div class="agent-floating-container">
          <!-- Avatar con aura -->
          <div class="agent-aura"></div>
          <img 
            v-if="agent.image" 
            :src="agent.image" 
            :alt="agent.name"
            class="agent-wandering-avatar"
          />
          <!-- Partículas flotando -->
          <div class="agent-particles">
            <div class="particle" v-for="i in 4" :key="i" :style="{ '--delay': i * 0.5 }"></div>
          </div>
          <!-- Nombre del agente -->
          <div class="agent-wandering-name">{{ agent.name }}</div>
          <div class="agent-wandering-status">{{ agent.status }}</div>
        </div>
      </div>
    </div>

    <!-- Panel de Conversación por Voz -->
    <transition name="voice-slide">
      <div v-if="voiceActive && activeAgent" class="voice-panel">
        <!-- Avatar VIVO con animaciones -->
        <div class="voice-agent-avatar" :class="{ 'speaking': agentSpeaking, 'breathing': !agentSpeaking }">
          <div class="avatar-container">
            <img 
              v-if="activeAgent.image" 
              :src="activeAgent.image" 
              :alt="activeAgent.name"
              class="avatar-voice-img"
            />
            <!-- Ojos animados superpuestos -->
            <div class="eyes-layer" v-if="activeAgent.id <= 2">
              <div class="eye eye-left"></div>
              <div class="eye eye-right"></div>
            </div>
            <!-- Efecto de respiración (partículas de energía) -->
            <div class="breath-particles">
              <div class="particle" v-for="i in 8" :key="i" :style="{ '--i': i }"></div>
            </div>
            <!-- Labios hablando (cuando activo) -->
            <div v-if="agentSpeaking" class="mouth-indicator"></div>
          </div>
          <div class="voice-glow"></div>
          <div class="voice-rings">
            <div class="ring ring-1"></div>
            <div class="ring ring-2"></div>
            <div class="ring ring-3"></div>
          </div>
        </div>

        <!-- Nombre y estado -->
        <div class="voice-agent-info">
          <div class="voice-agent-name">{{ activeAgent.name }}</div>
          <div class="voice-agent-status">
            <span v-if="listening">🎤 Escuchando...</span>
            <span v-else-if="agentSpeaking">🗣️ Hablando...</span>
            <span v-else>💬 Listo para conversar</span>
          </div>
        </div>

        <!-- Subtítulos / Transcripción -->
        <div class="voice-subtitles">
          <div v-if="currentTranscript" class="subtitle user">
            <strong>Tú:</strong> {{ currentTranscript }}
          </div>
          <div v-if="agentResponse" class="subtitle agent" :class="{ 'speaking': agentSpeaking }">
            <strong>{{ activeAgent.name }}:</strong> {{ agentResponse }}
          </div>
        </div>

        <!-- Controles de voz -->
        <div class="voice-controls">
          <button 
            @click="toggleVoiceListening" 
            class="voice-btn"
            :class="{ 'active': listening }"
          >
            <span v-if="listening">⏸️ PARAR</span>
            <span v-else>🎤 HABLAR</span>
          </button>
          
          <button 
            @click="stopAgentSpeaking" 
            class="voice-btn secondary"
            v-if="agentSpeaking"
          >
            🔇 SILENCIAR
          </button>

          <button @click="closeVoice" class="voice-btn close">
            ✕ CERRAR
          </button>
        </div>

        <!-- Onda de voz visual -->
        <div v-if="listening" class="voice-wave-container">
          <div class="voice-wave" v-for="i in 5" :key="i" :style="{ animationDelay: `${i * 0.1}s` }"></div>
        </div>
      </div>
    </transition>

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

    <!-- Botón Admin Panel -->
    <button @click="goToAdmin" class="admin-toggle">
      ⚙️ ADMIN
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
      🏛️ OLIMPO v1.0.6 GLB-FIXED
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
import Agent3DAvatar from '@/components/Agent3DAvatar.vue'
import DashboardProfesional from '@/components/DashboardProfesional.vue'

const router = useRouter()
const authStore = useAuthStore()

// Estado
const firstPersonMode = ref(true)  // MODO 3D POR DEFECTO
const showAgents = ref(true)  // Mostrar agentes por defecto
const showMetrics = ref(true)
const activeAgent = ref(null)
const notifications = ref([])

// Estado de conversación por voz
const voiceActive = ref(false)
const listening = ref(false)
const agentSpeaking = ref(false)
const currentTranscript = ref('')
const agentResponse = ref('')

// Web Speech API
let recognition = null
let speechSynthesis = window.speechSynthesis
let currentUtterance = null

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
    image: '/images/avatars/rafael-avatar.jpg',
    active: false, 
    description: 'Guardián Fiscal', 
    status: 'online' 
  },
  { 
    id: 4, 
    name: 'THALOS', 
    icon: '🛡️', 
    image: '/images/avatars/thalos-avatar.jpg',
    active: false, 
    description: 'Defensor Cibernético', 
    status: 'online' 
  },
  { 
    id: 5, 
    name: 'JUSTICIA', 
    icon: '⚖️', 
    image: '/images/avatars/justicia-avatar.jpg',
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

// Ir al Admin Panel
const goToAdmin = () => {
  router.push('/admin')
}

// Inicializar Speech Recognition
const initSpeechRecognition = () => {
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'es-ES'
    
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(result => result[0].transcript)
        .join('')
      
      currentTranscript.value = transcript
      
      // Si es final, enviar al agente
      if (event.results[event.results.length - 1].isFinal) {
        sendVoiceMessage(transcript)
      }
    }
    
    recognition.onerror = (event) => {
      console.error('Error de reconocimiento:', event.error)
      listening.value = false
      showNotification('error', '❌ Error en reconocimiento de voz')
    }
    
    recognition.onend = () => {
      listening.value = false
    }
  } else {
    showNotification('error', '❌ Tu navegador no soporta reconocimiento de voz')
  }
}

// Posiciones de agentes paseando por el Olimpo
const getAgentPosition = (agentId) => {
  const positions = {
    2: { left: '15%', top: '25%', animationDelay: '0s' },      // PERSEO - izquierda arriba
    3: { right: '15%', top: '30%', animationDelay: '1s' },     // RAFAEL - derecha arriba
    4: { left: '20%', bottom: '20%', animationDelay: '2s' },   // THALOS - izquierda abajo
    5: { right: '20%', bottom: '25%', animationDelay: '3s' }   // JUSTICIA - derecha abajo
  }
  return positions[agentId] || {}
}

// Convocar agente (se acerca al centro y abre conversación)
const summonAgent = (agent) => {
  // Desactivar todos
  olymposAgents.value.forEach(a => a.active = false)
  
  // Activar el seleccionado
  agent.active = true
  activeAgent.value = agent
  
  // Esperar animación de acercamiento
  setTimeout(() => {
    voiceActive.value = true
    
    // Inicializar speech recognition si no existe
    if (!recognition) {
      initSpeechRecognition()
    }
    
    // Mensaje de bienvenida con voz
    const greeting = `Soy ${agent.name}, ${agent.description}. ¿En qué puedo ayudarte?`
    agentResponse.value = greeting
    speakText(greeting)
    
    showNotification('success', `🎤 ${agent.name} se acerca para conversar`)
  }, 800) // Esperar animación de acercamiento
}

// Cerrar conversación por voz
const closeVoice = () => {
  voiceActive.value = false
  stopListening()
  stopAgentSpeaking()
  currentTranscript.value = ''
  agentResponse.value = ''
  
  if (activeAgent.value) {
    activeAgent.value.active = false
  }
}

// Iniciar/detener escucha
const toggleVoiceListening = () => {
  if (listening.value) {
    stopListening()
  } else {
    startListening()
  }
}

const startListening = () => {
  if (recognition) {
    currentTranscript.value = ''
    recognition.start()
    listening.value = true
    showNotification('info', '🎤 Escuchando...')
  }
}

const stopListening = () => {
  if (recognition && listening.value) {
    recognition.stop()
    listening.value = false
  }
}

// Enviar mensaje de voz al backend
const sendVoiceMessage = async (transcript) => {
  if (!transcript.trim() || !activeAgent.value) return
  
  stopListening()
  
  try {
    // Llamar al endpoint de chat
    const agentNameUrl = activeAgent.value.name.toLowerCase().replace(/ /g, '-')
    const response = await fetch(`/api/v1/chat/${agentNameUrl}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: transcript,
        context: {}
      })
    })
    
    const data = await response.json()
    
    // Mostrar y hablar la respuesta
    const responseText = data.message || 'Lo siento, no pude procesar tu solicitud.'
    agentResponse.value = responseText
    speakText(responseText)
    
    if (data.hitl_required) {
      showNotification('warning', '⚠️ Esta acción requiere aprobación humana')
    }
    
  } catch (error) {
    console.error('Error en conversación:', error)
    const errorMsg = 'Lo siento, tuve un problema al procesarlo.'
    agentResponse.value = errorMsg
    speakText(errorMsg)
    showNotification('error', '❌ Error al comunicarse con el agente')
  }
}

// Hablar texto (Text-to-Speech)
const speakText = (text) => {
  // Detener cualquier voz anterior
  stopAgentSpeaking()
  
  // Crear nueva utterance
  currentUtterance = new SpeechSynthesisUtterance(text)
  currentUtterance.lang = 'es-ES'
  currentUtterance.rate = 1.0
  currentUtterance.pitch = 1.0
  
  // Seleccionar voz española si está disponible
  const voices = speechSynthesis.getVoices()
  const spanishVoice = voices.find(voice => voice.lang.startsWith('es'))
  if (spanishVoice) {
    currentUtterance.voice = spanishVoice
  }
  
  // Eventos
  currentUtterance.onstart = () => {
    agentSpeaking.value = true
  }
  
  currentUtterance.onend = () => {
    agentSpeaking.value = false
    currentUtterance = null
  }
  
  currentUtterance.onerror = () => {
    agentSpeaking.value = false
    currentUtterance = null
  }
  
  // Hablar
  speechSynthesis.speak(currentUtterance)
}

// Detener voz del agente
const stopAgentSpeaking = () => {
  if (speechSynthesis.speaking) {
    speechSynthesis.cancel()
  }
  agentSpeaking.value = false
  currentUtterance = null
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

/* ========== AGENTES PASEANDO POR EL OLIMPO ========== */
.olympos-wandering-agents {
  position: absolute;
  inset: 0;
  z-index: 20;
  pointer-events: none;
}

.wandering-agent {
  position: absolute;
  width: 120px;
  height: 160px;
  cursor: pointer;
  pointer-events: all;
  transition: all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 20;
}

/* IDLE - Paseando flotando por el Olimpo */
.wandering-agent.idle {
  animation: agent-wander 12s ease-in-out infinite;
}

@keyframes agent-wander {
  0%, 100% { 
    transform: translateY(0) translateX(0) scale(1);
  }
  20% { 
    transform: translateY(-30px) translateX(20px) scale(1.05) rotate(3deg);
  }
  40% { 
    transform: translateY(-15px) translateX(-25px) scale(0.98) rotate(-2deg);
  }
  60% { 
    transform: translateY(-35px) translateX(15px) scale(1.03) rotate(2deg);
  }
  80% { 
    transform: translateY(-20px) translateX(-10px) scale(1.02) rotate(-3deg);
  }
}

/* SUMMONED - Se mueve al centro para conversar */
.wandering-agent.summoned {
  left: 50% !important;
  top: 30% !important;
  right: auto !important;
  bottom: auto !important;
  transform: translate(-50%, -50%) scale(1.5);
  z-index: 150;
  filter: brightness(1.4);
  pointer-events: none;
}

.agent-floating-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: gentle-float 4s ease-in-out infinite;
}

@keyframes gentle-float {
  0%, 100% { 
    transform: translateY(0);
  }
  50% { 
    transform: translateY(-20px);
  }
}

.agent-aura {
  position: absolute;
  inset: -20px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, transparent 70%);
  border-radius: 50%;
  animation: aura-pulse-wander 3s ease-in-out infinite;
  z-index: -1;
}

.wandering-agent:hover .agent-aura {
  background: radial-gradient(circle, rgba(255, 215, 0, 0.5) 0%, transparent 70%);
}

@keyframes aura-pulse-wander {
  0%, 100% { 
    opacity: 0.5;
    transform: scale(0.9);
  }
  50% { 
    opacity: 1;
    transform: scale(1.2);
  }
}

.agent-wandering-avatar {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid rgba(59, 130, 246, 0.7);
  box-shadow: 
    0 0 30px rgba(59, 130, 246, 0.6),
    inset 0 0 20px rgba(255, 215, 0, 0.2);
  transition: all 0.5s ease;
  animation: avatar-breathe-wander 5s ease-in-out infinite;
}

@keyframes avatar-breathe-wander {
  0%, 100% { 
    transform: scale(1);
    filter: brightness(1);
  }
  50% { 
    transform: scale(1.04);
    filter: brightness(1.15);
  }
}

.wandering-agent:hover .agent-wandering-avatar {
  transform: scale(1.2);
  border-color: rgba(255, 215, 0, 1);
  box-shadow: 
    0 0 50px rgba(255, 215, 0, 0.9),
    inset 0 0 30px rgba(255, 215, 0, 0.4);
}

.agent-particles {
  position: absolute;
  top: 10px;
  left: 50%;
  width: 120px;
  height: 120px;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: -1;
}

.agent-particles .particle {
  position: absolute;
  width: 4px;
  height: 4px;
  background: rgba(255, 215, 0, 0.8);
  border-radius: 50%;
  top: 50%;
  left: 50%;
  animation: particle-orbit-wander 5s ease-in-out infinite;
  animation-delay: calc(var(--delay) * 1s);
}

@keyframes particle-orbit-wander {
  0%, 100% {
    transform: translate(-50%, -50%) rotate(0deg) translateX(45px);
    opacity: 0.3;
  }
  50% {
    transform: translate(-50%, -50%) rotate(360deg) translateX(55px);
    opacity: 1;
  }
}

.agent-wandering-name {
  font-size: 1rem;
  font-weight: bold;
  color: #ffd700;
  text-shadow: 
    0 0 15px rgba(255, 215, 0, 0.9),
    0 2px 4px rgba(0, 0, 0, 0.5);
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.agent-wandering-status {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.8);
  text-transform: uppercase;
  letter-spacing: 2px;
  text-shadow: 0 0 10px rgba(59, 130, 246, 0.6);
}

/* ========== PANEL DE AGENTES (OCULTO) ========== */
.agents-panel {
  display: none;
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

.admin-toggle {
  position: fixed;
  top: 30px;
  right: 200px;
  padding: 12px 25px;
  background: rgba(75, 0, 130, 0.9);
  border: 2px solid rgba(139, 92, 246, 0.4);
  border-radius: 50px;
  color: #ffd700;
  font-weight: bold;
  cursor: pointer;
  backdrop-filter: blur(10px);
  z-index: 60;
  transition: all 0.3s ease;
}

.admin-toggle:hover {
  background: rgba(139, 92, 246, 0.6);
  transform: scale(1.05);
  box-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
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

/* ========== VOICE PANEL ========== */
.voice-panel {
  position: fixed;
  left: 50%;
  bottom: 100px;
  transform: translateX(-50%);
  width: 600px;
  min-height: 400px;
  background: rgba(10, 35, 66, 0.98);
  backdrop-filter: blur(25px);
  border: 3px solid rgba(255, 215, 0, 0.6);
  border-radius: 30px;
  box-shadow: 
    0 0 60px rgba(255, 215, 0, 0.5),
    inset 0 0 40px rgba(59, 130, 246, 0.2);
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  gap: 25px;
  animation: voice-panel-appear 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes voice-panel-appear {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(100px) scale(0.8);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

.chat-header {
  padding: 20px;
  background: rgba(59, 130, 246, 0.2);
  border-bottom: 2px solid rgba(59, 130, 246, 0.4);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-agent-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.chat-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 2px solid rgba(255, 215, 0, 0.6);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
}

.chat-agent-name {
  color: #ffd700;
  font-weight: bold;
  font-size: 1.1rem;
}

.chat-agent-desc {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.85rem;
}

.chat-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 1.5rem;
  cursor: pointer;
  padding: 5px 10px;
  transition: all 0.3s ease;
}

.chat-close:hover {
  color: #ff4444;
  transform: scale(1.2);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.8);
}

.chat-message {
  display: flex;
  flex-direction: column;
  max-width: 80%;
  animation: message-appear 0.3s ease;
}

@keyframes message-appear {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-message.user {
  align-self: flex-end;
}

.chat-message.agent {
  align-self: flex-start;
}

.message-content {
  padding: 12px 18px;
  border-radius: 15px;
  word-wrap: break-word;
}

.chat-message.user .message-content {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.8), rgba(59, 130, 246, 0.6));
  color: #fff;
  border-bottom-right-radius: 5px;
}

.chat-message.agent .message-content {
  background: rgba(255, 215, 0, 0.2);
  border: 1px solid rgba(255, 215, 0, 0.4);
  color: #ffd700;
  border-bottom-left-radius: 5px;
}

.message-time {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 5px;
  padding: 0 5px;
}

.chat-message.user .message-time {
  text-align: right;
}

.typing-indicator {
  display: inline-flex;
  gap: 5px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: rgba(255, 215, 0, 0.8);
  border-radius: 50%;
  animation: typing-bounce 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing-bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.chat-input-container {
  padding: 20px;
  background: rgba(0, 0, 0, 0.3);
  border-top: 2px solid rgba(59, 130, 246, 0.4);
  display: flex;
  gap: 10px;
}

.chat-input {
  flex: 1;
  padding: 12px 18px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-radius: 25px;
  color: #fff;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s ease;
}

.chat-input:focus {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
}

.chat-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send {
  padding: 12px 25px;
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.8), rgba(255, 215, 0, 0.6));
  border: none;
  border-radius: 25px;
  color: #0a1628;
  font-weight: bold;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.chat-send:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(255, 215, 0, 1), rgba(255, 215, 0, 0.8));
  transform: scale(1.05);
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.6);
}

.chat-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Chat slide transition */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.4s ease;
}

.chat-slide-enter-from {
  opacity: 0;
  transform: translateY(-50%) translateX(100px);
}

.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(100px);
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

