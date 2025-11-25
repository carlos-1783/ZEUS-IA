<template>
  <div class="activity-panel">
    <!-- Header con toggle Texto/Voz -->
    <div class="panel-header">
      <div class="agent-info">
        <img :src="agent.image" :alt="agent.name" class="agent-avatar-small" />
        <div>
          <h3>{{ agent.name }}</h3>
          <p class="agent-role">{{ agent.role }}</p>
        </div>
      </div>

      <!-- Toggle Texto/Voz -->
      <div class="communication-toggle">
        <button 
          :class="{ active: communicationMode === 'text' }"
          @click="communicationMode = 'text'"
          class="mode-btn"
        >
          💬 Texto
        </button>
        <button 
          :class="{ active: communicationMode === 'voice' }"
          @click="communicationMode = 'voice'"
          class="mode-btn"
        >
          🎤 Voz
        </button>
      </div>
    </div>

    <!-- Tabs: Workspace / Chat / Actividad / Métricas -->
    <div class="tabs">
      <button 
        :class="{ active: activeTab === 'workspace' }"
        @click="activeTab = 'workspace'"
        v-if="hasWorkspace"
      >
        🛠️ Workspace
      </button>
      <button 
        :class="{ active: activeTab === 'chat' }"
        @click="activeTab = 'chat'"
      >
        💬 Chat
      </button>
      <button 
        :class="{ active: activeTab === 'activity' }"
        @click="activeTab = 'activity'"
      >
        📊 Actividad
      </button>
      <button 
        :class="{ active: activeTab === 'metrics' }"
        @click="activeTab = 'metrics'"
      >
        📈 Métricas
      </button>
    </div>

    <!-- Workspace Tab -->
    <div v-if="activeTab === 'workspace'" class="tab-content workspace-content">
      <component :is="currentWorkspace" v-if="currentWorkspace" />
      <div v-else class="no-workspace">
        <p>Workspace no disponible para este agente</p>
      </div>
    </div>

    <!-- Chat Tab -->
    <div v-if="activeTab === 'chat'" class="tab-content">
      <!-- Modo Texto -->
      <div v-if="communicationMode === 'text'" class="text-chat">
        <div class="chat-messages" ref="messagesContainer">
          <div 
            v-for="message in messages" 
            :key="message.id"
            class="message"
            :class="{ user: message.sender === 'user', agent: message.sender === 'agent' }"
          >
            <div class="message-content">{{ message.content }}</div>
            <div class="message-time">{{ formatTime(message.timestamp) }}</div>
          </div>
        </div>

        <div v-if="isPerseoAgent" class="image-uploader-wrapper">
          <ImageUploader @uploaded="handleImageUploaded" />
          <div v-if="imageReferenceUrl" class="image-reference-chip">
            <span>Imagen adjunta</span>
            <a :href="imageReferenceUrl" target="_blank" rel="noopener">Ver</a>
            <button type="button" class="chip-remove" @click="clearImageReference">Quitar</button>
          </div>
        </div>

        <div class="chat-input-container">
          <input 
            v-model="textInput"
            @keyup.enter="sendTextMessage"
            placeholder="Escribe tu mensaje..."
            class="chat-input"
          />
          <button @click="sendTextMessage" class="send-btn">
            ➤
          </button>
        </div>
      </div>

      <!-- Modo Voz -->
      <div v-else class="voice-chat">
        <div class="voice-visualizer">
          <div class="voice-wave" :class="{ active: isListening || isSpeaking }">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>

        <p class="voice-status">
          {{ voiceStatus }}
        </p>

        <button 
          @click="toggleVoiceChat"
          class="voice-btn"
          :class="{ active: isListening }"
        >
          {{ isListening ? '⏸️ Detener' : '🎤 Hablar' }}
        </button>

        <div class="voice-transcript" v-if="currentTranscript">
          <p><strong>Tú:</strong> {{ currentTranscript }}</p>
        </div>

        <div class="voice-response" v-if="agentVoiceResponse">
          <p><strong>{{ agent.name }}:</strong> {{ agentVoiceResponse }}</p>
        </div>
      </div>
    </div>

    <!-- Activity Tab -->
    <div v-if="activeTab === 'activity'" class="tab-content activity-content">
      <div class="activity-header">
        <h4>Actividad Reciente</h4>
        <select v-model="activityDays" @change="loadActivities" class="days-selector">
          <option value="1">Últimas 24h</option>
          <option value="7">Última semana</option>
          <option value="30">Último mes</option>
        </select>
      </div>

      <div class="activity-timeline">
        <div 
          v-for="activity in activities" 
          :key="activity.id"
          class="activity-item"
          :class="activity.priority"
        >
          <div class="activity-icon" :class="activity.status">
            {{ getActivityIcon(activity.action_type) }}
          </div>
          <div class="activity-details">
            <p class="activity-description">{{ activity.description }}</p>
            <div class="activity-meta">
              <span class="activity-time">{{ formatDateTime(activity.created_at) }}</span>
              <span class="activity-status" :class="activity.status">
                {{ getStatusText(activity.status) }}
              </span>
            </div>
            <div v-if="activity.metrics" class="activity-metrics">
              <span v-for="(value, key) in activity.metrics" :key="key" class="metric-badge">
                {{ key }}: {{ value }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="activities.length === 0" class="empty-state">
          <p>No hay actividades registradas en este período</p>
        </div>
      </div>
    </div>

    <!-- Metrics Tab -->
    <div v-if="activeTab === 'metrics'" class="tab-content metrics-content">
      <h4>Métricas de {{ agent.name }}</h4>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Total de acciones</div>
          <div class="metric-value">{{ metrics.total_actions || 0 }}</div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Tasa de éxito</div>
          <div class="metric-value">{{ (metrics.success_rate || 0).toFixed(1) }}%</div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Completadas</div>
          <div class="metric-value success">{{ metrics.completed || 0 }}</div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Fallidas</div>
          <div class="metric-value error">{{ metrics.failed || 0 }}</div>
        </div>
      </div>

      <!-- Métricas específicas del agente -->
      <div v-if="metrics.specific_metrics" class="specific-metrics">
        <h5>Métricas Específicas</h5>
        <div class="specific-metrics-grid">
          <div 
            v-for="(value, key) in metrics.specific_metrics" 
            :key="key"
            class="specific-metric-item"
          >
            <span class="metric-key">{{ formatMetricKey(key) }}</span>
            <span class="metric-val">{{ formatMetricValue(value) }}</span>
          </div>
        </div>
      </div>

      <button @click="loadMetrics" class="btn-refresh-metrics">
        🔄 Actualizar Métricas
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import PerseoWorkspace from './agent-workspaces/PerseoWorkspace.vue'
import RafaelWorkspace from './agent-workspaces/RafaelWorkspace.vue'
import AfroditaWorkspace from './agent-workspaces/AfroditaWorkspace.vue'
import ThalosWorkspace from './agent-workspaces/ThalosWorkspace.vue'
import JusticiaWorkspace from './agent-workspaces/JusticiaWorkspace.vue'
import ImageUploader from '@/components/ImageUploader.jsx'

const props = defineProps({
  agent: {
    type: Object,
    required: true
  }
})

// Workspaces mapping
const workspaces = {
  'PERSEO': PerseoWorkspace,
  'RAFAEL': RafaelWorkspace,
  'AFRODITA': AfroditaWorkspace,
  'THALOS': ThalosWorkspace,
  'JUSTICIA': JusticiaWorkspace
  // ZEUS CORE no tiene workspace específico (es el orquestador)
}

const currentWorkspace = computed(() => {
  const agentKey = props.agent.name.split(' ')[0].toUpperCase()
  return workspaces[agentKey] || null
})

const hasWorkspace = computed(() => {
  return currentWorkspace.value !== null
})

// Communication mode
const communicationMode = ref('text')
const activeTab = ref(hasWorkspace.value ? 'workspace' : 'chat')

// Text chat
const messages = ref([])
const textInput = ref('')
const messagesContainer = ref(null)
const isPerseoAgent = computed(() => (props.agent?.name || '').toUpperCase().includes('PERSEO'))
const imageReferenceUrl = ref(null)

const handleImageUploaded = (payload) => {
  imageReferenceUrl.value = payload?.url || null
}

const clearImageReference = () => {
  imageReferenceUrl.value = null
}

// Voice chat
const isListening = ref(false)
const isSpeaking = ref(false)
const currentTranscript = ref('')
const agentVoiceResponse = ref('')
let recognition = null
let speechSynthesis = window.speechSynthesis

const voiceStatus = computed(() => {
  if (isListening.value) return '🎤 Escuchando...'
  if (isSpeaking.value) return '🗣️ Respondiendo...'
  return `🤖 ${props.agent.name} está listo para escucharte`
})

// Inicializar reconocimiento de voz
const initSpeechRecognition = () => {
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = 'es-ES'
    
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(result => result[0].transcript)
        .join('')
      
      currentTranscript.value = transcript
      
      // Si es final, enviar al agente
      if (event.results[event.results.length - 1].isFinal) {
        sendVoiceToAgent(transcript)
      }
    }
    
    recognition.onerror = (event) => {
      console.error('Error de reconocimiento:', event.error)
      isListening.value = false
      if (event.error === 'not-allowed') {
        alert('❌ Necesitas dar permiso al micrófono')
      }
    }
    
    recognition.onend = () => {
      isListening.value = false
    }
  }
}

