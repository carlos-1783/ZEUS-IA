<template>
  <div class="zeus-3d-container relative flex flex-col items-center justify-center h-full w-full">
    <img
      src="/images/zues-3d-main.png"
      alt="ZEUS IA Zeus"
      class="zeus-3d-image zeus-animated rounded-xl shadow-lg object-cover"
      draggable="false"
    />
    <div class="zeus-3d-buttons absolute inset-0 flex flex-col items-end justify-between p-6 pointer-events-none">
      <div class="flex flex-col space-y-4 mt-2 pointer-events-auto">
        <button @click="goToProfile" class="zeus-btn" title="Perfil de usuario">
          👤
        </button>
        <button @click="goToDashboard" class="zeus-btn" title="Panel de control">
          📊
        </button>
        <button @click="showSystemStatus" class="zeus-btn" title="Estado del sistema">
          📡
        </button>
        <button @click="toggle3D" class="zeus-btn" title="Vista 3D">
          🎮
        </button>
      </div>
      <div class="flex flex-col pointer-events-auto">
        <button @click="logout" class="zeus-btn" title="Cerrar sesión">
          🚪
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ref } from 'vue';

const router = useRouter();
const authStore = useAuthStore();
const is3DActive = ref(true);

const goToProfile = () => {
  router.push('/perfil');
};
const goToDashboard = () => {
  router.push('/dashboard');
};
const showSystemStatus = () => {
  // Performance: NO usar alert - usar console.log
  console.log('✅ Estado del sistema: conectado');
  // TODO: Implementar modal o toast en el futuro
};
const toggle3D = () => {
  is3DActive.value = !is3DActive.value;
  // Aquí puedes añadir lógica para maximizar/minimizar la experiencia 3D
};
const logout = async () => {
  await authStore.logout();
  router.push('/login');
};
</script>

<style scoped>
.zeus-3d-container {
  background: linear-gradient(135deg, #0a2342 60%, #1e293b 100%);
  border-radius: 1.5rem;
  overflow: hidden;
  min-height: 350px;
  min-width: 320px;
  position: relative;
}

.zeus-3d-image {
  width: 100%;
  height: 320px;
  object-fit: cover;
  user-select: none;
  pointer-events: none;
}

/* ⚡ ANIMACIÓN DE ZEUS - QUE SE MUEVA */
.zeus-animated {
  animation: zeus-breathe 4s ease-in-out infinite, zeus-glow 3s ease-in-out infinite;
  transform-origin: center center;
}

@keyframes zeus-breathe {
  0%, 100% { 
    transform: scale(1) translateY(0);
  }
  50% { 
    transform: scale(1.02) translateY(-5px);
  }
}

@keyframes zeus-glow {
  0%, 100% { 
    filter: brightness(1) drop-shadow(0 0 10px rgba(59, 130, 246, 0.3));
  }
  50% { 
    filter: brightness(1.1) drop-shadow(0 0 20px rgba(59, 130, 246, 0.6));
  }
}

.zeus-3d-container:hover .zeus-animated {
  animation: zeus-power 1s ease-in-out infinite, zeus-glow-intense 1s ease-in-out infinite;
}

@keyframes zeus-power {
  0%, 100% { 
    transform: scale(1.05) rotate(-1deg);
  }
  50% { 
    transform: scale(1.08) rotate(1deg);
  }
}

@keyframes zeus-glow-intense {
  0%, 100% { 
    filter: brightness(1.15) drop-shadow(0 0 30px rgba(59, 130, 246, 0.8));
  }
  50% { 
    filter: brightness(1.25) drop-shadow(0 0 40px rgba(147, 51, 234, 0.9));
  }
}

.zeus-3d-buttons {
  z-index: 2;
}

.zeus-btn {
  background: rgba(10, 35, 66, 0.85);
  color: #ffd700;
  border: none;
  border-radius: 50%;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  transition: all 0.3s ease;
  cursor: pointer;
}

.zeus-btn:hover {
  background: #ffd700;
  color: #0a2342;
  transform: scale(1.15) rotate(5deg);
  box-shadow: 0 4px 15px rgba(255, 215, 0, 0.5);
}

.zeus-btn:active {
  transform: scale(0.95);
}
</style> 