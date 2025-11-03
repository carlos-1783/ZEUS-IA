<template>
  <div class="dashboard-profesional">
    <!-- Sidebar Oscura -->
    <aside class="sidebar-dark">
      <div class="logo-section">
        <h1>⚡ ZEUS-IA</h1>
        <p class="subtitle">Enterprise AI Platform</p>
      </div>

      <nav class="nav-menu">
        <button class="nav-item active">
          <span class="icon">🏛️</span>
          <span>Dashboard</span>
        </button>
        <button class="nav-item">
          <span class="icon">📊</span>
          <span>Analytics</span>
        </button>
        <button class="nav-item">
          <span class="icon">⚙️</span>
          <span>Settings</span>
        </button>
      </nav>

      <div class="metrics-mini">
        <div class="metric-item">
          <div class="metric-value">98%</div>
          <div class="metric-label">System Health</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ agentsData.length }}</div>
          <div class="metric-label">Active Agents</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Header -->
      <header class="dashboard-header">
        <div class="header-left">
          <h2>AI Agents Control Center</h2>
          <p class="breadcrumb">Dashboard / Agents Overview</p>
        </div>
        <div class="header-right">
          <div class="status-badge online">● System Online</div>
        </div>
      </header>

      <!-- Agents Grid -->
      <section class="agents-grid">
        <div 
          v-for="agent in agentsData" 
          :key="agent.name"
          class="agent-card"
          :class="{ 'has-avatar': agent.hasGLB }"
          @click="selectAgent(agent)"
        >
          <!-- Avatar 3D Container -->
          <div class="avatar-container" :ref="el => setAvatarRef(agent.name, el)">
            <div class="avatar-loader" v-if="!agent.loaded">
              <div class="spinner"></div>
            </div>
          </div>

          <!-- Agent Info -->
          <div class="agent-info">
            <h3 class="agent-name">{{ agent.name }}</h3>
            <p class="agent-role">{{ agent.role }}</p>
            
            <div class="agent-stats">
              <div class="stat">
                <span class="stat-label">Status</span>
                <span class="stat-value status-active">Active</span>
              </div>
              <div class="stat">
                <span class="stat-label">Load</span>
                <span class="stat-value">{{ agent.load }}%</span>
              </div>
            </div>

            <button class="btn-interact" @click.stop="chatWith(agent)">
              <span>💬</span>
              Interact
            </button>
          </div>
        </div>
      </section>

      <!-- Chat Panel (si hay agente seleccionado) -->
      <div v-if="selectedAgent" class="chat-overlay" @click.self="selectedAgent = null">
        <div class="chat-panel">
          <div class="chat-header">
            <div class="chat-agent-info">
              <div class="chat-avatar-mini" :ref="el => setChatAvatarRef(el)"></div>
              <div>
                <h4>{{ selectedAgent.name }}</h4>
                <p>{{ selectedAgent.role }}</p>
              </div>
            </div>
            <button class="btn-close" @click="selectedAgent = null">✕</button>
          </div>

          <div class="chat-messages">
            <div class="message agent-message">
              <p>Hola, soy {{ selectedAgent.name }}. ¿En qué puedo ayudarte?</p>
            </div>
          </div>

          <div class="chat-input">
            <input type="text" placeholder="Escribe tu mensaje..." />
            <button class="btn-send">Enviar</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

const props = defineProps({
  agents: Array
})

const emit = defineEmits(['agentClicked'])

const selectedAgent = ref(null)
const avatarRefs = ref({})
const avatarScenes = ref({})

const agentsData = ref([
  {
    name: 'ZEUS CORE',
    role: 'Supreme Orchestrator',
    glbUrl: 'https://models.readyplayer.me/69079ecd48062250a4c853f4.glb',
    hasGLB: true,
    load: 45,
    loaded: false
  },
  {
    name: 'PERSEO',
    role: 'Growth Strategist',
    glbUrl: 'https://models.readyplayer.me/69079ce412a04a26c26798b2.glb',
    hasGLB: true,
    load: 62,
    loaded: false
  },
  {
    name: 'RAFAEL',
    role: 'Fiscal Guardian',
    glbUrl: null,
    hasGLB: false,
    load: 38,
    loaded: true,
    color: 0x10b981
  },
  {
    name: 'THALOS',
    role: 'Cybersecurity Defender',
    glbUrl: null,
    hasGLB: false,
    load: 71,
    loaded: true,
    color: 0x6366f1
  },
  {
    name: 'JUSTICIA',
    role: 'Legal & GDPR Advisor',
    glbUrl: null,
    hasGLB: false,
    load: 29,
    loaded: true,
    color: 0xec4899
  }
])

const setAvatarRef = (name, el) => {
  if (el) avatarRefs.value[name] = el
}

const setChatAvatarRef = (el) => {
  if (el) avatarRefs.value['chat'] = el
}

const selectAgent = (agent) => {
  selectedAgent.value = agent
  emit('agentClicked', agent)
}

