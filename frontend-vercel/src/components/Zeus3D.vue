<template>
  <div class="zeus-3d-container relative flex flex-col items-center justify-center h-full w-full">
    <img
      src="/images/zues-3d-main.png"
      alt="ZEUS IA Zeus"
      class="zeus-3d-image rounded-xl shadow-lg object-cover"
      draggable="false"
    />
    <div class="zeus-3d-buttons absolute inset-0 flex flex-col items-end justify-between p-6 pointer-events-none">
      <div class="flex flex-col space-y-4 mt-2 pointer-events-auto">
        <button @click="goToProfile" class="zeus-btn" title="Perfil de usuario">
          <i class="fas fa-user-circle"></i>
        </button>
        <button @click="goToDashboard" class="zeus-btn" title="Panel de control">
          <i class="fas fa-tachometer-alt"></i>
        </button>
        <button @click="showSystemStatus" class="zeus-btn" title="Estado del sistema">
          <i class="fas fa-signal"></i>
        </button>
        <button @click="toggle3D" class="zeus-btn" title="Vista 3D">
          <i class="fas fa-cube"></i>
        </button>
      </div>
      <div class="flex flex-col pointer-events-auto">
        <button @click="logout" class="zeus-btn" title="Cerrar sesión">
          <i class="fas fa-sign-out-alt"></i>
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
  // Aquí puedes abrir un modal o mostrar un toast con el estado del sistema
  alert('Estado del sistema: conectado');
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
}
.zeus-3d-image {
  width: 100%;
  height: 320px;
  object-fit: cover;
  user-select: none;
  pointer-events: none;
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
  transition: background 0.2s, transform 0.2s;
  cursor: pointer;
}
.zeus-btn:hover {
  background: #ffd700;
  color: #0a2342;
  transform: scale(1.1);
}
</style> 