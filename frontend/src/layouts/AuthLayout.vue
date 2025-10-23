<template>
  <div class="min-h-screen flex flex-col bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex justify-between items-center">
          <div class="flex-shrink-0">
            <h1 class="text-2xl font-bold text-indigo-600">
              <router-link to="/">ZEUS-IA</router-link>
            </h1>
          </div>
          <nav class="hidden md:flex space-x-8">
            <router-link 
              to="/auth/login" 
              class="text-gray-700 hover:text-indigo-600 px-3 py-2 text-sm font-medium"
              :class="{ 'text-indigo-600 border-b-2 border-indigo-600': $route.name === 'Login' }"
            >
              Iniciar sesión
            </router-link>
            <router-link 
              to="/auth/register" 
              class="text-gray-700 hover:text-indigo-600 px-3 py-2 text-sm font-medium"
              :class="{ 'text-indigo-600 border-b-2 border-indigo-600': $route.name === 'Register' }"
            >
              Crear cuenta
            </router-link>
          </nav>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-grow flex items-center justify-center p-4">
      <div class="w-full max-w-md">
        <div class="bg-white p-8 rounded-lg shadow-md">
          <div class="text-center mb-8">
            <h2 class="text-2xl font-bold text-gray-900">{{ pageTitle }}</h2>
            <p v-if="pageDescription" class="mt-2 text-sm text-gray-600">
              {{ pageDescription }}
            </p>
          </div>
          <router-view></router-view>
        </div>
      </div>
    </main>


    <!-- Footer -->
    <footer class="bg-white border-t border-gray-200">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <p class="text-center text-sm text-gray-500">
          &copy; {{ new Date().getFullYear() }} ZEUS-IA. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const pageTitle = computed(() => {
  return route.meta.title || 'Bienvenido a ZEUS-IA';
});

const pageDescription = computed(() => {
  return route.meta.description || '';
});
</script>

<style scoped>
/* Using direct Tailwind classes in template instead of @apply */
</style>
