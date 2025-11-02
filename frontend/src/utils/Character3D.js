import * as THREE from 'three'

export class Character3D {
  constructor(agentData) {
    this.agentData = agentData
    this.group = new THREE.Group()
    
    // Partes del cuerpo
    this.head = null
    this.body = null
    this.leftArm = null
    this.rightArm = null
    this.leftLeg = null
    this.rightLeg = null
    
    // Animación
    this.walkPhase = Math.random() * Math.PI * 2
    this.targetPosition = new THREE.Vector3()
    this.walkSpeed = 0.8 + Math.random() * 0.4
    this.idleTime = 0
    
    this.createCharacter()
  }
  
  createCharacter() {
    const skinColor = 0xffdbac
    const clothColor = 0x3b82f6
    
    // CUERPO COMPLETO - Usar cilindro ancho con tu foto mapeada
    const bodyGeometry = new THREE.CylinderGeometry(0.4, 0.3, 1.8, 32, 4, true)
    const textureLoader = new THREE.TextureLoader()
    
    // Cargar la imagen del avatar y mapearla al cilindro
    const bodyTexture = textureLoader.load(
      this.agentData.image || '/images/avatars/perseo-avatar.jpg',
      (texture) => {
        // Configurar textura para que cubra todo el cilindro
        texture.wrapS = THREE.RepeatWrapping
        texture.wrapT = THREE.ClampToEdgeWrapping
        texture.colorSpace = THREE.SRGBColorSpace
      }
    )
    
    const bodyMaterial = new THREE.MeshStandardMaterial({ 
      map: bodyTexture,
      side: THREE.DoubleSide,
      transparent: true,
      alphaTest: 0.5,
      roughness: 0.7,
      metalness: 0.1
    })
    
    this.body = new THREE.Mesh(bodyGeometry, bodyMaterial)
    this.body.position.y = 0.9
    this.body.castShadow = true
    this.body.receiveShadow = true
    this.group.add(this.body)
    
    // CABEZA - Esfera pequeña encima (invisible, solo para estructura)
    const headGeometry = new THREE.SphereGeometry(0.2, 16, 16)
    const headMaterial = new THREE.MeshStandardMaterial({ 
      color: skinColor,
      transparent: true,
      opacity: 0  // Invisible - la foto del cuerpo ya incluye la cabeza
    })
    this.head = new THREE.Mesh(headGeometry, headMaterial)
    this.head.position.y = 1.8
    this.group.add(this.head)
    
    // CUELLO
    const neckGeometry = new THREE.CylinderGeometry(0.08, 0.1, 0.15, 8)
    const neckMaterial = new THREE.MeshStandardMaterial({ color: skinColor })
    const neck = new THREE.Mesh(neckGeometry, neckMaterial)
    neck.position.y = 1.2
    neck.castShadow = true
    this.group.add(neck)
    
    // TORSO
    const torsoGeometry = new THREE.CapsuleGeometry(0.3, 0.6, 8, 8)
    const torsoMaterial = new THREE.MeshStandardMaterial({ 
      color: clothColor,
      roughness: 0.7
    })
    this.body = new THREE.Mesh(torsoGeometry, torsoMaterial)
    this.body.position.y = 0.8
    this.body.castShadow = true
    this.group.add(this.body)
    
    // BRAZOS
    const armGeometry = new THREE.CapsuleGeometry(0.08, 0.5, 6, 6)
    const armMaterial = new THREE.MeshStandardMaterial({ color: skinColor })
    
    this.leftArm = new THREE.Mesh(armGeometry, armMaterial)
    this.leftArm.position.set(-0.4, 0.8, 0)
    this.leftArm.rotation.z = 0.2
    this.leftArm.castShadow = true
    this.group.add(this.leftArm)
    
    this.rightArm = new THREE.Mesh(armGeometry, armMaterial.clone())
    this.rightArm.position.set(0.4, 0.8, 0)
    this.rightArm.rotation.z = -0.2
    this.rightArm.castShadow = true
    this.group.add(this.rightArm)
    
    // PIERNAS
    const legGeometry = new THREE.CapsuleGeometry(0.12, 0.7, 8, 8)
    const legMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x2c3e50,
      roughness: 0.8
    })
    
    this.leftLeg = new THREE.Mesh(legGeometry, legMaterial)
    this.leftLeg.position.set(-0.15, 0.35, 0)
    this.leftLeg.castShadow = true
    this.group.add(this.leftLeg)
    
    this.rightLeg = new THREE.Mesh(legGeometry, legMaterial.clone())
    this.rightLeg.position.set(0.15, 0.35, 0)
    this.rightLeg.castShadow = true
    this.group.add(this.rightLeg)
    
    // Aura/glow
    const glowGeometry = new THREE.SphereGeometry(0.6, 16, 16)
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: 0xffd700,
      transparent: true,
      opacity: 0.15,
      side: THREE.BackSide
    })
    const glow = new THREE.Mesh(glowGeometry, glowMaterial)
    glow.position.y = 1
    this.group.add(glow)
  }
  
  update(delta) {
    // Fase de caminar
    this.walkPhase += delta * 6
    
    // Animación de brazos (balanceo opuesto)
    if (this.leftArm && this.rightArm) {
      const armSwing = Math.sin(this.walkPhase) * 0.5
      this.leftArm.rotation.x = armSwing
      this.rightArm.rotation.x = -armSwing
    }
    
    // Animación de piernas (balanceo opuesto)
    if (this.leftLeg && this.rightLeg) {
      const legSwing = Math.sin(this.walkPhase) * 0.6
      this.leftLeg.rotation.x = legSwing
      this.rightLeg.rotation.x = -legSwing
    }
    
    // Cabeza mira hacia adelante con balanceo sutil
    if (this.head) {
      this.head.rotation.y = Math.sin(this.walkPhase * 0.5) * 0.1
      this.head.rotation.x = Math.sin(this.walkPhase * 0.3) * 0.05
    }
    
    // Torso balancea con el paso
    if (this.body) {
      this.body.rotation.y = Math.sin(this.walkPhase * 0.5) * 0.05
      this.body.position.y = 0.8 + Math.abs(Math.sin(this.walkPhase)) * 0.05
    }
  }
  
  setWalking(isWalking) {
    // Ajustar velocidad de animación según si camina o está quieto
    this.isWalking = isWalking
  }
  
  lookAt(target) {
    this.group.lookAt(target.x, this.group.position.y, target.z)
  }
  
  getGroup() {
    return this.group
  }
  
  getPosition() {
    return this.group.position
  }
  
  setPosition(x, y, z) {
    this.group.position.set(x, y, z)
  }
}

