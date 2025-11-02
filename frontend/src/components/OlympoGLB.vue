<template>
  <div class="olimpo-glb-world" ref="container">
    <canvas ref="canvas"></canvas>
    
    <!-- UI Overlay -->
    <div class="world-ui">
      <div class="agent-nameplate" v-for="agent in nearbyAgents" :key="agent.id" 
           :style="agent.screenPosition">
        <div class="nameplate-bg">
          <div class="agent-name-3d">{{ agent.name }}</div>
          <div class="agent-status-3d">{{ agent.description }}</div>
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
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

const props = defineProps({
  agents: Array
})

const emit = defineEmits(['agentClicked'])

const container = ref(null)
const canvas = ref(null)
const nearbyAgents = ref([])

let scene, camera, renderer
let models = []
let animationId
let clock = new THREE.Clock()
let raycaster = new THREE.Raycaster()
let mouse = new THREE.Vector2()

// Controls
let moveForward = false, moveBackward = false, moveLeft = false, moveRight = false
let velocity = new THREE.Vector3()
let direction = new THREE.Vector3()

const MOVE_SPEED = 8.0

// Mouse
let isDragging = false
let previousMousePosition = { x: 0, y: 0 }
let cameraRotation = { yaw: 0, pitch: 0 }

// URLs de Ready Player Me
const avatarURLs = {
  'ZEUS CORE': 'https://models.readyplayer.me/69079ecd48062250a4c853f4.glb',
  'PERSEO': 'https://models.readyplayer.me/69079ce412a04a26c26798b2.glb',
  'RAFAEL': null, // Usar placeholder
  'THALOS': null, // Usar placeholder
  'JUSTICIA': null // Usar placeholder
}

const setupScene = () => {
  scene = new THREE.Scene()
  
  // Skybox realista
  const skyGeometry = new THREE.SphereGeometry(500, 64, 64)
  const skyMaterial = new THREE.ShaderMaterial({
    uniforms: {
      topColor: { value: new THREE.Color(0x0066cc) },
      bottomColor: { value: new THREE.Color(0xccddff) },
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
  
  scene.fog = new THREE.FogExp2(0xccddff, 0.003)
  
  // Cámara
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
  camera.position.set(0, 1.6, 10)
  
  // Renderer
  renderer = new THREE.WebGLRenderer({ 
    canvas: canvas.value,
    antialias: true,
    alpha: false
  })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  renderer.outputColorSpace = THREE.SRGBColorSpace
  
  // Luces
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)
  
  const sunLight = new THREE.DirectionalLight(0xfff8dc, 1.5)
  sunLight.position.set(50, 50, 30)
  sunLight.castShadow = true
  sunLight.shadow.camera.left = -50
  sunLight.shadow.camera.right = 50
  sunLight.shadow.camera.top = 50
  sunLight.shadow.camera.bottom = -50
  sunLight.shadow.mapSize.width = 2048
  sunLight.shadow.mapSize.height = 2048
  scene.add(sunLight)
  
  const fillLight = new THREE.DirectionalLight(0xaaccff, 0.4)
  fillLight.position.set(-30, 20, -30)
  scene.add(fillLight)
  
  // Suelo
  const groundGeometry = new THREE.PlaneGeometry(200, 200, 100, 100)
  const groundMaterial = new THREE.MeshStandardMaterial({ 
    color: 0xe8e8e8,
    roughness: 0.8,
    metalness: 0.2
  })
  const ground = new THREE.Mesh(groundGeometry, groundMaterial)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)
  
  // Montañas de fondo
  createMountains()
  
  // Cargar avatares GLB
  loadGLBAvatars()
}

const createMountains = () => {
  const mountainPositions = [
    { x: -60, z: -80, scale: 1.5 },
    { x: 30, z: -90, scale: 1.8 },
    { x: 80, z: -70, scale: 1.3 },
    { x: -40, z: -100, scale: 2.0 }
  ]
  
  mountainPositions.forEach(pos => {
    const geometry = new THREE.ConeGeometry(20 * pos.scale, 40 * pos.scale, 8)
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xf0f0f0,
      roughness: 0.9,
      metalness: 0.1
    })
    const mountain = new THREE.Mesh(geometry, material)
    mountain.position.set(pos.x, 20 * pos.scale, pos.z)
    mountain.receiveShadow = true
    mountain.castShadow = true
    scene.add(mountain)
  })
}

