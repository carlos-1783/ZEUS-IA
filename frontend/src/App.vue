<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const authStore = useAuthStore()

onMounted(async () => {
  console.log('ZEUS IA Frontend iniciado correctamente')
  console.log('Current route:', route.path)
  console.log('Route name:', route.name)
  
  // Inicializar autenticación
  await authStore.initialize()
  console.log('Auth initialized:', authStore.isAuthenticated)
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>