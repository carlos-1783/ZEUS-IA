<template>
  <div class="olimpo-3d-world" ref="container">
    <canvas ref="canvas"></canvas>
    
    <!-- UI Overlay -->
    <div class="world-ui">
      <div class="agent-nameplate" v-for="agent in nearbyAgents" :key="agent.id" 
           :style="agent.screenPosition">
        <div class="nameplate-bg">
          <div class="agent-name-3d">{{ agent.name }}</div>
          <div class="agent-status-3d">{{ agent.status }}</div>
        </div>
      </div>
      
      <!-- Controles -->
      <div class="controls-hint">
        <p>🖱️ Arrastra para mirar</p>
        <p>WASD o Flechas para moverte</p>
        <p>CLIC en agente para conversar</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { Character3D } from '@/utils/Character3D.js'

const props = defineProps({
  agents: Array
})

const emit = defineEmits(['agentClicked'])

const container = ref(null)
const canvas = ref(null)
const nearbyAgents = ref([])

let scene, camera, renderer
let characters = []
let animationId
let clock = new THREE.Clock()

// Controls
let moveForward = false, moveBackward = false, moveLeft = false, moveRight = false
let velocity = new THREE.Vector3()
let direction = new THREE.Vector3()

const MOVE_SPEED = 5.0
const LOOK_SPEED = 0.002

let mouseX = 0, mouseY = 0
let isDragging = false

onMounted(() => {
  initScene()
  createOlymposEnvironment()
  createCharacters()
  setupControls()
  animate()
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  if (renderer) renderer.dispose()
})

const initScene = () => {
  // Escena
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x87CEEB) // Cielo azul claro
  scene.fog = new THREE.Fog(0x87CEEB, 20, 60)
  
  // Cámara en primera persona
  camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  )
  camera.position.set(0, 1.6, 5) // Altura de ojos humano
  
  // Renderer
  renderer = new THREE.WebGLRenderer({ 
    canvas: canvas.value,
    antialias: true 
  })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  
  // Luces MUY BRILLANTES para ver todo
  const ambientLight = new THREE.AmbientLight(0xffffff, 2.5)
  scene.add(ambientLight)
  
  const sunLight = new THREE.DirectionalLight(0xffffff, 3)
  sunLight.position.set(10, 30, 10)
  sunLight.castShadow = true
  sunLight.shadow.camera.far = 100
  sunLight.shadow.mapSize.width = 2048
  sunLight.shadow.mapSize.height = 2048
  scene.add(sunLight)
  
  // Luces de relleno
  const fillLight1 = new THREE.PointLight(0xffd700, 2, 50)
  fillLight1.position.set(-10, 10, -10)
  scene.add(fillLight1)
  
  const fillLight2 = new THREE.PointLight(0xffd700, 2, 50)
  fillLight2.position.set(10, 10, 10)
  scene.add(fillLight2)
  
  window.addEventListener('resize', onWindowResize)
}

