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

const MOVE_SPEED = 8.0

// Mouse
let isDragging = false
let previousMousePosition = { x: 0, y: 0 }
let cameraRotation = { yaw: 0, pitch: 0 }

const setupScene = () => {
  scene = new THREE.Scene()
  
  // ✅ SKYBOX ULTRA REALISTA CON SHADER
  const skyGeometry = new THREE.SphereGeometry(500, 64, 64)
  const skyMaterial = new THREE.ShaderMaterial({
    uniforms: {
      topColor: { value: new THREE.Color(0x0066cc) },  // Azul profundo
      bottomColor: { value: new THREE.Color(0xccddff) },  // Azul claro
      offset: { value: 33 },
      exponent: { value: 0.6 }
    },
    vertexShader: `
      varying vec3 vWorldPosition;
      void main() {
        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPosition.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 topColor;
      uniform vec3 bottomColor;
      uniform float offset;
      uniform float exponent;
      varying vec3 vWorldPosition;
      void main() {
        float h = normalize(vWorldPosition + offset).y;
        gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0);
      }
    `,
    side: THREE.BackSide
  })
  const sky = new THREE.Mesh(skyGeometry, skyMaterial)
  scene.add(sky)
  
  // Niebla atmosférica
  scene.fog = new THREE.FogExp2(0xccddff, 0.003)
  
  // Cámara
  camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  )
  camera.position.set(0, 2, 8)
  
  // Renderer CALIDAD ULTRA
  renderer = new THREE.WebGLRenderer({ 
    canvas: canvas.value,
    antialias: true,
    powerPreference: 'high-performance'
  })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.3
  
  // ✅ ILUMINACIÓN ULTRA REALISTA
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.8)
  scene.add(ambientLight)
  
  // Sol divino
  const sunLight = new THREE.DirectionalLight(0xfffacd, 4)
  sunLight.position.set(50, 60, 30)
  sunLight.castShadow = true
  sunLight.shadow.mapSize.width = 4096
  sunLight.shadow.mapSize.height = 4096
  sunLight.shadow.camera.far = 200
  sunLight.shadow.camera.left = -80
  sunLight.shadow.camera.right = 80
  sunLight.shadow.camera.top = 80
  sunLight.shadow.camera.bottom = -80
  sunLight.shadow.bias = -0.0001
  scene.add(sunLight)
  
  // Luz hemisférica
  const hemiLight = new THREE.HemisphereLight(0x87CEEB, 0xffffff, 1.2)
  hemiLight.position.set(0, 50, 0)
  scene.add(hemiLight)
  
  // 8 luces doradas en círculo
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2
    const pointLight = new THREE.PointLight(0xffd700, 1.5, 60)
    pointLight.position.set(
      Math.cos(angle) * 18,
      10,
      Math.sin(angle) * 18
    )
    scene.add(pointLight)
  }
  
  window.addEventListener('resize', onWindowResize)
}

