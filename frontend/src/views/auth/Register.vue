<template>
  <div class="space-y-6">
    <div v-if="error" class="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <p class="text-sm text-red-700">
            {{ error }}
          </p>
        </div>
      </div>
    </div>

    <form class="space-y-6" @submit.prevent="handleSubmit">
      <div class="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6">
        <div class="sm:col-span-3">
          <label for="first_name" class="block text-sm font-medium text-gray-700">
            Nombre
          </label>
          <div class="mt-1">
            <input
              id="first_name"
              v-model="form.first_name"
              name="first_name"
              type="text"
              autocomplete="given-name"
              required
              class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :class="{ 'border-red-300': errors.first_name }"
            >
            <p v-if="errors.first_name" class="mt-2 text-sm text-red-600">
              {{ errors.first_name }}
            </p>
          </div>
        </div>

        <div class="sm:col-span-3">
          <label for="last_name" class="block text-sm font-medium text-gray-700">
            Apellido
          </label>
          <div class="mt-1">
            <input
              id="last_name"
              v-model="form.last_name"
              name="last_name"
              type="text"
              autocomplete="family-name"
              required
              class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :class="{ 'border-red-300': errors.last_name }"
            >
            <p v-if="errors.last_name" class="mt-2 text-sm text-red-600">
              {{ errors.last_name }}
            </p>
          </div>
        </div>

        <div class="sm:col-span-6">
          <label for="email" class="block text-sm font-medium text-gray-700">
            Correo electrónico
          </label>
          <div class="mt-1">
            <input
              id="email"
              v-model="form.email"
              name="email"
              type="email"
              autocomplete="email"
              required
              class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :class="{ 'border-red-300': errors.email }"
            >
            <p v-if="errors.email" class="mt-2 text-sm text-red-600">
              {{ errors.email }}
            </p>
          </div>
        </div>

        <div class="sm:col-span-6">
          <label for="password" class="block text-sm font-medium text-gray-700">
            Contraseña
          </label>
          <div class="mt-1">
            <input
              id="password"
              v-model="form.password"
              name="password"
              type="password"
              autocomplete="new-password"
              required
              class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :class="{ 'border-red-300': errors.password }"
            >
            <p v-if="errors.password" class="mt-2 text-sm text-red-600">
              {{ errors.password }}
            </p>
          </div>
        </div>

        <div class="sm:col-span-6">
          <label for="password_confirmation" class="block text-sm font-medium text-gray-700">
            Confirmar contraseña
          </label>
          <div class="mt-1">
            <input
              id="password_confirmation"
              v-model="form.password_confirmation"
              name="password_confirmation"
              type="password"
              autocomplete="new-password"
              required
              class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :class="{ 'border-red-300': errors.password_confirmation }"
            >
            <p v-if="errors.password_confirmation" class="mt-2 text-sm text-red-600">
              {{ errors.password_confirmation }}
            </p>
          </div>
        </div>

        <div class="sm:col-span-6">
          <div class="flex items-start">
            <div class="flex items-center h-5">
              <input
                id="terms"
                v-model="form.terms"
                name="terms"
                type="checkbox"
                class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                :class="{ 'border-red-300': errors.terms }"
                required
              >
            </div>
            <div class="ml-3 text-sm">
              <label for="terms" class="font-medium text-gray-700">
                Acepto los <a href="#" class="text-indigo-600 hover:text-indigo-500">Términos de servicio</a> y la <a href="#" class="text-indigo-600 hover:text-indigo-500">Política de privacidad</a>
              </label>
              <p v-if="errors.terms" class="mt-2 text-sm text-red-600">
                {{ errors.terms }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div>
        <button
          type="submit"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          :disabled="isLoading"
        >
          <span v-if="!isLoading">Crear cuenta</span>
          <svg v-else class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </button>
      </div>
    </form>

    <div class="mt-6">
      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-gray-300"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-2 bg-gray-100 text-gray-500">
            ¿Ya tienes una cuenta?
          </span>
        </div>
      </div>

      <div class="mt-6">
        <router-link
          to="/auth/login"
          class="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Iniciar sesión
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

const isLoading = ref(false);
const error = ref('');
const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  password_confirmation: '',
  terms: false
});

const errors = reactive({
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  password_confirmation: '',
  terms: ''
});

// Pre-fill email if it's in the query params
onMounted(() => {
  if (route.query.email) {
    form.email = route.query.email;
  }
});

// Form validation
const validateForm = () => {
  let isValid = true;
  
  // Reset errors
  Object.keys(errors).forEach(key => {
    errors[key] = '';
  });
  
  // First name validation
  if (!form.first_name.trim()) {
    errors.first_name = 'El nombre es obligatorio';
    isValid = false;
  }
  
  // Last name validation
  if (!form.last_name.trim()) {
    errors.last_name = 'El apellido es obligatorio';
    isValid = false;
  }
  
  // Email validation
  if (!form.email) {
    errors.email = 'El correo electrónico es obligatorio';
    isValid = false;
  } else if (!/\S+@\S+\.\S+/.test(form.email)) {
    errors.email = 'El correo electrónico no es válido';
    isValid = false;
  }
  
  // Password validation
  if (!form.password) {
    errors.password = 'La contraseña es obligatoria';
    isValid = false;
  } else if (form.password.length < 8) {
    errors.password = 'La contraseña debe tener al menos 8 caracteres';
    isValid = false;
  } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(form.password)) {
    errors.password = 'La contraseña debe contener al menos una letra mayúscula, una minúscula y un número';
    isValid = false;
  }
  
  // Password confirmation
  if (form.password !== form.password_confirmation) {
    errors.password_confirmation = 'Las contraseñas no coinciden';
    isValid = false;
  }
  
  // Terms acceptance
  if (!form.terms) {
    errors.terms = 'Debes aceptar los términos y condiciones';
    isValid = false;
  }
  
  return isValid;
};

// Handle form submission
const handleSubmit = async () => {
  if (!validateForm()) {
    return;
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    // TODO: Implement actual registration logic with your API
    // const response = await authStore.register({
    //   name: `${form.first_name} ${form.last_name}`,
    //   email: form.email,
    //   password: form.password,
    //   password_confirmation: form.password_confirmation
    // });
    
    // For now, just simulate a successful registration
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    // Redirect to login with the registered email
    router.push({
      name: 'Login',
      query: { email: form.email, registered: 'true' }
    });
  } catch (err) {
    console.error('Registration error:', err);
    error.value = err.response?.data?.message || 'Ocurrió un error al registrar la cuenta. Por favor, inténtalo de nuevo.';
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Add any component-specific styles here */
</style>