const chatWith = (agent) => {
  selectedAgent.value = agent
  emit('agentClicked', agent)
}

const loadAvatars = () => {
  const loader = new GLTFLoader()

  agentsData.value.forEach(agent => {
    const container = avatarRefs.value[agent.name]
    if (!container) return

    // Crear escena Three.js para este avatar
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 1000)
    camera.position.set(0, 1.6, 2.5)
    camera.lookAt(0, 1, 0)

    const renderer = new THREE.WebGLRenderer({ 
      alpha: true, 
      antialias: true 
    })
    renderer.setSize(250, 250)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    renderer.outputColorSpace = THREE.SRGBColorSpace
    container.appendChild(renderer.domElement)

    // Luces
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.2)
    keyLight.position.set(2, 3, 2)
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight(0x4a90e2, 0.5)
    fillLight.position.set(-2, 1, -1)
    scene.add(fillLight)

    if (agent.hasGLB && agent.glbUrl) {
      // Cargar GLB
      loader.load(
        agent.glbUrl,
        (gltf) => {
          const model = gltf.scene
          
          // Centrar y escalar
          const box = new THREE.Box3().setFromObject(model)
          const center = box.getCenter(new THREE.Vector3())
          const size = box.getSize(new THREE.Vector3())
          
          const maxDim = Math.max(size.x, size.y, size.z)
          const scale = 1.8 / maxDim
          model.scale.setScalar(scale)
          
          model.position.x = -center.x * scale
          model.position.y = -center.y * scale
          model.position.z = -center.z * scale

          scene.add(model)
          agent.loaded = true

          // Animación de rotación suave
          const animate = () => {
            model.rotation.y += 0.005
            renderer.render(scene, camera)
            requestAnimationFrame(animate)
          }
          animate()
        },
        undefined,
        (error) => {
          console.error(`Error cargando ${agent.name}:`, error)
          createPlaceholder(scene, agent.color || 0x3b82f6)
          agent.loaded = true
          renderer.render(scene, camera)
        }
      )
    } else {
      // Placeholder para agentes sin GLB
      createPlaceholder(scene, agent.color)
      agent.loaded = true
      const animate = () => {
        renderer.render(scene, camera)
        requestAnimationFrame(animate)
      }
      animate()
    }

    avatarScenes.value[agent.name] = { scene, renderer, camera }
  })
}

const createPlaceholder = (scene, color) => {
  const geometry = new THREE.SphereGeometry(0.8, 32, 32)
  const material = new THREE.MeshStandardMaterial({
    color: color,
    roughness: 0.3,
    metalness: 0.7,
    emissive: color,
    emissiveIntensity: 0.2
  })
  const sphere = new THREE.Mesh(geometry, material)
  sphere.position.y = 1
  scene.add(sphere)
}

onMounted(() => {
  setTimeout(loadAvatars, 100)
})

onUnmounted(() => {
  Object.values(avatarScenes.value).forEach(({ renderer }) => {
    renderer.dispose()
  })
})
</script>

<style scoped>
.dashboard-profesional {
  display: flex;
  height: 100vh;
  background: #0a0e1a;
  color: #fff;
  font-family: 'Inter', -apple-system, sans-serif;
}

/* SIDEBAR */
.sidebar-dark {
  width: 280px;
  background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
}

.logo-section {
  margin-bottom: 48px;
}

.logo-section h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin: 4px 0 0;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.icon {
  font-size: 18px;
}

.metrics-mini {
  display: flex;
  gap: 16px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.metric-item {
  flex: 1;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #3b82f6;
}

.metric-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

/* MAIN CONTENT */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header-left h2 {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
}

.breadcrumb {
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  margin: 4px 0 0;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.online {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

/* AGENTS GRID */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
}

.agent-card {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s;
}

.agent-card:hover {
  transform: translateY(-4px);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 8px 32px rgba(59, 130, 246, 0.2);
}

.avatar-container {
  width: 250px;
  height: 250px;
  margin: 0 auto 20px;
  border-radius: 50%;
  overflow: hidden;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-loader {
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.agent-info {
  text-align: center;
}

.agent-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #fff;
}

.agent-role {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  margin: 0 0 20px;
}

.agent-stats {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 20px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
}

.status-active {
  color: #10b981;
}

.btn-interact {
  padding: 10px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.btn-interact:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.4);
}

/* CHAT OVERLAY */
.chat-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.chat-panel {
  width: 600px;
  max-height: 80vh;
  background: #1a1f2e;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-agent-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.chat-avatar-mini {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.2);
}

.chat-agent-info h4 {
  margin: 0;
  font-size: 18px;
}

.chat-agent-info p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
}

.btn-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.chat-messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.message {
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 12px;
  max-width: 80%;
}

.agent-message {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.chat-input {
  display: flex;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-input input {
  flex: 1;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
}

.chat-input input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.btn-send {
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
</style>