const createOlymposEnvironment = () => {
  console.log('🏛️ CREANDO ENTORNO DEL OLIMPO')
  
  // SUELO - Mármol blanco con baldosas doradas REALISTA
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
  ctx.strokeStyle = 'rgba(255, 215, 0, 0.4)'
  ctx.lineWidth = 6
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
  floorTexture.repeat.set(12, 12)
  
  const floorMaterial = new THREE.MeshStandardMaterial({ 
    map: floorTexture,
    roughness: 0.15,
    metalness: 0.8,
    emissive: 0xffd700,
    emissiveIntensity: 0.12
  })
  const floor = new THREE.Mesh(floorGeometry, floorMaterial)
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  scene.add(floor)
  
  // COLUMNAS GRIEGAS MONUMENTALES
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
    // Base
    const baseGeometry = new THREE.CylinderGeometry(0.8, 1.2, 0.8, 32)
    const marbleMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.1,
      metalness: 0.5,
      emissive: 0xffffff,
      emissiveIntensity: 0.08
    })
    const base = new THREE.Mesh(baseGeometry, marbleMaterial)
    base.position.set(pos[0], 0.4, pos[2])
    base.castShadow = true
    scene.add(base)
    
    // Fuste con acanaladuras
    const shaftGroup = new THREE.Group()
    const mainShaft = new THREE.CylinderGeometry(0.65, 0.65, 14, 48)
    const shaft = new THREE.Mesh(mainShaft, marbleMaterial)
    shaftGroup.add(shaft)
    
    // Acanaladuras (16 detalles verticales)
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2
      const grooveGeometry = new THREE.BoxGeometry(0.06, 14, 0.12)
      const groove = new THREE.Mesh(grooveGeometry, marbleMaterial)
      groove.position.set(
        Math.cos(angle) * 0.68,
        0,
        Math.sin(angle) * 0.68
      )
      shaftGroup.add(groove)
    }
    
    shaftGroup.position.set(pos[0], 7.5, pos[2])
    shaftGroup.castShadow = true
    scene.add(shaftGroup)
    
    // Capitel dorado ornamentado
    const capitalGroup = new THREE.Group()
    
    const capitalMain = new THREE.CylinderGeometry(1.2, 0.75, 1.5, 32)
    const goldMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffd700,
      roughness: 0.08,
      metalness: 0.98,
      emissive: 0xffd700,
      emissiveIntensity: 0.35
    })
    const capital = new THREE.Mesh(capitalMain, goldMaterial)
    capitalGroup.add(capital)
    
    // Anillo decorativo
    const ringGeometry = new THREE.TorusGeometry(0.95, 0.1, 20, 32)
    const ring = new THREE.Mesh(ringGeometry, goldMaterial)
    ring.rotation.x = Math.PI / 2
    ring.position.y = -0.4
    capitalGroup.add(ring)
    
    capitalGroup.position.set(pos[0], 15, pos[2])
    capitalGroup.castShadow = true
    scene.add(capitalGroup)
  })
  
  // TECHO DORADO
  const ceilingGeometry = new THREE.PlaneGeometry(42, 37)
  const ceilingMaterial = new THREE.MeshStandardMaterial({
    color: 0xffd700,
    roughness: 0.15,
    metalness: 0.9,
    emissive: 0xffd700,
    emissiveIntensity: 0.2,
    side: THREE.DoubleSide
  })
  const ceiling = new THREE.Mesh(ceilingGeometry, ceilingMaterial)
  ceiling.position.set(0, 16, 0)
  ceiling.rotation.x = Math.PI / 2
  scene.add(ceiling)
  
  // MONTAÑAS AL FONDO
  for (let i = 0; i < 6; i++) {
    const mountainGeometry = new THREE.ConeGeometry(10 + Math.random() * 6, 18 + Math.random() * 8, 12)
    const mountainMaterial = new THREE.MeshStandardMaterial({
      color: 0xe5e5e5,
      roughness: 0.85
    })
    const mountain = new THREE.Mesh(mountainGeometry, mountainMaterial)
    mountain.position.set(
      (i - 2.5) * 18,
      6,
      -45 - Math.random() * 15
    )
    mountain.castShadow = true
    scene.add(mountain)
  }
  
  // NUBES FLOTANTES
  for (let i = 0; i < 20; i++) {
    const cloudGeometry = new THREE.SphereGeometry(2.5 + Math.random() * 2.5, 20, 20)
    const cloudMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.75
    })
    const cloud = new THREE.Mesh(cloudGeometry, cloudMaterial)
    cloud.position.set(
      (Math.random() - 0.5) * 70,
      10 + Math.random() * 12,
      (Math.random() - 0.5) * 70
    )
    scene.add(cloud)
  }
  
  console.log('✅ Entorno del Olimpo creado')
}

const createCharacters = () => {
  console.log('🔥 CREANDO PERSONAJES - props.agents:', props.agents)
  
  // SIEMPRE CREAR PERSONAJES POR DEFECTO
  const defaultAgents = [
    { id: 2, name: 'PERSEO', image: '/images/avatars/Perseo-avatar.jpg', status: 'Volando' },
    { id: 3, name: 'RAFAEL', image: '/images/avatars/Rafael-avatar.jpg', status: 'Vigilando' },
    { id: 4, name: 'THALOS', image: '/images/avatars/Thalos-avatar.jpg', status: 'Protegiendo' },
    { id: 5, name: 'JUSTICIA', image: '/images/avatars/Justicia-avatar.jpg', status: 'Juzgando' },
    { id: 1, name: 'ZEUS', image: '/images/avatars/Zeus-avatar.jpg', status: 'Reinando' }
  ]
  
  console.log('✅ Creando 5 personajes por defecto')
  
  defaultAgents.forEach((agent, index) => {
    console.log(`📌 Creando agente ${index + 1}/${defaultAgents.length}:`, agent.name)
    createSingleCharacter(agent, index)
  })
  
  console.log(`✅ Total de ${characters.length} personajes creados en la escena`)
}

