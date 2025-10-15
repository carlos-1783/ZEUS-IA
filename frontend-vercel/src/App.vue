<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

onMounted(() => {
  console.log('ZEUS IA Frontend iniciado correctamente')
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>