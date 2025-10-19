<template>
  <div class="max-w-4xl mx-auto p-6">
    <h1 class="text-2xl font-bold mb-6">Authentication Test</h1>
    
    <!-- Auth State -->
    <div class="bg-white shadow rounded-lg p-6 mb-6">
      <h2 class="text-lg font-medium mb-4">Authentication State</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p class="text-sm font-medium text-gray-500">Is Authenticated</p>
          <p class="text-lg font-semibold" :class="{ 'text-green-600': isAuthenticated, 'text-red-600': !isAuthenticated }">
            {{ isAuthenticated ? 'Yes' : 'No' }}
          </p>
        </div>
        <div v-if="user">
          <p class="text-sm font-medium text-gray-500">User</p>
          <p class="text-lg font-semibold">{{ user.email }}</p>
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500">Access Token</p>
          <p class="text-sm font-mono truncate">{{ accessToken ? '••••••••' + accessToken.slice(-8) : 'None' }}</p>
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500">Refresh Token</p>
          <p class="text-sm font-mono truncate">{{ refreshToken ? '••••••••' + refreshToken.slice(-8) : 'None' }}</p>
        </div>
      </div>
    </div>

    <!-- Login Form -->
    <div v-if="!isAuthenticated" class="bg-white shadow rounded-lg p-6 mb-6">
      <h2 class="text-lg font-medium mb-4">Login</h2>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
          <input
            id="email"
            v-model="loginForm.email"
            type="email"
            required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
          <input
            id="password"
            v-model="loginForm.password"
            type="password"
            required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
        </div>
        <div>
          <button
            type="submit"
            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            :disabled="isLoading"
          >
            <span v-if="!isLoading">Login</span>
            <svg v-else class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </button>
        </div>
      </form>
      <div v-if="loginError" class="mt-4 p-3 bg-red-50 text-red-700 rounded-md">
        {{ loginError }}
      </div>
    </div>

    <!-- Protected Content -->
    <div v-else class="space-y-6">
      <!-- Protected Data -->
      <div class="bg-white shadow rounded-lg p-6">
        <h2 class="text-lg font-medium mb-4">Protected Data</h2>
        <div v-if="protectedData" class="bg-gray-50 p-4 rounded-md">
          <pre class="text-sm overflow-x-auto">{{ JSON.stringify(protectedData, null, 2) }}</pre>
        </div>
        <div v-else-if="isLoadingData" class="text-center py-4">
          <p>Loading protected data...</p>
        </div>
        <div v-else class="text-center py-4">
          <p>No data loaded. Click the button below to fetch protected data.</p>
        </div>
        <div class="mt-4">
          <button
            @click="fetchProtectedData"
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            :disabled="isLoadingData"
          >
            <span v-if="!isLoadingData">Fetch Protected Data</span>
            <svg v-else class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- Token Actions -->
      <div class="bg-white shadow rounded-lg p-6">
        <h2 class="text-lg font-medium mb-4">Token Actions</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            @click="handleRefreshToken"
            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            :disabled="isRefreshing"
          >
            <span v-if="!isRefreshing">Refresh Token</span>
            <svg v-else class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </button>
          <button
            @click="logout"
            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import api from '@/api';

const router = useRouter();
const authStore = useAuthStore();

// State
const loginForm = ref({
  email: 'test@example.com',
  password: 'password123',
});

const isLoading = ref(false);
const isRefreshing = ref(false);
const isLoadingData = ref(false);
const loginError = ref('');
const protectedData = ref(null);

// Computed
const isAuthenticated = computed(() => authStore.isAuthenticated);
const user = computed(() => authStore.user);
const accessToken = computed(() => authStore.accessToken);
const refreshToken = computed(() => authStore.refreshToken);

// Methods
const handleLogin = async () => {
  try {
    isLoading.value = true;
    loginError.value = '';
    
    const result = await authStore.login(
      loginForm.value.email,
      loginForm.value.password
    );
    
    if (!result.success) {
      loginError.value = result.error || 'Login failed';
    } else {
      // Reset form and error on successful login
      loginForm.value = { email: '', password: '' };
    }
  } catch (error) {
    console.error('Login error:', error);
    loginError.value = 'An error occurred during login';
  } finally {
    isLoading.value = false;
  }
};

const logout = async () => {
  try {
    await authStore.logout();
    protectedData.value = null;
  } catch (error) {
    console.error('Logout error:', error);
  }
};

const handleRefreshToken = async () => {
  try {
    isRefreshing.value = true;
    await authStore.refreshAccessToken();
  } catch (error) {
    console.error('Token refresh error:', error);
  } finally {
    isRefreshing.value = false;
  }
};

const fetchProtectedData = async () => {
  try {
    isLoadingData.value = true;
    const response = await system.testProtectedEndpoint();
    protectedData.value = response.data;
  } catch (error) {
    console.error('Failed to fetch protected data:', error);
    protectedData.value = { error: 'Failed to fetch protected data' };
  } finally {
    isLoadingData.value = false;
  }
};

// Lifecycle hooks
onMounted(() => {
  // Auto-fetch protected data if already authenticated
  if (isAuthenticated.value) {
    fetchProtectedData();
  }
});
</script>
