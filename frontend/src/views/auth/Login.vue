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
            <label for="email-address" class="sr-only">{{ t('auth.login.emailPlaceholder') }}</label>
            <input
              id="email-address"
              v-model="form.email"
              name="email"
              type="email"
              autocomplete="email"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              :placeholder="t('auth.login.emailPlaceholder')"
              :disabled="isLoading"
            >
          </div>
          <div>
            <label for="password" class="sr-only">{{ t('auth.login.passwordPlaceholder') }}</label>
            <input
              id="password"
              v-model="form.password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              :placeholder="t('auth.login.passwordPlaceholder')"
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
              {{ t('auth.login.rememberMe') }}
            </label>
          </div>

          <div class="text-sm">
            <a href="#" class="font-medium text-indigo-600 hover:text-indigo-500">
              {{ t('auth.login.forgotPassword') }}
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
            <span v-if="!isLoading">{{ t('auth.login.submit') }}</span>
            <span v-else>{{ t('auth.login.submitting') }}</span>
          </button>
        </div>
      </form>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';

console.log('🔍 Login.vue component is mounting...')

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const { t } = useI18n();

console.log('🔍 Login.vue router:', router)
console.log('🔍 Login.vue route:', route)

// DESHABILITAR TOAST TEMPORALMENTE PARA EVITAR VIOLACIONES DE RENDIMIENTO
const toast = {
  success: (msg: string) => console.log('✅', msg),
  error: (msg: string) => console.error('❌', msg)
}
const form = ref({
  email: '',
  password: '',
  rememberMe: false
});

const error = ref('');
const isLoading = ref(false);
const redirectTo = (route.query.redirect as string) || '/dashboard';

const normalizeErrorMessage = (err: unknown, fallbackKey: string) => {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  if (err && typeof err === 'object' && 'message' in err) {
    const maybeMessage = (err as { message?: unknown }).message;
    if (typeof maybeMessage === 'string') {
      return maybeMessage;
    }
  }
  return t(fallbackKey);
};

// Verificar si ya hay una sesión activa
onMounted(() => {
  console.log('🔍 Login.vue onMounted called!')
  console.log('🔍 Login.vue authStore.isAuthenticated:', authStore.isAuthenticated)
  console.log('🔍 Login.vue redirectTo:', redirectTo)
  
  if (authStore.isAuthenticated) {
    console.log('🔍 Login.vue redirecting to:', redirectTo)
    router.push(redirectTo);
  } else {
    console.log('🔍 Login.vue not authenticated, staying on login page')
  }
});

// Validar formulario
const validateForm = (): true | Record<string, string> => {
  const errors: Record<string, string> = {};
  
  if (!form.value.email) {
    errors.email = t('auth.login.emailRequired');
  } else if (!/\S+@\S+\.\S+/.test(form.value.email)) {
    errors.email = t('auth.login.emailInvalid');
  }
  
  if (!form.value.password) {
    errors.password = t('auth.login.passwordRequired');
  } else if (form.value.password.length < 6) {
    errors.password = t('auth.login.passwordLength');
  }
  
  return Object.keys(errors).length === 0 ? true : errors;
};

// Manejar envío del formulario
const handleSubmit = async () => {
  console.log('[auth/Login.vue] handleSubmit llamado');
  
  // Performance: Validación síncrona rápida
  const validation = validateForm();
  if (validation !== true) {
    error.value = Object.values(validation).join('\n');
    return;  // ✅ No usar alert - solo mostrar error en UI
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    console.log('[auth/Login.vue] Iniciando proceso de login...');
    
    // Performance: Ejecutar login de forma non-blocking
    const result = await authStore.login(form.value.email, form.value.password);
    console.log('[auth/Login.vue] Resultado del login:', result);
    
    if (result.success) {
      console.log('✅ Login exitoso, redirigiendo...');
      
      // Performance: Verificación rápida del token
      const token = localStorage.getItem('auth_token');
      
      if (!token) {
        error.value = t('auth.login.tokenError');
        return;
      }
      
      // Performance: Redirección inmediata sin delays
      console.log('🚀 Redirigiendo a:', redirectTo);
      window.location.href = redirectTo;
      
    } else {
      // Performance: Solo mostrar error en UI, sin alerts
      const mensaje = normalizeErrorMessage(result.error ?? result.message, 'auth.login.defaultError');
      error.value = mensaje;
      console.error('Error de login:', mensaje);
    }
  } catch (err) {
    console.error('[auth/Login.vue] Error en el inicio de sesión:', err);
    
    // Performance: Solo mostrar error en UI, sin alerts
    const mensaje = normalizeErrorMessage(err, 'auth.login.genericError');
    error.value = mensaje;
    console.error('Error:', mensaje);
  } finally {
    isLoading.value = false;
  }
};
</script>
