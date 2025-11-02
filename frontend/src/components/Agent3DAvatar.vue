<template>
  <div class="agent-3d-container" ref="container"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'

const props = defineProps({
  agentName: String,
  imagePath: String,
  isActive: Boolean,
  isSpeaking: Boolean
})

const container = ref(null)
let scene, camera, renderer, mesh, animationId
let breathPhase = 0
let speakPhase = 0

onMounted(() => {
  initThreeJS()
  animate()
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (renderer) renderer.dispose()
})

watch(() => props.isSpeaking, (speaking) => {
  if (speaking) {
    // Animación más rápida cuando habla
    speakPhase = 0
  }
})

const initThreeJS = () => {
  // Escena
  scene = new THREE.Scene()
  
  // Cámara
  camera = new THREE.PerspectiveCamera(
    50,
    1, // aspect ratio 1:1 para circular
    0.1,
    1000
  )
  camera.position.z = 2
  
  // Renderer
  renderer = new THREE.WebGLRenderer({ 
    alpha: true, 
    antialias: true 
  })
  renderer.setSize(250, 250)
  renderer.setPixelRatio(window.devicePixelRatio)
  container.value.appendChild(renderer.domElement)
  
  // Geometría - Plano con la imagen del agente
  const geometry = new THREE.PlaneGeometry(1.5, 1.5, 32, 32)
  
  // Textura - Cargar imagen del agente
  const textureLoader = new THREE.TextureLoader()
  const texture = textureLoader.load(props.imagePath || '/images/avatars/perseo-avatar.jpg')
  
  // Material con la imagen
  const material = new THREE.MeshStandardMaterial({
    map: texture,
    transparent: true,
    side: THREE.DoubleSide,
    emissive: new THREE.Color(0x3b82f6),
    emissiveIntensity: 0.2
  })
  
  mesh = new THREE.Mesh(geometry, material)
  scene.add(mesh)
  
  // Hacer el mesh circular (deformación de vértices)
  const positionAttribute = geometry.getAttribute('position')
  for (let i = 0; i < positionAttribute.count; i++) {
    const x = positionAttribute.getX(i)
    const y = positionAttribute.getY(i)
    const distance = Math.sqrt(x * x + y * y)
    
    // Ocultar vértices fuera del círculo
    if (distance > 0.75) {
      positionAttribute.setZ(i, -10) // Empujar hacia atrás
    }
  }
  geometry.computeVertexNormals()
  
  // Luces
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)
  
  const pointLight1 = new THREE.PointLight(0xffd700, 1, 100)
  pointLight1.position.set(2, 2, 2)
  scene.add(pointLight1)
  
  const pointLight2 = new THREE.PointLight(0x3b82f6, 0.8, 100)
  pointLight2.position.set(-2, -2, 2)
  scene.add(pointLight2)
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  
  if (!mesh) return
  
  // RESPIRACIÓN - Movimiento sutil constante
  breathPhase += 0.01
  const breathScale = 1 + Math.sin(breathPhase) * 0.03
  mesh.scale.set(breathScale, breathScale, 1)
  
  // Movimiento de cabeza sutil
  mesh.rotation.y = Math.sin(breathPhase * 0.5) * 0.05
  mesh.rotation.x = Math.cos(breathPhase * 0.3) * 0.02
  
  // Si está hablando - movimiento más intenso
  if (props.isSpeaking) {
    speakPhase += 0.15
    const speakIntensity = Math.sin(speakPhase) * 0.08
    mesh.scale.set(
      breathScale + speakIntensity,
      breathScale + speakIntensity,
      1
    )
    mesh.rotation.z = Math.sin(speakPhase * 2) * 0.03
    
    // Cambiar color de luz cuando habla
    mesh.material.emissive = new THREE.Color(0x10b981)
    mesh.material.emissiveIntensity = 0.4 + Math.sin(speakPhase) * 0.2
  } else {
    mesh.material.emissive = new THREE.Color(0x3b82f6)
    mesh.material.emissiveIntensity = 0.2
  }
  
  renderer.render(scene, camera)
}
</script>

<style scoped>
.agent-3d-container {
  width: 250px;
  height: 250px;
  position: relative;
  border-radius: 50%;
  overflow: hidden;
  border: 4px solid rgba(255, 215, 0, 0.8);
  box-shadow: 
    0 0 40px rgba(255, 215, 0, 0.6),
    inset 0 0 30px rgba(59, 130, 246, 0.3);
}

.agent-3d-container :deep(canvas) {
  display: block;
  border-radius: 50%;
}
</style>

