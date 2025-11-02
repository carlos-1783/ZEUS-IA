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
  scene.background = new THREE.Color(0x0a1628)
  scene.fog = new THREE.Fog(0x0a1628, 10, 50)
  
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
  
  // Luces
  const ambientLight = new THREE.AmbientLight(0x404040, 1.5)
  scene.add(ambientLight)
  
  const sunLight = new THREE.DirectionalLight(0xffd700, 2)
  sunLight.position.set(10, 20, 10)
  sunLight.castShadow = true
  sunLight.shadow.camera.far = 50
  sunLight.shadow.mapSize.width = 2048
  sunLight.shadow.mapSize.height = 2048
  scene.add(sunLight)
  
  // Luz de relleno
  const fillLight = new THREE.PointLight(0x3b82f6, 1, 30)
  fillLight.position.set(-5, 5, -5)
  scene.add(fillLight)
  
  window.addEventListener('resize', onWindowResize)
}

const createOlymposEnvironment = () => {
  // Suelo del Olimpo (mármol)
  const floorGeometry = new THREE.PlaneGeometry(100, 100)
  const floorMaterial = new THREE.MeshStandardMaterial({ 
    color: 0xe8e8e8,
    roughness: 0.3,
    metalness: 0.1
  })
  const floor = new THREE.Mesh(floorGeometry, floorMaterial)
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  scene.add(floor)
  
  // Columnas griegas
  const columnPositions = [
    [-8, 0, -8], [8, 0, -8],
    [-8, 0, 8], [8, 0, 8],
    [-8, 0, 0], [8, 0, 0],
    [0, 0, -8], [0, 0, 8]
  ]
  
  columnPositions.forEach(pos => {
    const columnGeometry = new THREE.CylinderGeometry(0.5, 0.5, 6, 16)
    const columnMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xf5f5dc,
      roughness: 0.7
    })
    const column = new THREE.Mesh(columnGeometry, columnMaterial)
    column.position.set(pos[0], 3, pos[2])
    column.castShadow = true
    scene.add(column)
  })
  
  // Cielo/cúpula dorada
  const skyGeometry = new THREE.SphereGeometry(50, 32, 32, 0, Math.PI * 2, 0, Math.PI / 2)
  const skyMaterial = new THREE.MeshBasicMaterial({ 
    color: 0x1a2f4a,
    side: THREE.BackSide
  })
  const sky = new THREE.Mesh(skyGeometry, skyMaterial)
  scene.add(sky)
}

const createCharacters = () => {
  if (!props.agents) return
  
  // Posiciones iniciales de los personajes
  const spawnPositions = [
    { x: -5, z: -5 },  // PERSEO
    { x: 5, z: -5 },   // RAFAEL
    { x: -5, z: 5 },   // THALOS
    { x: 5, z: 5 }     // JUSTICIA
  ]
  
  props.agents.filter(a => a.id !== 1).forEach((agent, index) => {
    const pos = spawnPositions[index] || { x: 0, z: 0 }
    
    // Crear personaje 3D con cuerpo completo
    const character = new Character3D(agent)
    character.setPosition(pos.x, 0, pos.z)
    
    const charGroup = character.getGroup()
    
    // Metadata en el Group (no en character)
    charGroup.userData = {
      agent: agent,
      targetPosition: new THREE.Vector3(pos.x, 0, pos.z),
      walkSpeed: 0.8 + Math.random() * 0.4,
      idleTime: 0,
      character3D: character
    }
    
    scene.add(charGroup)
    characters.push(charGroup)
  })
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
  characters.forEach((charGroup) => {
    const data = charGroup.userData
    const character = data.character3D
    
    // IA simple - movimiento aleatorio
    data.idleTime += delta
    
    if (data.idleTime > 3 + Math.random() * 2) {
      // Nuevo destino aleatorio
      data.targetPosition.set(
        (Math.random() - 0.5) * 15,
        0,
        (Math.random() - 0.5) * 15
      )
      data.idleTime = 0
    }
    
    // Moverse hacia el objetivo
    const dx = data.targetPosition.x - charGroup.position.x
    const dz = data.targetPosition.z - charGroup.position.z
    const distance = Math.sqrt(dx * dx + dz * dz)
    
    if (distance > 0.5) {
      // Normalizar y aplicar velocidad
      charGroup.position.x += (dx / distance) * data.walkSpeed * delta
      charGroup.position.z += (dz / distance) * data.walkSpeed * delta
      
      // Rotar hacia dirección de movimiento
      const angle = Math.atan2(dx, dz)
      charGroup.rotation.y = angle
      
      // Animación de caminar (mover brazos y piernas)
      character.update(delta)
      character.setWalking(true)
    } else {
      character.setWalking(false)
    }
    
    // Actualizar posición en pantalla para UI
    updateAgentScreenPosition(charGroup, data.agent)
  })
}

const updateAgentScreenPosition = (charGroup, agent) => {
  // Proyectar posición 3D a 2D para el nameplate
  const headPos = charGroup.position.clone()
  headPos.y += 2 // Sobre la cabeza
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

