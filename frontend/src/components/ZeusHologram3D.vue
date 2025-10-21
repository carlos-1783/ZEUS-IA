<template>
  <div class="zeus-hologram-container">
    <!-- Canvas 3D para hologramas -->
    <canvas 
      ref="hologramCanvas" 
      class="hologram-canvas"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @wheel="onWheel"
    ></canvas>
    
    <!-- Panel de control holográfico -->
    <div class="holographic-controls">
      <div class="agent-status-panel">
        <div 
          v-for="agent in agents" 
          :key="agent.name"
          class="agent-card"
          :class="{ active: agent.status === 'active' }"
          @click="selectAgent(agent)"
        >
          <div class="agent-avatar">
            <div class="holographic-avatar" :class="agent.type">
              {{ agent.name.charAt(0) }}
            </div>
          </div>
          <div class="agent-info">
            <h3>{{ agent.name }}</h3>
            <p>{{ agent.description }}</p>
            <div class="status-indicator" :class="agent.status">
              {{ agent.status.toUpperCase() }}
            </div>
          </div>
        </div>
      </div>
      
      <!-- Comando input holográfico -->
      <div class="command-input-panel">
        <div class="holographic-input">
          <input 
            v-model="currentCommand"
            @keyup.enter="executeCommand"
            placeholder="Ingresa comando ZEUS..."
            class="command-input"
          />
          <button @click="executeCommand" class="execute-btn">
            EJECUTAR
          </button>
        </div>
        
        <!-- Respuesta del agente -->
        <div v-if="lastResponse" class="agent-response">
          <div class="response-header">
            <span class="agent-name">{{ lastResponse.agent }}</span>
            <span class="response-time">{{ formatTime(lastResponse.timestamp) }}</span>
          </div>
          <div class="response-content">
            <p>{{ lastResponse.message }}</p>
            <div v-if="lastResponse.voice" class="voice-indicator">
              🔊 {{ lastResponse.voice }}
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Efectos holográficos de fondo -->
    <div class="holographic-background">
      <div class="grid-lines"></div>
      <div class="particles"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as THREE from 'three'
import { useAuthStore } from '@/stores/auth'

// Props
const props = defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 600 }
})

// Refs
const hologramCanvas = ref(null)
const currentCommand = ref('')
const lastResponse = ref(null)

// Estado 3D
let scene, camera, renderer, controls
let holographicObjects = []
let animationId = null
let isMouseDown = false
let mouseX = 0, mouseY = 0

// Agentes ZEUS
const agents = ref([
  {
    name: 'ZEUS',
    type: 'zeus',
    description: 'Núcleo principal del sistema',
    status: 'inactive',
    position: { x: 0, y: 0, z: 0 }
  },
  {
    name: 'THALOS',
    type: 'thalos',
    description: 'Seguridad y protección',
    status: 'inactive',
    position: { x: -2, y: 0, z: 0 }
  },
  {
    name: 'JUSTICIA',
    type: 'justicia',
    description: 'Ética y cumplimiento',
    status: 'inactive',
    position: { x: 2, y: 0, z: 0 }
  },
  {
    name: 'RAFAEL',
    type: 'rafael',
    description: 'Salud y bienestar',
    status: 'inactive',
    position: { x: 0, y: 2, z: 0 }
  },
  {
    name: 'ANÁLISIS',
    type: 'analisis',
    description: 'Análisis de datos',
    status: 'inactive',
    position: { x: 0, y: -2, z: 0 }
  },
  {
    name: 'IA',
    type: 'ia',
    description: 'Inteligencia artificial',
    status: 'inactive',
    position: { x: 0, y: 0, z: 2 }
  }
])

// Store
const authStore = useAuthStore()

// ========================================
// INICIALIZACIÓN 3D
// ========================================

onMounted(async () => {
  await nextTick()
  initThreeJS()
  createHolographicScene()
  animate()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  if (renderer) {
    renderer.dispose()
  }
})

function initThreeJS() {
  // Crear escena
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x000011)
  
  // Crear cámara
  camera = new THREE.PerspectiveCamera(
    75, 
    props.width / props.height, 
    0.1, 
    1000
  )
  camera.position.set(0, 0, 10)
  
  // Crear renderer
  renderer = new THREE.WebGLRenderer({ 
    canvas: hologramCanvas.value,
    antialias: true,
    alpha: true
  })
  renderer.setSize(props.width, props.height)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  
  // Configurar iluminación holográfica
  setupHolographicLighting()
}

function setupHolographicLighting() {
  // Luz ambiental holográfica
  const ambientLight = new THREE.AmbientLight(0x00ffff, 0.3)
  scene.add(ambientLight)
  
  // Luz direccional principal
  const directionalLight = new THREE.DirectionalLight(0x00ffff, 1)
  directionalLight.position.set(5, 5, 5)
  directionalLight.castShadow = true
  scene.add(directionalLight)
  
  // Luces de punto para efecto holográfico
  const pointLight1 = new THREE.PointLight(0xff00ff, 0.5, 100)
  pointLight1.position.set(-5, 0, 5)
  scene.add(pointLight1)
  
  const pointLight2 = new THREE.PointLight(0x00ff00, 0.5, 100)
  pointLight2.position.set(5, 0, 5)
  scene.add(pointLight2)
}

