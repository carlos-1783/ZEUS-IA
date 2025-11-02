import * as THREE from 'three';

/**
 * Personaje 3D procedural para ZEUS-IA
 * Sin necesidad de modelos externos - Solo geometría Three.js
 */
export class ProceduralCharacter {
  constructor(name, color = 0x4a90e2, position = { x: 0, y: 0, z: 0 }) {
    this.name = name;
    this.color = color;
    this.group = new THREE.Group();
    this.group.position.set(position.x, position.y, position.z);
    
    // Partes del cuerpo
    this.parts = {};
    
    // Animación
    this.walkCycle = 0;
    this.isWalking = false;
    this.walkSpeed = 2;
    this.targetPosition = null;
    
    // Crear el personaje
    this.createBody();
    this.createHead();
    this.createArms();
    this.createLegs();
    this.createHalo();
    
    // Metadata para interacción
    this.group.userData = {
      name: this.name,
      isAgent: true,
      character: this
    };
  }
  
  /**
   * Crear cuerpo (torso)
   */
  createBody() {
    const bodyGeometry = new THREE.CylinderGeometry(0.4, 0.5, 1.2, 8);
    const bodyMaterial = new THREE.MeshStandardMaterial({
      color: this.color,
      metalness: 0.3,
      roughness: 0.7
    });
    
    const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
    body.position.y = 2.5;
    body.castShadow = true;
    body.receiveShadow = true;
    
    this.parts.body = body;
    this.group.add(body);
  }
  
  /**
   * Crear cabeza
   */
  createHead() {
    const headGeometry = new THREE.SphereGeometry(0.35, 16, 16);
    const headMaterial = new THREE.MeshStandardMaterial({
      color: 0xffdbac, // Piel
      metalness: 0.1,
      roughness: 0.8
    });
    
    const head = new THREE.Mesh(headGeometry, headMaterial);
    head.position.y = 3.5;
    head.castShadow = true;
    
    // Ojos simples
    const eyeGeometry = new THREE.SphereGeometry(0.08, 8, 8);
    const eyeMaterial = new THREE.MeshStandardMaterial({ color: 0x000000 });
    
    const leftEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
    leftEye.position.set(-0.15, 0.1, 0.3);
    head.add(leftEye);
    
    const rightEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
    rightEye.position.set(0.15, 0.1, 0.3);
    head.add(rightEye);
    
    this.parts.head = head;
    this.group.add(head);
  }
  
  /**
   * Crear brazos
   */
  createArms() {
    const armGeometry = new THREE.CylinderGeometry(0.12, 0.1, 0.8, 8);
    const armMaterial = new THREE.MeshStandardMaterial({
      color: this.color,
      metalness: 0.2,
      roughness: 0.8
    });
    
    // Brazo izquierdo
    const leftArm = new THREE.Mesh(armGeometry, armMaterial);
    leftArm.position.set(-0.6, 2.7, 0);
    leftArm.castShadow = true;
    this.parts.leftArm = leftArm;
    this.group.add(leftArm);
    
    // Brazo derecho
    const rightArm = new THREE.Mesh(armGeometry, armMaterial);
    rightArm.position.set(0.6, 2.7, 0);
    rightArm.castShadow = true;
    this.parts.rightArm = rightArm;
    this.group.add(rightArm);
  }
  
  /**
   * Crear piernas
   */
  createLegs() {
    const legGeometry = new THREE.CylinderGeometry(0.15, 0.12, 1.0, 8);
    const legMaterial = new THREE.MeshStandardMaterial({
      color: new THREE.Color(this.color).multiplyScalar(0.7),
      metalness: 0.2,
      roughness: 0.8
    });
    
    // Pierna izquierda
    const leftLeg = new THREE.Mesh(legGeometry, legMaterial);
    leftLeg.position.set(-0.25, 1.3, 0);
    leftLeg.castShadow = true;
    this.parts.leftLeg = leftLeg;
    this.group.add(leftLeg);
    
    // Pierna derecha
    const rightLeg = new THREE.Mesh(legGeometry, legMaterial);
    rightLeg.position.set(0.25, 1.3, 0);
    rightLeg.castShadow = true;
    this.parts.rightLeg = rightLeg;
    this.group.add(rightLeg);
  }
  
  /**
   * Crear halo dorado (para look divino)
   */
  createHalo() {
    const haloGeometry = new THREE.TorusGeometry(0.5, 0.05, 8, 32);
    const haloMaterial = new THREE.MeshStandardMaterial({
      color: 0xffd700,
      emissive: 0xffd700,
      emissiveIntensity: 0.5,
      metalness: 0.8,
      roughness: 0.2
    });
    
    const halo = new THREE.Mesh(haloGeometry, haloMaterial);
    halo.position.y = 4.2;
    halo.rotation.x = Math.PI / 2;
    
    this.parts.halo = halo;
    this.group.add(halo);
  }
  