const createOlymposEnvironment = () => {
  // SUELO - Mármol blanco con patrón de baldosas doradas REALISTA
  const floorGeometry = new THREE.PlaneGeometry(150, 150, 30, 30)
  
  // Textura procedural de mármol
  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const ctx = canvas.getContext('2d')
  
  // Fondo blanco mármol
  ctx.fillStyle = '#f5f5f5'
  ctx.fillRect(0, 0, 512, 512)
  
  // Venas de mármol
  for (let i = 0; i < 50; i++) {
    ctx.strokeStyle = `rgba(200, 200, 200, ${Math.random() * 0.3})`
    ctx.lineWidth = Math.random() * 3
    ctx.beginPath()
    ctx.moveTo(Math.random() * 512, Math.random() * 512)
    ctx.bezierCurveTo(
      Math.random() * 512, Math.random() * 512,
      Math.random() * 512, Math.random() * 512,
      Math.random() * 512, Math.random() * 512
    )
    ctx.stroke()
  }
  
  // Baldosas doradas
  ctx.strokeStyle = 'rgba(255, 215, 0, 0.3)'
  ctx.lineWidth = 4
  for (let x = 0; x < 512; x += 64) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, 512)
    ctx.stroke()
  }
  for (let y = 0; y < 512; y += 64) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(512, y)
    ctx.stroke()
  }
  
  const floorTexture = new THREE.CanvasTexture(canvas)
  floorTexture.wrapS = THREE.RepeatWrapping
  floorTexture.wrapT = THREE.RepeatWrapping
  floorTexture.repeat.set(10, 10)
  
  const floorMaterial = new THREE.MeshStandardMaterial({ 
    map: floorTexture,
    roughness: 0.2,
    metalness: 0.7,
    emissive: 0xffd700,
    emissiveIntensity: 0.1
  })
  const floor = new THREE.Mesh(floorGeometry, floorMaterial)
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  scene.add(floor)
  
  // COLUMNAS GRIEGAS MASIVAS (como templo real)
  const columnPositions = [
    // Fila frontal
    [-12, 0, -15], [-6, 0, -15], [0, 0, -15], [6, 0, -15], [12, 0, -15],
    // Fila trasera
    [-12, 0, 15], [-6, 0, 15], [0, 0, 15], [6, 0, 15], [12, 0, 15],
    // Laterales
    [-18, 0, -8], [-18, 0, 0], [-18, 0, 8],
    [18, 0, -8], [18, 0, 0], [18, 0, 8]
  ]
  
  columnPositions.forEach(pos => {
    // Base de columna DETALLADA
    const baseGeometry = new THREE.CylinderGeometry(0.8, 1.2, 0.8, 24)
    const marbleMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.15,
      metalness: 0.4,
      emissive: 0xffffff,
      emissiveIntensity: 0.05
    })
    const base = new THREE.Mesh(baseGeometry, marbleMaterial)
    base.position.set(pos[0], 0.4, pos[2])
    base.castShadow = true
    scene.add(base)
    
    // Fuste (columna principal) con ACANALADURAS
    const shaftGroup = new THREE.Group()
    const mainShaft = new THREE.CylinderGeometry(0.65, 0.65, 12, 32)
    const shaft = new THREE.Mesh(mainShaft, marbleMaterial)
    shaftGroup.add(shaft)
    
    // Acanaladuras (detalles verticales)
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2
      const grooveGeometry = new THREE.BoxGeometry(0.05, 12, 0.1)
      const groove = new THREE.Mesh(grooveGeometry, marbleMaterial)
      groove.position.set(
        Math.cos(angle) * 0.68,
        0,
        Math.sin(angle) * 0.68
      )
      shaftGroup.add(groove)
    }
    
    shaftGroup.position.set(pos[0], 6.5, pos[2])
    shaftGroup.castShadow = true
    scene.add(shaftGroup)
    
    // Capitel dorado ORNAMENTADO
    const capitalGroup = new THREE.Group()
    
    const capitalMain = new THREE.CylinderGeometry(1.1, 0.75, 1.2, 24)
    const goldMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffd700,
      roughness: 0.1,
      metalness: 0.95,
      emissive: 0xffd700,
      emissiveIntensity: 0.3
    })
    const capital = new THREE.Mesh(capitalMain, goldMaterial)
    capitalGroup.add(capital)
    
    // Decoración del capitel
    const ringGeometry = new THREE.TorusGeometry(0.9, 0.08, 16, 24)
    const ring = new THREE.Mesh(ringGeometry, goldMaterial)
    ring.rotation.x = Math.PI / 2
    ring.position.y = -0.3
    capitalGroup.add(ring)
    
    capitalGroup.position.set(pos[0], 13, pos[2])
    capitalGroup.castShadow = true
    scene.add(capitalGroup)
  })
  
  // TECHO DORADO (entre columnas)
  const ceilingGeometry = new THREE.PlaneGeometry(40, 35)
  const ceilingMaterial = new THREE.MeshStandardMaterial({
    color: 0xffd700,
    roughness: 0.2,
    metalness: 0.8,
    emissive: 0xffd700,
    emissiveIntensity: 0.15,
    side: THREE.DoubleSide
  })
  const ceiling = new THREE.Mesh(ceilingGeometry, ceilingMaterial)
  ceiling.position.set(0, 12, 0)
  ceiling.rotation.x = Math.PI / 2
  scene.add(ceiling)
  
  // MONTAÑAS AL FONDO
  for (let i = 0; i < 5; i++) {
    const mountainGeometry = new THREE.ConeGeometry(8 + Math.random() * 4, 15 + Math.random() * 5, 8)
    const mountainMaterial = new THREE.MeshStandardMaterial({
      color: 0xe0e0e0,
      roughness: 0.8
    })
    const mountain = new THREE.Mesh(mountainGeometry, mountainMaterial)
    mountain.position.set(
      (i - 2) * 15,
      5,
      -40 - Math.random() * 10
    )
    scene.add(mountain)
  }
  
  // NUBES FLOTANTES
  for (let i = 0; i < 15; i++) {
    const cloudGeometry = new THREE.SphereGeometry(2 + Math.random() * 2, 16, 16)
    const cloudMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.7
    })
    const cloud = new THREE.Mesh(cloudGeometry, cloudMaterial)
    cloud.position.set(
      (Math.random() - 0.5) * 60,
      8 + Math.random() * 8,
      (Math.random() - 0.5) * 60
    )
    scene.add(cloud)
  }
  
  // ESTATUAS GRIEGAS (decoración)
  const statuePositions = [[-10, 0, -10], [10, 0, -10]]
  statuePositions.forEach(pos => {
    const statueGeometry = new THREE.CylinderGeometry(0.3, 0.4, 2, 16)
    const statueMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.4,
      metalness: 0.1
    })
    const statue = new THREE.Mesh(statueGeometry, statueMaterial)
    statue.position.set(pos[0], 1, pos[2])
    statue.castShadow = true
    scene.add(statue)
  })
}

