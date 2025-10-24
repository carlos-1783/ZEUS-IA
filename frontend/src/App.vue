<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

// Performance: Solo inicializar una vez
let isInitialized = false

onMounted(() => {
  // Performance: Prevenir múltiples inicializaciones
  if (isInitialized) return
  
  console.log('✅ ZEUS IA Frontend iniciado')
  
  // Performance: Inicialización non-blocking con Promise
  Promise.resolve().then(async () => {
    try {
      await authStore.initialize()
      console.log('✅ Auth initialized:', authStore.isAuthenticated)
    } catch (error) {
      console.error('❌ Auth init error:', error)
    }
  })
  
  isInitialized = true
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>