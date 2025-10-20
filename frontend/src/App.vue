<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

onMounted(() => {
  console.log('ZEUS IA Frontend iniciado correctamente')
  console.log('Current route:', route.path)
  console.log('Route name:', route.name)
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  width: 100%;
}
</style>