const createCharacters = () => {
  console.log('🔥 CREANDO PERSONAJES - props.agents:', props.agents)
  
  if (!props.agents || props.agents.length === 0) {
    console.error('❌ NO HAY AGENTS - CREANDO DEFAULTS')
    // CREAR PERSONAJES POR DEFECTO SI NO HAY PROPS
    const defaultAgents = [
      { id: 2, name: 'PERSEO', image: '/images/avatars/Perseo-avatar.jpg' },
      { id: 3, name: 'RAFAEL', image: '/images/avatars/Rafael-avatar.jpg' },
      { id: 4, name: 'THALOS', image: '/images/avatars/Thalos-avatar.jpg' },
      { id: 5, name: 'JUSTICIA', image: '/images/avatars/Justicia-avatar.jpg' },
      { id: 1, name: 'ZEUS', image: '/images/avatars/Zeus-avatar.jpg' }
    ]
    
    defaultAgents.forEach((agent, index) => {
      createSingleCharacter(agent, index)
    })
    return
  }
  
  // Usar agents reales
  props.agents.forEach((agent, index) => {
    createSingleCharacter(agent, index)
  })
}

const createSingleCharacter = (agent, index) => {
  // Posiciones de vuelo - distribuidos en círculo
  const angle = (index / 5) * Math.PI * 2
  const radius = 12
  const pos = {
    x: Math.cos(angle) * radius,
    z: Math.sin(angle) * radius,
    y: 6 + Math.random() * 4  // Volando alto
  }
  
  console.log(`✅ Creando ${agent.name} en posición:`, pos)
  
  // Cargar imagen del avatar
  const textureLoader = new THREE.TextureLoader()
  textureLoader.crossOrigin = 'anonymous'
  
  const texture = textureLoader.load(
    agent.image || '/images/avatars/Perseo-avatar.jpg',
    (tex) => {
      console.log(`✅ Textura cargada para ${agent.name}`)
    },
    undefined,
    (err) => {
      console.error(`❌ Error cargando textura para ${agent.name}:`, err)
    }
  )
  
  // BILLBOARD GIGANTE Y BRILLANTE
  const geometry = new THREE.PlaneGeometry(4, 5)  // GIGANTE: 4m x 5m
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    alphaTest: 0.1,
    side: THREE.DoubleSide,
    opacity: 1,
    depthWrite: false  // Para que se vea siempre
  })
  
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(pos.x, pos.y, pos.z)
  
  // HALO DORADO ALREDEDOR (como dios griego)
  const haloGeometry = new THREE.RingGeometry(2.5, 3, 32)
  const haloMaterial = new THREE.MeshBasicMaterial({
    color: 0xffd700,
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide
  })
  const halo = new THREE.Mesh(haloGeometry, haloMaterial)
  halo.position.set(0, 2, -0.1)
  mesh.add(halo)
  
  // Metadata para vuelo
  mesh.userData = {
    agent: agent,
    targetPosition: new THREE.Vector3(pos.x, pos.y, pos.z),
    flySpeed: 2.5,  // Velocidad de vuelo
    idleTime: 0,
    flyPhase: Math.random() * Math.PI * 2,
    floatPhase: Math.random() * Math.PI * 2,
    halo: halo,
    isFlying: true
  }
  
  scene.add(mesh)
  characters.push(mesh)
  
  console.log(`✅ ${agent.name} añadido a la escena. Total personajes:`, characters.length)
}