const createSingleCharacter = (agent, index) => {
  // Posiciones de vuelo - distribuidos en círculo
  const angle = (index / 5) * Math.PI * 2
  const radius = 14
  const pos = {
    x: Math.cos(angle) * radius,
    z: Math.sin(angle) * radius,
    y: 7 + Math.random() * 5  // Volando alto (7-12m)
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
  const geometry = new THREE.PlaneGeometry(5, 6)  // GIGANTE: 5m x 6m
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    alphaTest: 0.05,
    side: THREE.DoubleSide,
    opacity: 1,
    depthWrite: false
  })
  
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(pos.x, pos.y, pos.z)
  
  // HALO DORADO BRILLANTE (como dios griego)
  const haloGeometry = new THREE.RingGeometry(3, 3.5, 48)
  const haloMaterial = new THREE.MeshBasicMaterial({
    color: 0xffd700,
    transparent: true,
    opacity: 0.4,
    side: THREE.DoubleSide
  })
  const halo = new THREE.Mesh(haloGeometry, haloMaterial)
  halo.position.set(0, 2.5, -0.1)
  mesh.add(halo)
  
  // Partículas doradas alrededor
  const particlesGeometry = new THREE.BufferGeometry()
  const particlesCount = 50
  const positions = new Float32Array(particlesCount * 3)
  
  for (let i = 0; i < particlesCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 4
    positions[i * 3 + 1] = (Math.random() - 0.5) * 6
    positions[i * 3 + 2] = (Math.random() - 0.5) * 2
  }
  
  particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  
  const particlesMaterial = new THREE.PointsMaterial({
    color: 0xffd700,
    size: 0.1,
    transparent: true,
    opacity: 0.6
  })
  
  const particles = new THREE.Points(particlesGeometry, particlesMaterial)
  mesh.add(particles)
  
  // Metadata para vuelo
  mesh.userData = {
    agent: agent,
    targetPosition: new THREE.Vector3(pos.x, pos.y, pos.z),
    flySpeed: 3,  // Velocidad de vuelo
    idleTime: 0,
    flyPhase: Math.random() * Math.PI * 2,
    floatPhase: Math.random() * Math.PI * 2,
    halo: halo,
    particles: particles,
    isFlying: true
  }
  
  scene.add(mesh)
  characters.push(mesh)
  
  console.log(`✅ ${agent.name} añadido a la escena. Total personajes:`, characters.length)
}

const setupControls = () => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  
  canvas.value.addEventListener('mousedown', onMouseDown)
  canvas.value.addEventListener('mousemove', onMouseMove)
  canvas.value.addEventListener('mouseup', onMouseUp)
  canvas.value.addEventListener('click', onCanvasClick)
}

const onKeyDown = (event) => {
  switch (event.code) {
    case 'KeyW':
    case 'ArrowUp':
      moveForward = true
      break
    case 'KeyS':
    case 'ArrowDown':
      moveBackward = true
      break
    case 'KeyA':
    case 'ArrowLeft':
      moveLeft = true
      break
    case 'KeyD':
    case 'ArrowRight':
      moveRight = true
      break
  }
}

const onKeyUp = (event) => {
  switch (event.code) {
    case 'KeyW':
    case 'ArrowUp':
      moveForward = false
      break
    case 'KeyS':
    case 'ArrowDown':
      moveBackward = false
      break
    case 'KeyA':
    case 'ArrowLeft':
      moveLeft = false
      break
    case 'KeyD':
    case 'ArrowRight':
      moveRight = false
      break
  }
}

const onMouseDown = (event) => {
  isDragging = true
  previousMousePosition = {
    x: event.clientX,
    y: event.clientY
  }
}

const onMouseMove = (event) => {
  if (!isDragging) return
  
  const deltaX = event.clientX - previousMousePosition.x
  const deltaY = event.clientY - previousMousePosition.y
  
  cameraRotation.yaw -= deltaX * 0.002
  cameraRotation.pitch -= deltaY * 0.002
  
  cameraRotation.pitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, cameraRotation.pitch))
  
  previousMousePosition = {
    x: event.clientX,
    y: event.clientY
  }
}

const onMouseUp = () => {
  isDragging = false
}

const onCanvasClick = (event) => {
  const rect = canvas.value.getBoundingClientRect()
  const mouse = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  )
  
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(mouse, camera)
  
  const intersects = raycaster.intersectObjects(characters)
  
  if (intersects.length > 0) {
    const clickedAgent = intersects[0].object.userData.agent
    console.log('🎯 Agente clickeado:', clickedAgent.name)
    emit('agentClicked', clickedAgent)
  }
}

const onWindowResize = () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

