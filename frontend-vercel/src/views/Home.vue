<template>
  <div class="home">
    <h1>Bienvenido a ZEUS IA</h1>
    <p>Tu negocio autónomo inteligente</p>
    <router-link to="/dashboard" class="btn btn-primary">
      Ir al Dashboard
    </router-link>
  </div>
</template>

<script setup lang="ts">
// Componente Home básico
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  text-align: center;
}

.btn {
  padding: 12px 24px;
  border-radius: 8px;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.3s ease;
}

.btn-primary {
  background-color: #4f46e5;
  color: white;
}

.btn-primary:hover {
  background-color: #4338ca;
}
</style>
