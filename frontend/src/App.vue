<template>
  <div id="app">
    <RouterView />
    <ToastNotification />
  </div>
</template>

<script setup lang="ts">
import ToastNotification from '@/components/ToastNotification.vue'

// Performance: NO inicializar auth aquí - el router lo maneja
// Esto elimina las violations de 'visibilitychange' (6909ms)
console.log('✅ ZEUS IA Frontend iniciado')
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>