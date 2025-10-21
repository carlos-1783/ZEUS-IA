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

      <form class="space-y-6" @submit.prevent="handleSubmit">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="email-address" class="sr-only">Correo electrónico</label>
            <input
              id="email-address"
              v-model="form.email"
              name="email"
              type="email"
              autocomplete="email"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="Correo electrónico"
              :disabled="isLoading"
            >
          </div>
          <div>
            <label for="password" class="sr-only">Contraseña</label>
            <input
              id="password"
              v-model="form.password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="Contraseña"
              :disabled="isLoading"
            >
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <input
              id="remember-me"
              v-model="form.rememberMe"
              name="remember-me"
              type="checkbox"
              class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              :disabled="isLoading"
            >
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
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            :disabled="isLoading"
          >
            <span class="absolute left-0 inset-y-0 flex items-center pl-3">
              <svg class="h-5 w-5 text-indigo-500 group-hover:text-indigo-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fill-rule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clip-rule="evenodd" />
              </svg>
            </span>
            <span v-if="!isLoading">Iniciar sesión</span>
            <span v-else>Iniciando sesión...</span>
          </button>
        </div>
      </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const form = ref({
  email: '',
  password: '',
  rememberMe: false
});

const error = ref('');
const isLoading = ref(false);
const redirectTo = route.query.redirect || '/';

// Verificar si ya hay una sesión activa
onMounted(() => {
  if (authStore.isAuthenticated) {
    router.push(redirectTo);
  }
});

// Validar formulario
const validateForm = () => {
  const errors = {};
  
  if (!form.value.email) {
    errors.email = 'El correo electrónico es obligatorio';
  } else if (!/\S+@\S+\.\S+/.test(form.value.email)) {
    errors.email = 'El correo electrónico no es válido';
  }
  
  if (!form.value.password) {
    errors.password = 'La contraseña es obligatoria';
  } else if (form.value.password.length < 6) {
    errors.password = 'La contraseña debe tener al menos 6 caracteres';
  }
  
  return Object.keys(errors).length === 0 ? true : errors;
};

// Manejar envío del formulario
const handleSubmit = async () => {
  console.log('[auth/Login.vue] handleSubmit llamado');
  const validation = validateForm();
  if (validation !== true) {
    error.value = Object.values(validation).join('\n');
    alert('Error de validación: ' + error.value);
    return;
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    console.log('[auth/Login.vue] Iniciando proceso de login...');
    const result = await authStore.login(form.value.email, form.value.password);
    console.log('[auth/Login.vue] Resultado del login:', result);
    
    if (result.success) {
      alert('Login exitoso, recargando estado y redirigiendo...');
      await authStore.initialize();
      // Verificar que el token se guardó correctamente
      const token = localStorage.getItem('auth_token');
      console.log('[auth/Login.vue] Token guardado en localStorage:', token ? '\u2705' : '\u274c No se guardó');
      
      if (!token) {
        alert('No se pudo guardar el token de autenticación');
        throw new Error('No se pudo guardar el token de autenticación');
      }
      setTimeout(() => {
        router.push(redirectTo);
      }, 100);
    } else {
      let mensaje = result.error || result.message || 'Error al iniciar sesión. Por favor, verifica tus credenciales.';
      if (typeof mensaje !== 'string') {
        mensaje = JSON.stringify(mensaje);
      }
      error.value = mensaje;
      alert('Error en login: ' + mensaje);
      console.error('Error mostrado al usuario:', mensaje);
    }
  } catch (err) {
    console.error('[auth/Login.vue] Error en el inicio de sesión:', err);
    let mensaje = err.message || 'Ocurrió un error al intentar iniciar sesión. Por favor, inténtalo de nuevo.';
    if (typeof mensaje !== 'string') {
      mensaje = JSON.stringify(mensaje);
    }
    error.value = mensaje;
    alert('Error inesperado en login: ' + mensaje);
    console.error('Error mostrado al usuario (catch):', mensaje);
  } finally {
    isLoading.value = false;
  }
};
</script>