// Enviar mensaje de voz al agente
const sendVoiceToAgent = async (transcript) => {
  if (!transcript.trim()) return
  
  isListening.value = false
  isSpeaking.value = true
  agentVoiceResponse.value = '⏳ Procesando...'
  
  try {
    const agentNameUrl = props.agent.name.toLowerCase().replace(/ /g, '-')
    const response = await fetch(`/api/v1/chat/${agentNameUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: transcript, context: {} })
    })
    
    const data = await response.json()
    const responseText = data.message || 'Lo siento, no pude procesar tu solicitud.'
    
    agentVoiceResponse.value = responseText
    
    // Text-to-Speech
    if (speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(responseText)
      utterance.lang = 'es-ES'
      utterance.rate = 0.9
      utterance.onend = () => {
        isSpeaking.value = false
      }
      speechSynthesis.speak(utterance)
    } else {
      isSpeaking.value = false
    }
    
  } catch (error) {
    console.error('Error en voz:', error)
    agentVoiceResponse.value = '❌ Error al procesar'
    isSpeaking.value = false
  }
}

// Activities
const activities = ref([])
const activityDays = ref(7)

// Metrics
const metrics = ref({})

onMounted(() => {
  loadActivities()
  loadMetrics()
})

// Watch para recargar cuando cambie de agente
watch(() => props.agent.name, () => {
  loadActivities()
  loadMetrics()
  messages.value = []
  imageReferenceUrl.value = null
})

const loadActivities = async () => {
  try {
    const agentName = props.agent.name.split(' ')[0].toUpperCase()
    const response = await fetch(
      `/api/v1/activities/${agentName}?days=${activityDays.value}`
    )
    const data = await response.json()
    
    if (data.success) {
      activities.value = data.activities
      console.log(`✅ Actividades de ${agentName} cargadas:`, data.total_activities)
    }
  } catch (error) {
    console.error('Error loading activities:', error)
    // Datos de ejemplo si falla
    activities.value = generateMockActivities()
  }
}

const loadMetrics = async () => {
  try {
    const agentName = props.agent.name.split(' ')[0].toUpperCase()
    const response = await fetch(
      `/api/v1/activities/${agentName}/metrics?days=30`
    )
    const data = await response.json()
    
    if (data.success) {
      metrics.value = data
      console.log(`✅ Métricas de ${agentName} cargadas`)
    }
  } catch (error) {
    console.error('Error loading metrics:', error)
    // Métricas de ejemplo
    metrics.value = generateMockMetrics()
  }
}

const sendTextMessage = async () => {
  if (!textInput.value.trim()) return
  
  const userMessage = textInput.value
  textInput.value = ''
  
  // Añadir mensaje del usuario
  messages.value.push({
    id: Date.now(),
    sender: 'user',
    content: userMessage,
    timestamp: new Date()
  })
  
  // Añadir mensaje de "procesando"
  const processingId = Date.now() + 1
  messages.value.push({
    id: processingId,
    sender: 'agent',
    content: '⏳ Procesando...',
    timestamp: new Date()
  })
  
  try {
    // Llamar al API real del agente
    const agentNameUrl = props.agent.name.toLowerCase().replace(/ /g, '-')
    const contextPayload = {}
    if (isPerseoAgent.value && imageReferenceUrl.value) {
      contextPayload.image_url = imageReferenceUrl.value
    }

    const response = await fetch(`/api/v1/chat/${agentNameUrl}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: userMessage,
        context: contextPayload
      })
    })
    
    const data = await response.json()
    
    // Remover mensaje de "procesando"
    messages.value = messages.value.filter(m => m.id !== processingId)
    
    // Añadir respuesta real del agente
    messages.value.push({
      id: Date.now() + 2,
      sender: 'agent',
      content: data.message || 'Lo siento, no pude procesar tu solicitud.',
      timestamp: new Date()
    })
    
    // Scroll al final
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
    
  } catch (error) {
    console.error('Error al comunicarse con el agente:', error)
    
    // Remover mensaje de "procesando"
    messages.value = messages.value.filter(m => m.id !== processingId)
    
    // Mostrar error
    messages.value.push({
      id: Date.now() + 2,
      sender: 'agent',
      content: '❌ Error: No pude conectarme con el agente. Intenta de nuevo.',
      timestamp: new Date()
    })
  }
}

