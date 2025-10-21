<template>
  <div>
    <div v-if="error" class="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <p class="text-sm text-red-700 whitespace-pre-line">
            {{ error }}
          </p>
        </div>
      </div>
    </div>

    <form @submit.prevent="handleSubmit" class="space-y-6">
      <div>
        <label for="email" class="block text-sm font-medium text-gray-700">
          Correo electrónico
        </label>
        <input
          id="email"
          v-model="form.email"
          type="email"
          required
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          placeholder="tu@email.com"
          :disabled="isLoading"
        />
      </div>

      <div>
        <label for="password" class="block text-sm font-medium text-gray-700">
          Contraseña
        </label>
        <input
          id="password"
          v-model="form.password"
          type="password"
          required
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          placeholder="Tu contraseña"
          :disabled="isLoading"
        />
      </div>

      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <input
            id="remember-me"
            v-model="form.rememberMe"
            type="checkbox"
            class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            :disabled="isLoading"
          />
          <label for="remember-me" class="ml-2 block text-sm text-gray-900">
            Recordar sesión
          </label>
        </div>

        <div class="text-sm">
          <a href="#" class="font-medium text-indigo-600 hover:text-indigo-500">
            ¿Olvidaste tu contraseña?
          </a>
        </div>
      </div>

      <div>
        <button
          type="submit"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
          :disabled="isLoading"
        >
          <span v-if="!isLoading">Iniciar sesión</span>
          <span v-else>Iniciando sesión...</span>
        </button>
      </div>

      <div class="text-center">
        <p class="text-sm text-gray-600">
          ¿No tienes cuenta? 
          <router-link to="/auth/register" class="font-medium text-indigo-600 hover:text-indigo-500">
            Crear cuenta
          </router-link>
        </p>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// Form data
const form = ref({
  email: '',
  password: '',
  rememberMe: false
});

// State
const isLoading = ref(false);
const error = ref('');

// Methods
const handleSubmit = async () => {
  if (isLoading.value) return;
  
  isLoading.value = true;
  error.value = '';
  
  try {
    console.log('🔐 Intentando iniciar sesión...', form.value);
    
    // Simular login por ahora
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    console.log('✅ Login exitoso');
    router.push('/dashboard');
    
  } catch (err) {
    console.error('❌ Error en login:', err);
    error.value = 'Error al iniciar sesión. Inténtalo de nuevo.';
  } finally {
    isLoading.value = false;
  }
};
</script>