const updateCharacters = (delta) => {
  characters.forEach(mesh => {
    const data = mesh.userData
    
    data.idleTime += delta
    
    // VUELO COMO DIOSES GRIEGOS
    if (data.isFlying) {
      if (data.idleTime > 6 + Math.random() * 4) {
        // Nuevo destino de vuelo aleatorio
        const angle = Math.random() * Math.PI * 2
        const radius = 10 + Math.random() * 10
        data.targetPosition.set(
          Math.cos(angle) * radius,
          6 + Math.random() * 8,  // Vuelan alto (6-14m)
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
        data.flyPhase += delta * 2.5
        data.floatPhase += delta * 1.8
        
        // Balanceo vertical suave (flotando)
        mesh.position.y += Math.sin(data.floatPhase) * 0.02
        
        // Inclinación al volar
        const tilt = Math.sin(data.flyPhase) * 0.06
        mesh.rotation.z = tilt
        
        // Escala respiratoria
        const breathe = 1 + Math.sin(data.floatPhase * 1.5) * 0.04
        mesh.scale.set(5 * breathe, 6 * breathe, 1)
        
        // Halo pulsante
        if (data.halo) {
          data.halo.material.opacity = 0.3 + Math.abs(Math.sin(data.floatPhase)) * 0.35
          data.halo.rotation.z += delta * 0.6
        }
        
        // Partículas girando
        if (data.particles) {
          data.particles.rotation.y += delta * 0.5
          data.particles.rotation.z += delta * 0.3
        }
      } else {
        // Hover en el lugar
        data.floatPhase += delta * 2
        mesh.position.y += Math.sin(data.floatPhase) * 0.015
        mesh.scale.set(5, 6, 1)
        
        if (data.halo) {
          data.halo.material.opacity = 0.4
          data.halo.rotation.z += delta * 0.4
        }
        
        if (data.particles) {
          data.particles.rotation.y += delta * 0.3
        }
      }
    }
    
    // Siempre mirar a la cámara (billboard)
    mesh.lookAt(camera.position)
    
    // Actualizar posición en pantalla para UI
    updateAgentScreenPosition(mesh)
  })
}

const updateAgentScreenPosition = (mesh) => {
  const vector = mesh.position.clone()
  vector.project(camera)
  
  const x = (vector.x * 0.5 + 0.5) * window.innerWidth
  const y = (vector.y * -0.5 + 0.5) * window.innerHeight
  
  const existingAgent = nearbyAgents.value.find(a => a.id === mesh.userData.agent.id)
  
  if (existingAgent) {
    existingAgent.screenPosition = {
      left: `${x}px`,
      top: `${y}px`
    }
  } else {
    nearbyAgents.value.push({
      ...mesh.userData.agent,
      screenPosition: {
        left: `${x}px`,
        top: `${y}px`
      }
    })
  }
}

const updatePlayer = (delta) => {
  velocity.x -= velocity.x * 10.0 * delta
  velocity.z -= velocity.z * 10.0 * delta
  
  direction.z = Number(moveForward) - Number(moveBackward)
  direction.x = Number(moveRight) - Number(moveLeft)
  direction.normalize()
  
  if (moveForward || moveBackward) velocity.z -= direction.z * MOVE_SPEED * delta
  if (moveLeft || moveRight) velocity.x -= direction.x * MOVE_SPEED * delta
  
  // Aplicar rotación de cámara
  camera.rotation.order = 'YXZ'
  camera.rotation.y = cameraRotation.yaw
  camera.rotation.x = cameraRotation.pitch
  
  // Moverse en la dirección de la cámara
  const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion)
  forward.y = 0
  forward.normalize()
  
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion)
  right.y = 0
  right.normalize()
  
  camera.position.addScaledVector(forward, velocity.z)
  camera.position.addScaledVector(right, velocity.x)
  
  // Limitar altura
  camera.position.y = Math.max(0.5, Math.min(camera.position.y, 20))
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  
  const delta = clock.getDelta()
  
  updatePlayer(delta)
  updateCharacters(delta)
  
  renderer.render(scene, camera)
}

onMounted(() => {
  console.log('🚀 INICIANDO OLIMPO 3D')
  setupScene()
  createOlymposEnvironment()
  createCharacters()
  setupControls()
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('resize', onWindowResize)
  
  if (renderer) {
    renderer.dispose()
  }
})
</script>

<style scoped>
.olimpo-3d-world {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #000;
}

canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.world-ui {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.agent-nameplate {
  position: absolute;
  transform: translate(-50%, -120%);
  pointer-events: none;
}

.nameplate-bg {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  padding: 8px 16px;
  border-radius: 8px;
  border: 2px solid rgba(255, 215, 0, 0.6);
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
}

.agent-name-3d {
  color: #ffd700;
  font-weight: 700;
  font-size: 14px;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.8);
  margin-bottom: 2px;
}

.agent-status-3d {
  color: #fff;
  font-size: 11px;
  opacity: 0.9;
}

.controls-hint {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(15px);
  padding: 20px 30px;
  border-radius: 12px;
  border: 2px solid rgba(255, 215, 0, 0.5);
  box-shadow: 0 0 30px rgba(255, 215, 0, 0.3);
}

.controls-hint p {
  margin: 6px 0;
  color: #ffd700;
  font-size: 14px;
  font-weight: 600;
  text-shadow: 0 0 8px rgba(255, 215, 0, 0.6);
}
</style>