const loadGLBAvatars = () => {
  const loader = new GLTFLoader()
  
  const positions = [
    { x: -15, z: 0 },   // JUSTICIA
    { x: -5, z: -2 },   // RAFAEL
    { x: 0, z: 0 },     // ZEUS CORE (centro)
    { x: 5, z: -2 },    // PERSEO
    { x: 15, z: 0 }     // THALOS
  ]
  
  props.agents.forEach((agent, index) => {
    const url = avatarURLs[agent.name]
    
    if (url) {
      // Cargar GLB de Ready Player Me
      loader.load(
        url,
        (gltf) => {
          const model = gltf.scene
          model.position.set(positions[index].x, 0, positions[index].z)
          model.scale.setScalar(1.0)
          
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true
              child.receiveShadow = true
            }
          })
          
          scene.add(model)
          models.push({ model, agent, mixer: new THREE.AnimationMixer(model) })
          
          // Reproducir animaciones si existen
          if (gltf.animations && gltf.animations.length > 0) {
            const mixer = models[models.length - 1].mixer
            gltf.animations.forEach(clip => {
              mixer.clipAction(clip).play()
            })
          }
          
          console.log(`✅ Cargado avatar GLB: ${agent.name}`)
        },
        (progress) => {
          console.log(`⏳ Cargando ${agent.name}: ${Math.floor((progress.loaded / progress.total) * 100)}%`)
        },
        (error) => {
          console.warn(`⚠️ No se pudo cargar GLB de ${agent.name}, usando placeholder`)
          createPlaceholderAvatar(agent, positions[index])
        }
      )
    } else {
      // Placeholder mientras obtienes el GLB
      createPlaceholderAvatar(agent, positions[index])
    }
  })
}

const createPlaceholderAvatar = (agent, position) => {
  const group = new THREE.Group()
  
  // Cuerpo (cápsula)
  const bodyGeometry = new THREE.CapsuleGeometry(0.5, 1.5, 8, 16)
  const bodyMaterial = new THREE.MeshStandardMaterial({ 
    color: agent.id === 1 ? 0xFFD700 : // ZEUS oro
           agent.id === 2 ? 0x3b82f6 : // PERSEO azul
           agent.id === 3 ? 0x10b981 : // RAFAEL verde
           agent.id === 4 ? 0x6366f1 : // THALOS morado
           0xec4899,                    // JUSTICIA rosa
    roughness: 0.6,
    metalness: 0.4
  })
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial)
  body.position.y = 1
  body.castShadow = true
  body.receiveShadow = true
  group.add(body)
  
  // Halo
  const haloGeometry = new THREE.TorusGeometry(0.4, 0.05, 16, 32)
  const haloMaterial = new THREE.MeshStandardMaterial({ 
    color: 0xFFD700,
    emissive: 0xFFD700,
    emissiveIntensity: 0.8,
    roughness: 0.2,
    metalness: 0.8
  })
  const halo = new THREE.Mesh(haloGeometry, haloMaterial)
  halo.position.y = 2.5
  halo.rotation.x = Math.PI / 2
  group.add(halo)
  
  group.position.set(position.x, 0, position.z)
  scene.add(group)
  models.push({ model: group, agent, isPlaceholder: true })
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  
  const delta = clock.getDelta()
  
  // Actualizar mixers de animaciones GLB
  models.forEach(({ mixer }) => {
    if (mixer) mixer.update(delta)
  })
  
  // Movimiento de cámara
  direction.z = Number(moveForward) - Number(moveBackward)
  direction.x = Number(moveRight) - Number(moveLeft)
  direction.normalize()
  
  if (moveForward || moveBackward) {
    const forward = new THREE.Vector3(0, 0, -1)
    forward.applyAxisAngle(new THREE.Vector3(0, 1, 0), cameraRotation.yaw)
    camera.position.addScaledVector(forward, direction.z * MOVE_SPEED * delta)
  }
  if (moveLeft || moveRight) {
    const right = new THREE.Vector3(1, 0, 0)
    right.applyAxisAngle(new THREE.Vector3(0, 1, 0), cameraRotation.yaw)
    camera.position.addScaledVector(right, direction.x * MOVE_SPEED * delta)
  }
  
  // Rotación de cámara
  camera.rotation.order = 'YXZ'
  camera.rotation.y = cameraRotation.yaw
  camera.rotation.x = cameraRotation.pitch
  
  // Actualizar nameplates
  updateNameplates()
  
  renderer.render(scene, camera)
}