function createHolographicScene() {
  // Crear objetos holográficos para cada agente
  agents.value.forEach((agent, index) => {
    createAgentHologram(agent, index)
  })
  
  // Crear efectos de partículas holográficas
  createHolographicParticles()
  
  // Crear grid holográfico
  createHolographicGrid()
}

function createAgentHologram(agent, index) {
  // Geometría del avatar
  const geometry = new THREE.ConeGeometry(0.5, 2, 8)
  
  // Material holográfico
  const material = new THREE.MeshPhongMaterial({
    color: getAgentColor(agent.type),
    transparent: true,
    opacity: 0.8,
    emissive: getAgentColor(agent.type),
    emissiveIntensity: 0.2
  })
  
  // Crear mesh
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(agent.position.x, agent.position.y, agent.position.z)
  mesh.userData = { agent: agent }
  
  // Añadir efecto de rotación
  mesh.rotation.y = index * Math.PI / 3
  
  scene.add(mesh)
  holographicObjects.push(mesh)
  
  // Crear anillo holográfico alrededor del agente
  const ringGeometry = new THREE.RingGeometry(0.8, 1.0, 16)
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: getAgentColor(agent.type),
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide
  })
  
  const ring = new THREE.Mesh(ringGeometry, ringMaterial)
  ring.position.set(agent.position.x, agent.position.y, agent.position.z - 0.1)
  ring.rotation.x = -Math.PI / 2
  
  scene.add(ring)
  holographicObjects.push(ring)
}

function getAgentColor(type) {
  const colors = {
    zeus: 0xff6b00,      // Naranja dorado
    thalos: 0x0066ff,    // Azul
    justicia: 0xff0066,  // Rosa
    rafael: 0x00ff66,    // Verde
    analisis: 0x6600ff,  // Púrpura
    ia: 0xff6600         // Naranja
  }
  return colors[type] || 0x00ffff
}

function createHolographicParticles() {
  const particleCount = 100
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(particleCount * 3)
  
  for (let i = 0; i < particleCount * 3; i++) {
    positions[i] = (Math.random() - 0.5) * 20
  }
  
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  
  const material = new THREE.PointsMaterial({
    color: 0x00ffff,
    size: 0.1,
    transparent: true,
    opacity: 0.6
  })
  
  const particles = new THREE.Points(geometry, material)
  scene.add(particles)
  holographicObjects.push(particles)
}

function createHolographicGrid() {
  const gridSize = 20
  const divisions = 20
  
  const gridHelper = new THREE.GridHelper(gridSize, divisions, 0x00ffff, 0x004444)
  gridHelper.position.y = -5
  scene.add(gridHelper)
  holographicObjects.push(gridHelper)
}

// ========================================
// ANIMACIÓN Y CONTROLES
// ========================================

function animate() {
  animationId = requestAnimationFrame(animate)
  
  // Rotar objetos holográficos
  holographicObjects.forEach((obj, index) => {
    if (obj.userData && obj.userData.agent) {
      obj.rotation.y += 0.01
      obj.rotation.x += 0.005
    }
  })
  
  // Rotar cámara suavemente
  if (!isMouseDown) {
    camera.position.x = Math.sin(Date.now() * 0.0005) * 10
    camera.position.z = Math.cos(Date.now() * 0.0005) * 10
    camera.lookAt(0, 0, 0)
  }
  
  renderer.render(scene, camera)
}

// ========================================
// CONTROLES DE MOUSE
// ========================================

function onMouseDown(event) {
  isMouseDown = true
  mouseX = event.clientX
  mouseY = event.clientY
}

function onMouseMove(event) {
  if (!isMouseDown) return
  
  const deltaX = event.clientX - mouseX
  const deltaY = event.clientY - mouseY
  
  camera.position.x += deltaX * 0.01
  camera.position.y -= deltaY * 0.01
  
  mouseX = event.clientX
  mouseY = event.clientY
}

function onMouseUp() {
  isMouseDown = false
}

function onWheel(event) {
  camera.position.z += event.deltaY * 0.01
  camera.position.z = Math.max(5, Math.min(20, camera.position.z))
}

// ========================================
// FUNCIONES DE AGENTES
// ========================================

function selectAgent(agent) {
  console.log(`Agente seleccionado: ${agent.name}`)
  // Enfocar cámara en el agente seleccionado
  camera.position.x = agent.position.x
  camera.position.y = agent.position.y
  camera.position.z = agent.position.z + 5
  camera.lookAt(agent.position.x, agent.position.y, agent.position.z)
}

