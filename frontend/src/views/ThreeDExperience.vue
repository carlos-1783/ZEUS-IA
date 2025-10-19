<template>
  <div class="three-d-experience">
    <div v-if="isLoading">Cargando experiencia 3D...</div>
    <div v-else-if="error">Error: {{ error }}</div>
    <div v-else>
      <!-- Aquí irá tu canvas o escena de Three.js -->
      <div ref="container" class="three-container"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';

const isLoading = ref(false);
const error = ref<string | null>(null);
const container = ref(null);

// Ejemplo de inicialización segura de Three.js
onMounted(async () => {
  isLoading.value = true;
  await nextTick();
  if (!container.value) {
    error.value = 'No se encontró el contenedor para la escena 3D.';
    isLoading.value = false;
    return;
  }
  try {
    // Aquí iría la inicialización de Three.js
    // Por ejemplo: initScene(containerRef.value)
    // ...
    isLoading.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    isLoading.value = false;
  }
});

onBeforeUnmount(() => {
  // Aquí puedes limpiar la escena de Three.js si es necesario
});
</script>

<style scoped>
.three-d-experience {
  width: 100%;
  height: 100%;
}
.three-container {
  width: 100%;
  height: 600px;
  background: #111;
}
</style> 