const updateNameplates = () => {
  nearbyAgents.value = models.map(({ model, agent }) => {
    const pos = new THREE.Vector3()
    if (model.isGroup) {
      pos.copy(model.position)
    } else {
      model.getWorldPosition(pos)
    }
    pos.y += 3
    
    const screenPos = pos.clone().project(camera)
    const x = (screenPos.x * 0.5 + 0.5) * window.innerWidth
    const y = (-screenPos.y * 0.5 + 0.5) * window.innerHeight
    
    const distance = camera.position.distanceTo(model.position)
    
    return {
      ...agent,
      screenPosition: {
        left: `${x}px`,
        top: `${y}px`,
        opacity: distance < 20 ? 1 : 0
      }
    }
  })
}

// Event Handlers
const onKeyDown = (e) => {
  switch(e.code) {
    case 'KeyW': case 'ArrowUp': moveForward = true; break
    case 'KeyS': case 'ArrowDown': moveBackward = true; break
    case 'KeyA': case 'ArrowLeft': moveLeft = true; break
    case 'KeyD': case 'ArrowRight': moveRight = true; break
  }
}

const onKeyUp = (e) => {
  switch(e.code) {
    case 'KeyW': case 'ArrowUp': moveForward = false; break
    case 'KeyS': case 'ArrowDown': moveBackward = false; break
    case 'KeyA': case 'ArrowLeft': moveLeft = false; break
    case 'KeyD': case 'ArrowRight': moveRight = false; break
  }
}

const onMouseDown = (e) => {
  isDragging = true
  previousMousePosition = { x: e.clientX, y: e.clientY }
}

const onMouseMove = (e) => {
  if (isDragging) {
    const deltaX = e.clientX - previousMousePosition.x
    const deltaY = e.clientY - previousMousePosition.y
    
    cameraRotation.yaw -= deltaX * 0.002
    cameraRotation.pitch -= deltaY * 0.002
    cameraRotation.pitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, cameraRotation.pitch))
    
    previousMousePosition = { x: e.clientX, y: e.clientY }
  }
}

const onMouseUp = () => {
  isDragging = false
}

const onClick = (e) => {
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1
  
  raycaster.setFromCamera(mouse, camera)
  
  const clickableObjects = models.map(m => m.model)
  const intersects = raycaster.intersectObjects(clickableObjects, true)
  
  if (intersects.length > 0) {
    const clickedModel = models.find(m => {
      return m.model === intersects[0].object || m.model.children.includes(intersects[0].object)
    })
    if (clickedModel) {
      emit('agentClicked', clickedModel.agent)
    }
  }
}

const onResize = () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

onMounted(() => {
  setupScene()
  animate()
  
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  window.addEventListener('click', onClick)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('mousedown', onMouseDown)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  window.removeEventListener('click', onClick)
  window.removeEventListener('resize', onResize)
  
  if (renderer) {
    renderer.dispose()
    models.forEach(({ mixer }) => mixer?.stopAllAction())
  }
})
</script>

<style scoped>
.olimpo-glb-world {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(to bottom, #0066cc 0%, #ccddff 100%);
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
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
  transform: translate(-50%, -100%);
  pointer-events: none;
  transition: opacity 0.3s;
}

.nameplate-bg {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 215, 0, 0.6);
  border-radius: 12px;
  padding: 8px 16px;
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.3);
}

.agent-name-3d {
  color: #FFD700;
  font-weight: bold;
  font-size: 14px;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.8);
  white-space: nowrap;
}

.agent-status-3d {
  color: #ffffff;
  font-size: 11px;
  opacity: 0.9;
  text-align: center;
}

.controls-hint {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 215, 0, 0.4);
  border-radius: 16px;
  padding: 16px 32px;
  pointer-events: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.controls-hint p {
  margin: 6px 0;
  color: #ffffff;
  font-size: 14px;
  text-align: center;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.8);
}
</style>

