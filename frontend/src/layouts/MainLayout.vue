<template>
  <div class="min-h-screen bg-gray-100 flex">
    <!-- Mobile menu button -->
    <div class="md:hidden fixed top-4 left-4 z-50">
      <button 
        @click="isSidebarOpen = !isSidebarOpen"
        class="p-2 rounded-md text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
      >
        <span class="sr-only">Abrir menú</span>
        <svg 
          class="h-6 w-6" 
          xmlns="http://www.w3.org/2000/svg" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path 
            stroke-linecap="round" 
            stroke-linejoin="round" 
            stroke-width="2" 
            d="M4 6h16M4 12h16M4 18h16" 
          />
        </svg>
      </button>
    </div>

    <!-- Sidebar -->
    <div 
      class="fixed inset-y-0 left-0 transform md:translate-x-0 transition duration-300 ease-in-out z-40"
      :class="{
        'translate-x-0': isSidebarOpen,
        '-translate-x-full': !isSidebarOpen
      }"
    >
      <div class="flex flex-col h-full bg-indigo-700 w-64 shadow-lg">
        <!-- Logo -->
        <div class="flex items-center justify-center h-16 px-4 bg-indigo-800">
          <h1 class="text-white text-xl font-bold">ZEUS-IA</h1>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 px-2 py-4 space-y-1">
          <router-link 
            v-for="item in navigation" 
            :key="item.name"
            :to="{ name: item.route }"
            class="group flex items-center px-4 py-3 text-sm font-medium rounded-md text-indigo-100 hover:bg-indigo-600 hover:bg-opacity-75"
            :class="{ 'bg-indigo-800': $route.name === item.route }"
          >
            <font-awesome-icon 
              :icon="item.icon" 
              class="mr-3 h-5 w-5 text-indigo-300 group-hover:text-indigo-200" 
              aria-hidden="true" 
            />
            {{ item.name }}
          </router-link>
        </nav>

        <!-- User Profile -->
        <div class="p-4 border-t border-indigo-600">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <img 
                class="h-10 w-10 rounded-full" 
                :src="userAvatar" 
                alt="User avatar"
              >
            </div>
            <div class="ml-3">
              <p class="text-sm font-medium text-white">
                {{ userFullName || 'Usuario' }}
              </p>
              <button 
                @click="logout"
                class="text-xs font-medium text-indigo-200 hover:text-white"
              >
                Cerrar sesión
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex flex-col md:pl-64">
      <!-- Top navigation -->
      <header class="bg-white shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 class="text-lg font-semibold text-gray-900">
            {{ pageTitle }}
          </h1>
          <div class="flex items-center space-x-4">
            <!-- Add any header actions here -->
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </main>
    </div>
  </div>

  <!-- Overlay for mobile menu -->
  <div 
    v-if="isSidebarOpen"
    class="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
    @click="isSidebarOpen = false"
  ></div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const isSidebarOpen = ref(window.innerWidth >= 768);

// Navigation items
const navigation = [
  { name: 'Dashboard', route: 'Dashboard', icon: 'tachometer-alt' },
  // Add more navigation items as needed
];

// Computed properties
const pageTitle = computed(() => route.meta.title || 'Dashboard');
const userFullName = computed(() => authStore.userFullName);
const userAvatar = computed(() => {
  // Replace with actual user avatar URL or initials
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(userFullName.value || 'U')}&background=4f46e5&color=fff`;
});

// Methods
const logout = async () => {
  await authStore.logout();
  router.push({ name: 'Login' });
};

// Handle window resize
const handleResize = () => {
  isSidebarOpen.value = window.innerWidth >= 768;
};

// Add event listeners
onMounted(() => {
  window.addEventListener('resize', handleResize);
  handleResize(); // Set initial state
});

// Clean up event listeners
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Custom scrollbar for sidebar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
