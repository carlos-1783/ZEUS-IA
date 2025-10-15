<template>
  <div class="three-experience">
    <!-- Estado de carga -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="spinner"></div>
      <p>Cargando experiencia 3D...</p>
    </div>
    
    <!-- Mensaje de error -->
    <div v-else-if="error" class="error-message">
      <i class="fas fa-exclamation-triangle"></i>
      <p>{{ error }}</p>
    </div>
    
    <!-- Contenedor 3D -->
    <div v-else ref="container" class="three-container">
      <!-- El renderizado 3D se hará en este contenedor -->
    </div>
  </div>
</template>

<script>
import { onMounted, onBeforeUnmount, ref, watch, defineAsyncComponent, defineComponent, nextTick } from 'vue';

// Carga perezosa de Three.js
const loadThreeJS = () => {
  return Promise.all([
    import('three'),
    import('three/examples/jsm/loaders/GLTFLoader.js'),
    import('three/examples/jsm/controls/OrbitControls.js')
  ]).then(([three, { GLTFLoader }, { OrbitControls }]) => {
    return { ...three, GLTFLoader, OrbitControls };
  });
};

export default defineComponent({
  name: 'ThreeDExperience',
  props: {
    // Propiedad para controlar si la empresa está activada
    empresaActivada: {
      type: Boolean,
      default: false
    },
    // Texto que se mostrará en la escena 3D
    mensajeBienvenida: {
      type: String,
      default: 'Bienvenido a ZEUS-IA'
    },
    // Color de fondo de la escena
    colorFondo: {
      type: String,
      default: '#000000'
    }
  },
  setup(props) {
    const three = ref(null);
    const isLoading = ref(true);
    const error = ref(null);
    const container = ref(null);

    // Cargar Three.js de forma asíncrona
    const loadThree = async () => {
      try {
        await nextTick();
        if (!container.value) {
          error.value = 'No se encontró el contenedor para la escena 3D.';
          isLoading.value = false;
          return;
        }
        three.value = await loadThreeJS();
        initScene();
      } catch (err) {
        console.error('Error al cargar Three.js:', err);
        error.value = 'No se pudo cargar la experiencia 3D. Por favor, inténtalo de nuevo más tarde.';
      } finally {
        isLoading.value = false;
      }
    };

    // Variables para almacenar referencias a los recursos 3D
    let scene, camera, renderer, cube, audio, audioListener, audioLoader, geometry, material;
    let animationFrameId = null;
    const isAudioPlaying = ref(false);
    
    // Función para limpiar recursos
    const cleanupResources = () => {
      // Cancelar la animación
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
      
      // Eliminar el listener de redimensionamiento
      window.removeEventListener('resize', onWindowResize);
      
      // Liberar recursos de Three.js
      if (geometry) {
        geometry.dispose();
        geometry = null;
      }
      
      if (material) {
        material.dispose();
        material = null;
      }
      
      if (renderer) {
        renderer.dispose();
        if (container.value && container.value.contains(renderer.domElement)) {
          container.value.removeChild(renderer.domElement);
        }
        renderer = null;
      }
      
      // Liberar recursos de audio
      if (audio) {
        if (audio.isPlaying) audio.stop();
        if (audio.source) audio.source.disconnect();
        audio = null;
      }
      
      if (audioListener && camera) {
        camera.remove(audioListener);
        audioListener = null;
      }
      
      cube = null;
      scene = null;
      camera = null;
    };
    
    // Inicializar la escena 3D
    const initScene = () => {
      if (!three.value) return;
      if (!container.value) {
        error.value = 'No se encontró el contenedor para la escena 3D.';
        return;
      }
      
      const { Scene, WebGLRenderer, PerspectiveCamera, BoxGeometry, MeshBasicMaterial, Mesh, 
              AmbientLight, DirectionalLight, Color, Audio, AudioListener, AudioLoader } = three.value;
              
      // Crear la escena
      scene = new Scene();
      scene.background = new Color(props.colorFondo);

      // Configurar la cámara
      const width = container.value.clientWidth;
      const height = container.value.clientHeight;
      camera = new PerspectiveCamera(
        75, // Campo de visión
        width / height, // Relación de aspecto
        0.1, // Plano cercano
        1000 // Plano lejano
      );
      
      // Optimización: Reducir la precisión de la matriz de proyección
      camera.matrixAutoUpdate = true;
      camera.position.z = 5;

      // Configurar el renderizador
      renderer = new WebGLRenderer({ 
        antialias: true, 
        alpha: true,
        powerPreference: 'high-performance',
        antialias: false // Desactivar antialiasing para mejor rendimiento
      });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      container.value.appendChild(renderer.domElement);

      // Crear un cubo con geometría optimizada
      geometry = new BoxGeometry(1, 1, 1, 1, 1, 1); // Reducir subdivisiones
      material = new MeshBasicMaterial({ 
        color: 0x00ff00,
        wireframe: true,
        transparent: true,
        opacity: 0.9
      });
      cube = new Mesh(geometry, material);
      scene.add(cube);

      // Agregar luces optimizadas
      const ambientLight = new AmbientLight(0x404040);
      scene.add(ambientLight);

      const directionalLight = new DirectionalLight(0xffffff, 1);
      directionalLight.position.set(1, 1, 1);
      directionalLight.castShadow = false; // Desactivar sombras para mejor rendimiento
      scene.add(directionalLight);

      // Configurar el audio
      initAudio();

      // Manejar el redimensionamiento de la ventana
      window.addEventListener('resize', onWindowResize);
      
      // Iniciar la animación
      animate();
    };

    // Inicializar el audio con carga diferida
    const initAudio = () => {
      if (!three.value) return;
      
      const { Audio, AudioListener, AudioLoader } = three.value;
      
      audioListener = new AudioListener();
      camera.add(audioListener);
      
      // Crear un audio posicional
      audio = new Audio(audioListener);
      audioLoader = new AudioLoader();
      
      // Cargar el sonido con manejo de errores
      const audioPath = '/sounds/zeus-bienvenida.mp3';
      audioLoader.load(
        audioPath,
        (buffer) => {
          if (audio) {
            audio.setBuffer(buffer);
            audio.setLoop(false);
            audio.setVolume(0.5);
            
            // Reproducir automáticamente si la empresa está activada
            if (props.empresaActivada) {
              playWelcomeAudio();
            }
          }
        },
        undefined,
        (error) => {
          console.error('Error al cargar el audio:', error);
        }
      );
    };

    // Reproducir el audio de bienvenida
    const playWelcomeAudio = () => {
      if (audio && !isAudioPlaying.value) {
        audio.play();
        isAudioPlaying.value = true;
      }
    };

    // Actualizar la animación
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      
      // Rotar el cubo
      if (cube) {
        cube.rotation.x += 0.01;
        cube.rotation.y += 0.01;
      }
      
      renderer.render(scene, camera);
    };

    // Manejar el redimensionamiento de la ventana
    const onWindowResize = () => {
      if (camera && renderer) {
        camera.aspect = container.value.clientWidth / container.value.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.value.clientWidth, container.value.clientHeight);
      }
    };

    // Limpiar recursos
    const cleanup = () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
      
      if (renderer) {
        renderer.dispose();
        if (container.value && container.value.contains(renderer.domElement)) {
          container.value.removeChild(renderer.domElement);
        }
      }
      
      if (audio && audio.isPlaying) {
        audio.stop();
      }
      
      window.removeEventListener('resize', onWindowResize);
    };

    // Cargar Three.js cuando el componente se monte
    onMounted(() => {
      loadThree();
    });
    
    // Limpiar recursos cuando el componente se desmonte
    onBeforeUnmount(() => {
      cleanup();
    });
    
    // Observar cambios en la propiedad empresaActivada
    watch(() => props.empresaActivada, (newVal) => {
      if (newVal && audio && !isAudioPlaying.value) {
        playWelcomeAudio();
      }
    });

    return {
      container,
      isLoading,
      error
    };
  }
});
</script>

<style scoped>
.three-experience {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background-color: #000;
}

.three-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.three-container canvas {
  display: block;
  width: 100%;
  height: 100%;
  outline: none;
}

.loading-overlay,
.error-message {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.8);
  color: #fff;
  z-index: 10;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  border-top-color: #3b82f6;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 1rem;
}

.error-message {
  text-align: center;
  padding: 1rem;
}

.error-message i {
  font-size: 2rem;
  color: #ef4444;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
