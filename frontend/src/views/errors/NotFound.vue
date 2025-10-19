<template>
  <div class="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <h1 class="mt-6 text-center text-6xl font-extrabold text-gray-900">
        404
      </h1>
      <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
        Página no encontrada
      </h2>
      <p class="mt-2 text-center text-sm text-gray-600">
        Lo sentimos, no pudimos encontrar la página que estás buscando.
      </p>
      <div class="mt-6">
        <router-link
          to="/"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Volver al inicio
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';

const router = useRouter();

// Optional: Redirect to home after a delay
// setTimeout(() => {
//   router.push('/');
// }, 5000);
</script>

<style scoped>
/* Add any component-specific styles here */
</style>