const setupControls = () => {
  // Teclado
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  
  // Mouse para mirar
  canvas.value.addEventListener('mousedown', (e) => {
    isDragging = true
  })
  
  window.addEventListener('mousemove', (e) => {
    if (isDragging) {
      mouseX += e.movementX * LOOK_SPEED
      mouseY += e.movementY * LOOK_SPEED
      mouseY = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, mouseY))
    }
  })
  
  window.addEventListener('mouseup', () => {
    isDragging = false
  })
  
  // Click en personaje
  canvas.value.addEventListener('click', onCanvasClick)
}

const onKeyDown = (event) => {
  switch (event.code) {
    case 'ArrowUp':
    case 'KeyW':
      moveForward = true
      break
    case 'ArrowLeft':
    case 'KeyA':
      moveLeft = true
      break
    case 'ArrowDown':
    case 'KeyS':
      moveBackward = true
      break
    case 'ArrowRight':
    case 'KeyD':
      moveRight = true
      break
  }
}

const onKeyUp = (event) => {
  switch (event.code) {
    case 'ArrowUp':
    case 'KeyW':
      moveForward = false
      break
    case 'ArrowLeft':
    case 'KeyA':
      moveLeft = false
      break
    case 'ArrowDown':
    case 'KeyS':
      moveBackward = false
      break
    case 'ArrowRight':
    case 'KeyD':
      moveRight = false
      break
  }
}

const onCanvasClick = (event) => {
  // Raycast para detectar click en personaje
  const mouse = new THREE.Vector2()
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1
  
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(mouse, camera)
  
  const intersects = raycaster.intersectObjects(characters)
  if (intersects.length > 0) {
    const character = intersects[0].object
    emit('agentClicked', character.userData.agent)
  }
}

const onWindowResize = () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

const updateCharacters = (delta) => {
  characters.forEach((mesh) => {
    const data = mesh.userData
    
    // IA simple - movimiento aleatorio
    data.idleTime += delta
    
    // VUELO COMO DIOSES GRIEGOS
    if (data.isFlying) {
      if (data.idleTime > 6 + Math.random() * 4) {
        // Nuevo destino de vuelo aleatorio
        const angle = Math.random() * Math.PI * 2
        const radius = 8 + Math.random() * 8
        data.targetPosition.set(
          Math.cos(angle) * radius,
          5 + Math.random() * 6,  // Vuelan alto
          Math.sin(angle) * radius
        )
        data.idleTime = 0
      }
      
      // Moverse suavemente hacia el objetivo
      const dx = data.targetPosition.x - mesh.position.x
      const dy = data.targetPosition.y - mesh.position.y
      const dz = data.targetPosition.z - mesh.position.z
      const distance = Math.sqrt(dx * dx + dy * dy + dz * dz)
      
      if (distance > 1.5) {
        // Vuelo suave
        mesh.position.x += (dx / distance) * data.flySpeed * delta
        mesh.position.y += (dy / distance) * data.flySpeed * delta
        mesh.position.z += (dz / distance) * data.flySpeed * delta
        
        // Animación de vuelo - ondulación elegante
        data.flyPhase += delta * 3
        data.floatPhase += delta * 2
        
        // Balanceo vertical suave (flotando)
        mesh.position.y += Math.sin(data.floatPhase) * 0.015
        
        // Inclinación al volar
        const tilt = Math.sin(data.flyPhase) * 0.05
        mesh.rotation.z = tilt
        
        // Escala respiratoria
        const breathe = 1 + Math.sin(data.floatPhase * 1.5) * 0.03
        mesh.scale.set(4 * breathe, 5 * breathe, 1)
        
        // Halo pulsante
        if (data.halo) {
          data.halo.material.opacity = 0.2 + Math.abs(Math.sin(data.floatPhase)) * 0.3
          data.halo.rotation.z += delta * 0.5
        }
      } else {
        // Hover en el lugar
        data.floatPhase += delta * 2
        mesh.position.y += Math.sin(data.floatPhase) * 0.01
        mesh.scale.set(4, 5, 1)
        
        if (data.halo) {
          data.halo.material.opacity = 0.3
          data.halo.rotation.z += delta * 0.3
        }
      }
    }
    
    // Siempre mirar a la cámara (billboard)
    mesh.lookAt(camera.position)
    
    // Actualizar posición en pantalla para UI
    updateAgentScreenPosition(mesh, data.agent)
  })
}