const toggleVoiceChat = () => {
  if (!recognition) {
    initSpeechRecognition()
  }
  
  if (isListening.value) {
    // Detener
    if (recognition) {
      recognition.stop()
    }
    isListening.value = false
    currentTranscript.value = ''
  } else {
    // Iniciar
    if (recognition) {
      currentTranscript.value = ''
      agentVoiceResponse.value = ''
      recognition.start()
      isListening.value = true
    } else {
      alert('❌ Tu navegador no soporta reconocimiento de voz. Usa Chrome, Edge o Safari.')
    }
  }
}

const getActivityIcon = (actionType) => {
  const icons = {
    campaign_created: '📢',
    invoice_sent: '📄',
    security_scan: '🔍',
    threat_blocked: '🛡️',
    document_reviewed: '⚖️',
    optimization: '⚡',
    backup_created: '💾',
    default: '📌'
  }
  return icons[actionType] || icons.default
}

const getStatusText = (status) => {
  const texts = {
    completed: 'Completado',
    failed: 'Fallido',
    pending: 'Pendiente'
  }
  return texts[status] || status
}

const formatTime = (date) => {
  return new Date(date).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
}

const formatDateTime = (date) => {
  return new Date(date).toLocaleString('es-ES', { 
    day: '2-digit', 
    month: 'short', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

const formatMetricKey = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatMetricValue = (value) => {
  if (typeof value === 'number') {
    return value.toLocaleString('es-ES')
  }
  return value
}

// Mock data generators para demo
const generateMockActivities = () => {
  const agentActivities = {
    'ZEUS': [
      { id: 1, action_type: 'task_delegated', description: 'Tarea delegada a PERSEO: Crear campaña Google Ads', status: 'completed', priority: 'normal', created_at: new Date(Date.now() - 3600000) },
      { id: 2, action_type: 'coordination', description: 'Coordinación PERSEO + RAFAEL para análisis de ROI', status: 'completed', priority: 'high', created_at: new Date(Date.now() - 7200000) }
    ],
    'PERSEO': [
      { id: 1, action_type: 'campaign_created', description: 'Campaña creada en Google Ads: "Marketing Digital España"', status: 'completed', priority: 'high', metrics: { budget: '€500', roi: '4.2x' }, created_at: new Date(Date.now() - 3600000) },
      { id: 2, action_type: 'optimization', description: 'Optimización de keywords: +15% CTR', status: 'completed', priority: 'normal', metrics: { improvement: '+15%' }, created_at: new Date(Date.now() - 7200000) },
      { id: 3, action_type: 'campaign_created', description: 'Campaña Meta Ads creada: "Instagram Awareness"', status: 'completed', priority: 'normal', metrics: { budget: '€300', reach: '45k' }, created_at: new Date(Date.now() - 10800000) }
    ],
    'RAFAEL': [
      { id: 1, action_type: 'invoice_sent', description: 'Factura #2024-105 enviada al SII', status: 'completed', priority: 'high', metrics: { amount: '€1,250', tax: '€262.50' }, created_at: new Date(Date.now() - 3600000) },
      { id: 2, action_type: 'modelo_303', description: 'Modelo 303 T4/2024 calculado', status: 'completed', priority: 'critical', metrics: { result: '€2,450', type: 'A ingresar' }, created_at: new Date(Date.now() - 86400000) },
      { id: 3, action_type: 'invoice_sent', description: 'Factura #2024-106 generada (PDF)', status: 'completed', priority: 'normal', metrics: { amount: '€890' }, created_at: new Date(Date.now() - 14400000) }
    ],
    'THALOS': [
      { id: 1, action_type: 'security_scan', description: 'Escaneo de seguridad completado (0 amenazas)', status: 'completed', priority: 'normal', created_at: new Date(Date.now() - 3600000) },
      { id: 2, action_type: 'threat_blocked', description: 'Intento de acceso sospechoso bloqueado', status: 'completed', priority: 'critical', metrics: { ip: '192.168.x.x', type: 'Brute force' }, created_at: new Date(Date.now() - 7200000) },
      { id: 3, action_type: 'backup_created', description: 'Backup automático realizado', status: 'completed', priority: 'normal', metrics: { size: '2.4 GB' }, created_at: new Date(Date.now() - 10800000) }
    ],
    'JUSTICIA': [
      { id: 1, action_type: 'document_reviewed', description: 'Contrato revisado: Términos de servicio', status: 'completed', priority: 'high', created_at: new Date(Date.now() - 3600000) },
      { id: 2, action_type: 'compliance_check', description: 'Auditoría GDPR completada (98% compliance)', status: 'completed', priority: 'normal', metrics: { score: '98%' }, created_at: new Date(Date.now() - 86400000) },
      { id: 3, action_type: 'document_reviewed', description: 'Política de privacidad actualizada', status: 'completed', priority: 'normal', created_at: new Date(Date.now() - 172800000) }
    ]
  }
  
  const agentKey = props.agent.name.split(' ')[0]
  return agentActivities[agentKey] || []
}

const generateMockMetrics = () => {
  const agentMetrics = {
    'ZEUS': {
      total_actions: 45,
      completed: 42,
      failed: 3,
      success_rate: 93.3,
      specific_metrics: {
        tasks_delegated: 38,
        coordinations: 12,
        efficiency: 94
      }
    },
    'PERSEO': {
      total_actions: 28,
      completed: 27,
      failed: 1,
      success_rate: 96.4,
      specific_metrics: {
        campaigns_created: 8,
        campaigns_optimized: 15,
        total_ad_spend: 2450,
        average_roi: 4.2
      }
    },
    'RAFAEL': {
      total_actions: 35,
      completed: 35,
      failed: 0,
      success_rate: 100,
      specific_metrics: {
        invoices_sent: 28,
        tax_models_filed: 3,
        total_invoiced: 45600,
        total_tax: 9576
      }
    },
    'THALOS': {
      total_actions: 52,
      completed: 51,
      failed: 1,
      success_rate: 98.1,
      specific_metrics: {
        threats_blocked: 12,
        security_scans: 28,
        backups_created: 7,
        incidents: 2
      }
    },
    'JUSTICIA': {
      total_actions: 18,
      completed: 18,
      failed: 0,
      success_rate: 100,
      specific_metrics: {
        documents_reviewed: 12,
        compliance_checks: 4,
        legal_issues: 0
      }
    }
  }
  
  const agentKey = props.agent.name.split(' ')[0]
  return agentMetrics[agentKey] || {}
}

// Inicializar con mock data
onMounted(() => {
  if (activities.value.length === 0) {
    activities.value = generateMockActivities()
  }
  if (Object.keys(metrics.value).length === 0) {
    metrics.value = generateMockMetrics()
  }
})
</script>

<style scoped>
.activity-panel {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  padding: 32px;
  height: auto;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  width: 100%;
}

/* Header */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar-small {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.agent-info h3 {
  margin: 0;
  font-size: 18px;
  color: #fff;
}

.agent-role {
  margin: 4px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

/* Communication Toggle */
.communication-toggle {
  display: flex;
  gap: 8px;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px;
  border-radius: 8px;
}

.mode-btn {
  padding: 8px 16px;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  font-size: 14px;
}

.mode-btn.active {
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: white;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.tabs button {
  flex: 1;
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}

.tabs button.active {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

/* Tab Content */
.tab-content {
  flex: 1;
  overflow-y: auto;
}

/* Text Chat */
.text-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
}

.message.agent {
  align-self: flex-start;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.2);
  color: #fff;
}

.message.agent .message-content {
  background: rgba(139, 92, 246, 0.2);
}

.message-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
  padding: 0 8px;
}

.image-uploader-wrapper {
  margin: 12px 16px 0;
  padding: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.25);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.perseo-image-uploader {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.perseo-image-uploader input[type="file"] {
  color: rgba(255, 255, 255, 0.8);
}

.uploader-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}

.uploader-link {
  font-size: 12px;
  color: #93c5fd;
}

.uploader-body {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.uploader-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}

.uploader-preview {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.uploader-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.uploader-reset {
  position: absolute;
  top: 4px;
  right: 4px;
  border: none;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.uploader-error,
.uploader-hint {
  font-size: 12px;
  color: #f87171;
}

.image-reference-chip {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.2);
  color: #bfdbfe;
  font-size: 13px;
}

.image-reference-chip a {
  color: #dbeafe;
  text-decoration: underline;
}

.chip-remove {
  border: none;
  background: transparent;
  color: #fff;
  cursor: pointer;
  font-size: 12px;
}

.chat-input-container {
  display: flex;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-input {
  flex: 1;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
}

.send-btn {
  padding: 12px 20px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
}

/* Voice Chat */
.voice-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 24px;
}

.voice-visualizer {
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-wave {
  display: flex;
  gap: 4px;
  align-items: center;
}

.voice-wave span {
  width: 4px;
  height: 20px;
  background: #3b82f6;
  border-radius: 2px;
  transition: all 0.2s;
}

.voice-wave.active span {
  animation: wave 0.6s ease-in-out infinite;
}

.voice-wave span:nth-child(2) { animation-delay: 0.1s; }
.voice-wave span:nth-child(3) { animation-delay: 0.2s; }
.voice-wave span:nth-child(4) { animation-delay: 0.3s; }
.voice-wave span:nth-child(5) { animation-delay: 0.4s; }

@keyframes wave {
  0%, 100% { height: 20px; }
  50% { height: 60px; }
}

.voice-status {
  color: rgba(255, 255, 255, 0.8);
  font-size: 16px;
  text-align: center;
}

.voice-btn {
  padding: 16px 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  color: white;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.voice-btn.active {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  animation: pulse 1.5s infinite;
}

.voice-transcript, .voice-response {
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  text-align: center;
  max-width: 400px;
}

/* Activity Timeline */
.activity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.activity-header h4 {
  margin: 0;
  font-size: 18px;
}

.days-selector {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
}

.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.activity-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid #3b82f6;
  border-radius: 8px;
  transition: all 0.2s;
}

.activity-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.activity-item.high {
  border-left-color: #eab308;
}

.activity-item.critical {
  border-left-color: #ef4444;
}

.activity-icon {
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  flex-shrink: 0;
}

.activity-icon.failed {
  background: rgba(239, 68, 68, 0.2);
}

.activity-details {
  flex: 1;
}

.activity-description {
  margin: 0 0 8px;
  color: #fff;
  font-size: 14px;
}

.activity-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.activity-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.activity-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.activity-status.failed {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.activity-metrics {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.metric-badge {
  font-size: 11px;
  padding: 4px 8px;
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  border-radius: 4px;
}

/* Metrics */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 8px;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-value.success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-value.error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.specific-metrics {
  margin-top: 24px;
}

.specific-metrics h5 {
  margin: 0 0 16px;
  font-size: 16px;
}

.specific-metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.specific-metric-item {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.metric-key {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.metric-val {
  font-size: 14px;
  font-weight: 600;
  color: #3b82f6;
}

.btn-refresh-metrics {
  width: 100%;
  padding: 12px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #3b82f6;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 20px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: rgba(255, 255, 255, 0.4);
}

/* Workspace Tab */
.workspace-content {
  padding: 0;
  overflow: visible;
  max-height: none;
}

.no-workspace {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 16px;
}

/* Responsive */
@media (max-width: 768px) {
  .activity-panel {
    height: auto;
    min-height: unset;
    max-height: calc(100vh - 140px);
    width: 100%;
    padding: 18px 14px;
  }

  .metrics-grid,
  .specific-metrics-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    gap: 16px;
  }

  .tab-content,
  .workspace-content {
    max-height: none;
  }
}
</style>

