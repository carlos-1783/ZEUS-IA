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
  
  // Performance: Defer auth init completamente (requestIdleCallback si disponible)
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      authStore.initialize().catch(console.error)
    })
  } else {
    // Fallback: setTimeout con delay largo
    setTimeout(() => {
      authStore.initialize().catch(console.error)
    }, 100)
  }
  
  isInitialized = true
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>