  /**
   * Actualizar animaciones
   */
  update(deltaTime) {
    if (!deltaTime) return;
    
    // Animación de idle (respiración)
    if (!this.isWalking) {
      const breathe = Math.sin(Date.now() * 0.001) * 0.05;
      this.parts.body.scale.y = 1 + breathe;
      this.parts.head.position.y = 3.5 + breathe * 0.5;
    }
    
    // Rotación del halo
    this.parts.halo.rotation.z += deltaTime * 0.5;
    
    // Walk cycle
    if (this.isWalking) {
      this.walkCycle += deltaTime * this.walkSpeed;
      
      // Oscilación de brazos
      this.parts.leftArm.rotation.x = Math.sin(this.walkCycle * Math.PI) * 0.5;
      this.parts.rightArm.rotation.x = Math.sin(this.walkCycle * Math.PI + Math.PI) * 0.5;
      
      // Oscilación de piernas
      this.parts.leftLeg.rotation.x = Math.sin(this.walkCycle * Math.PI + Math.PI) * 0.4;
      this.parts.rightLeg.rotation.x = Math.sin(this.walkCycle * Math.PI) * 0.4;
      
      // Oscilación del cuerpo
      this.parts.body.position.y = 2.5 + Math.abs(Math.sin(this.walkCycle * Math.PI * 2)) * 0.1;
      
      // Movimiento hacia objetivo
      if (this.targetPosition) {
        const direction = new THREE.Vector3()
          .subVectors(this.targetPosition, this.group.position)
          .normalize();
        
        const distance = this.group.position.distanceTo(this.targetPosition);
        
        if (distance > 0.5) {
          // Mover hacia el objetivo
          this.group.position.add(direction.multiplyScalar(deltaTime * this.walkSpeed));
          
          // Rotar hacia la dirección de movimiento
          const angle = Math.atan2(direction.x, direction.z);
          this.group.rotation.y = angle;
        } else {
          // Llegó al destino
          this.isWalking = false;
          this.targetPosition = null;
        }
      }
    }
  }
  
  /**
   * Caminar hacia una posición
   */
  walkTo(position) {
    this.targetPosition = new THREE.Vector3(position.x, position.y, position.z);
    this.isWalking = true;
  }
  
  /**
   * Detener movimiento
   */
  stopWalking() {
    this.isWalking = false;
    this.targetPosition = null;
    
    // Reset rotaciones
    this.parts.leftArm.rotation.x = 0;
    this.parts.rightArm.rotation.x = 0;
    this.parts.leftLeg.rotation.x = 0;
    this.parts.rightLeg.rotation.x = 0;
  }
  
  /**
   * Animación de hablar
   */
  talk(duration = 2000) {
    const startTime = Date.now();
    
    const talkAnimation = () => {
      const elapsed = Date.now() - startTime;
      
      if (elapsed < duration) {
        // Oscilación de cabeza mientras habla
        const talkCycle = Math.sin(elapsed * 0.01) * 0.1;
        this.parts.head.rotation.y = talkCycle;
        
        // Gestos con brazos
        this.parts.leftArm.rotation.z = Math.sin(elapsed * 0.005) * 0.3;
        this.parts.rightArm.rotation.z = -Math.sin(elapsed * 0.005) * 0.3;
        
        requestAnimationFrame(talkAnimation);
      } else {
        // Reset
        this.parts.head.rotation.y = 0;
        this.parts.leftArm.rotation.z = 0;
        this.parts.rightArm.rotation.z = 0;
      }
    };
    
    talkAnimation();
  }
  
  /**
   * Obtener el grupo Three.js
   */
  getGroup() {
    return this.group;
  }
  
  /**
   * Obtener posición
   */
  getPosition() {
    return this.group.position.clone();
  }
  
  /**
   * Establecer posición
   */
  setPosition(x, y, z) {
    this.group.position.set(x, y, z);
  }
}

/**
 * Configuración de colores por agente
 */
export const AGENT_COLORS = {
  'ZEUS CORE': 0xffd700,    // Dorado
  'PERSEO': 0x4a90e2,       // Azul
  'RAFAEL': 0x2ecc71,       // Verde
  'THALOS': 0xe74c3c,       // Rojo
  'JUSTICIA': 0x9b59b6      // Púrpura
};

/**
 * Factory para crear personajes
 */
export function createAgent(name, position) {
  const color = AGENT_COLORS[name] || 0x95a5a6;
  return new ProceduralCharacter(name, color, position);
}