async function executeCommand() {
  if (!currentCommand.value.trim()) return
  
  try {
    const response = await fetch('/api/v1/zeus/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({
        command: currentCommand.value,
        data: {}
      })
    })
    
    const result = await response.json()
    lastResponse.value = result
    
    // Actualizar estado del agente
    if (result.agent) {
      const agent = agents.value.find(a => a.name === result.agent)
      if (agent) {
        agent.status = result.status === 'success' ? 'active' : 'error'
      }
    }
    
    // Reproducir voz si está disponible
    if (result.voice) {
      speakText(result.voice)
    }
    
    // Limpiar comando
    currentCommand.value = ''
    
  } catch (error) {
    console.error('Error ejecutando comando ZEUS:', error)
    lastResponse.value = {
      agent: 'ERROR',
      message: 'Error ejecutando comando',
      timestamp: new Date().toISOString(),
      status: 'error'
    }
  }
}

function speakText(text) {
  if ('speechSynthesis' in window) {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'es-ES'
    utterance.rate = 0.9
    utterance.pitch = 1.0
    speechSynthesis.speak(utterance)
  }
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}
</script>

<style scoped>
.zeus-hologram-container {
  position: relative;
  width: 100%;
  height: 100vh;
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
  overflow: hidden;
}

.hologram-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}

.holographic-controls {
  position: absolute;
  top: 20px;
  left: 20px;
  right: 20px;
  z-index: 10;
  display: flex;
  gap: 20px;
}

.agent-status-panel {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.agent-card {
  background: rgba(0, 255, 255, 0.1);
  border: 1px solid rgba(0, 255, 255, 0.3);
  border-radius: 10px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  min-width: 200px;
}

.agent-card:hover {
  background: rgba(0, 255, 255, 0.2);
  border-color: rgba(0, 255, 255, 0.6);
  transform: translateY(-2px);
}

.agent-card.active {
  background: rgba(0, 255, 0, 0.2);
  border-color: rgba(0, 255, 0, 0.6);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
}

.agent-avatar {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.holographic-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
  color: white;
  text-shadow: 0 0 10px currentColor;
}

.holographic-avatar.zeus { background: linear-gradient(45deg, #ff6b00, #ffaa00); }
.holographic-avatar.thalos { background: linear-gradient(45deg, #0066ff, #00aaff); }
.holographic-avatar.justicia { background: linear-gradient(45deg, #ff0066, #ff66aa); }
.holographic-avatar.rafael { background: linear-gradient(45deg, #00ff66, #66ffaa); }
.holographic-avatar.analisis { background: linear-gradient(45deg, #6600ff, #aa66ff); }
.holographic-avatar.ia { background: linear-gradient(45deg, #ff6600, #ffaa66); }

.agent-info h3 {
  color: #00ffff;
  margin: 0 0 5px 0;
  font-size: 14px;
  text-shadow: 0 0 5px currentColor;
}

.agent-info p {
  color: #cccccc;
  margin: 0 0 10px 0;
  font-size: 12px;
}

.status-indicator {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: bold;
  text-align: center;
}

.status-indicator.active {
  background: rgba(0, 255, 0, 0.3);
  color: #00ff00;
  border: 1px solid #00ff00;
}

.status-indicator.inactive {
  background: rgba(255, 0, 0, 0.3);
  color: #ff0000;
  border: 1px solid #ff0000;
}

.command-input-panel {
  flex: 1;
  max-width: 400px;
}

.holographic-input {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.command-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 255, 255, 0.3);
  border-radius: 5px;
  padding: 10px;
  color: #00ffff;
  font-family: 'Courier New', monospace;
  backdrop-filter: blur(10px);
}

.command-input:focus {
  outline: none;
  border-color: rgba(0, 255, 255, 0.6);
  box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
}

.execute-btn {
  background: linear-gradient(45deg, #00ffff, #0088ff);
  border: none;
  border-radius: 5px;
  padding: 10px 20px;
  color: white;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
}

.execute-btn:hover {
  background: linear-gradient(45deg, #00aaff, #0066ff);
  box-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
}

.agent-response {
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(0, 255, 255, 0.3);
  border-radius: 10px;
  padding: 15px;
  backdrop-filter: blur(10px);
}

.response-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.agent-name {
  color: #00ffff;
  font-weight: bold;
  text-shadow: 0 0 5px currentColor;
}

.response-time {
  color: #888888;
  font-size: 12px;
}

.response-content p {
  color: #ffffff;
  margin: 0 0 10px 0;
  line-height: 1.4;
}

.voice-indicator {
  color: #00ff00;
  font-style: italic;
  font-size: 12px;
}

.holographic-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

.grid-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px);
  background-size: 50px 50px;
  animation: gridMove 20s linear infinite;
}

@keyframes gridMove {
  0% { transform: translate(0, 0); }
  100% { transform: translate(50px, 50px); }
}

.particles {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 20% 20%, rgba(0, 255, 255, 0.1) 0%, transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(255, 0, 255, 0.1) 0%, transparent 50%);
  animation: particleFloat 15s ease-in-out infinite;
}

@keyframes particleFloat {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  50% { transform: translate(-20px, -20px) rotate(180deg); }
}
</style>