const updateAgentScreenPosition = (mesh, agent) => {
  // Proyectar posición 3D a 2D para el nameplate
  const headPos = mesh.position.clone()
  headPos.y += 1.8 // Sobre la cabeza
  headPos.project(camera)
  
  const x = (headPos.x * 0.5 + 0.5) * window.innerWidth
  const y = (headPos.y * -0.5 + 0.5) * window.innerHeight
  
  // Solo mostrar si está delante de la cámara
  if (headPos.z < 1) {
    const existing = nearbyAgents.value.find(a => a.id === agent.id)
    const screenPos = {
      left: `${x}px`,
      top: `${y}px`
    }
    
    if (existing) {
      existing.screenPosition = screenPos
    } else {
      nearbyAgents.value.push({
        ...agent,
        screenPosition: screenPos
      })
    }
  } else {
    // Quitar si está detrás
    nearbyAgents.value = nearbyAgents.value.filter(a => a.id !== agent.id)
  }
}

const updatePlayer = (delta) => {
  // Movimiento del jugador
  velocity.x -= velocity.x * 10.0 * delta
  velocity.z -= velocity.z * 10.0 * delta
  
  direction.z = Number(moveForward) - Number(moveBackward)
  direction.x = Number(moveRight) - Number(moveLeft)
  direction.normalize()
  
  if (moveForward || moveBackward) velocity.z -= direction.z * MOVE_SPEED * delta
  if (moveLeft || moveRight) velocity.x -= direction.x * MOVE_SPEED * delta
  
  // Aplicar rotación de cámara
  camera.rotation.y = mouseX
  camera.rotation.x = mouseY
  
  // Mover cámara
  const forward = new THREE.Vector3(0, 0, -1)
  forward.applyQuaternion(camera.quaternion)
  forward.y = 0
  forward.normalize()
  
  const right = new THREE.Vector3(1, 0, 0)
  right.applyQuaternion(camera.quaternion)
  right.y = 0
  right.normalize()
  
  camera.position.addScaledVector(forward, velocity.z)
  camera.position.addScaledVector(right, velocity.x)
  
  // Límites del Olimpo
  camera.position.x = Math.max(-45, Math.min(45, camera.position.x))
  camera.position.z = Math.max(-45, Math.min(45, camera.position.z))
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  
  const delta = clock.getDelta()
  
  updatePlayer(delta)
  updateCharacters(delta)
  
  renderer.render(scene, camera)
}
</script>

<style scoped>
.olimpo-3d-world {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: #000;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
}

canvas:active {
  cursor: grabbing;
}

.world-ui {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.agent-nameplate {
  position: absolute;
  transform: translate(-50%, -100%);
  pointer-events: all;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nameplate-bg {
  background: rgba(10, 35, 66, 0.9);
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 215, 0, 0.6);
  border-radius: 15px;
  padding: 8px 16px;
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
}

.agent-nameplate:hover .nameplate-bg {
  border-color: rgba(255, 215, 0, 1);
  box-shadow: 0 0 30px rgba(255, 215, 0, 0.8);
  transform: scale(1.1);
}

.agent-name-3d {
  font-size: 1.2rem;
  font-weight: bold;
  color: #ffd700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.8);
}

.agent-status-3d {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.8);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.controls-hint {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(10, 35, 66, 0.95);
  backdrop-filter: blur(15px);
  border: 2px solid rgba(59, 130, 246, 0.5);
  border-radius: 20px;
  padding: 20px 40px;
  color: #fff;
  text-align: center;
  pointer-events: none;
}

.controls-hint p {
  margin: 5px 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.9);
}
</style>

