<template>
  <div class="dashboard">
    <!-- Estado de carga -->
    <div v-if="isLoading" class="fixed inset-0 bg-white bg-opacity-75 flex items-center justify-center z-50">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
        <p class="mt-4 text-gray-700">Cargando datos del dashboard...</p>
      </div>
    </div>
    
    <!-- Mensaje de error -->
    <div v-else-if="error" class="fixed inset-0 bg-white flex items-center justify-center z-50">
      <div class="text-center p-6 max-w-md mx-auto">
        <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
          <i class="fas fa-exclamation-triangle text-red-600 text-xl"></i>
        </div>
        <h3 class="mt-3 text-lg font-medium text-gray-900">Error al cargar el dashboard</h3>
        <p class="mt-2 text-sm text-gray-500">{{ error }}</p>
        <div class="mt-5">
          <button
            @click="retryLoading"
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            <i class="fas fa-sync-alt mr-2"></i>
            Reintentar
          </button>
          <button
            @click="authStore.logout()"
            class="ml-3 inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            <i class="fas fa-sign-out-alt mr-2"></i>
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
    <!-- Barra superior con información del usuario y estado -->
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
        <h1 class="text-2xl font-bold text-gray-900">Panel de Control</h1>
        <div class="flex items-center space-x-4">
          <SystemStatusBadge />
          <div class="relative">
            <button 
              @click="showUserMenu = !showUserMenu"
              class="flex items-center space-x-2 focus:outline-none"
            >
              <span class="inline-block h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center">
                <i class="fas fa-user text-indigo-600"></i>
              </span>
              <span class="hidden md:inline text-sm font-medium text-gray-700">
                {{ userFullName }}
              </span>
            </button>
            
            <!-- Menú desplegable del usuario -->
            <div 
              v-if="showUserMenu" 
              class="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
              role="menu"
              tabindex="-1"
            >
              <div class="py-1" role="none">
                <router-link 
                  to="/perfil" 
                  class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  role="menuitem"
                  @click="showUserMenu = false"
                >
                  <i class="fas fa-user-circle mr-2"></i> Perfil
                </router-link>
                <button
                  @click="handleLogout"
                  class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  role="menuitem"
                >
                  <i class="fas fa-sign-out-alt mr-2"></i> Cerrar sesión
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Contenido principal -->
    <main class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
      <!-- Tarjetas de métricas -->
      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <DashboardMetric 
          v-for="metric in metrics" 
          :key="metric.title"
          :title="metric.title"
          :value="metric.value"
          :icon="metric.icon"
          :trend="metric.trend"
          :trend-value="metric.trendValue"
          :loading="isLoading"
        />
      </div>

      <!-- Sección de gráficos y experiencia 3D -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <!-- Gráfico de ventas -->
        <div class="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-medium text-gray-900">Ventas Recientes</h2>
            <div class="flex space-x-2">
              <button 
                v-for="period in ['Día', 'Semana', 'Mes']"
                :key="period"
                @click="selectedPeriod = period.toLowerCase()"
                class="px-3 py-1 text-sm rounded-md"
                :class="{
                  'bg-indigo-100 text-indigo-700': selectedPeriod === period.toLowerCase(),
                  'text-gray-500 hover:bg-gray-100': selectedPeriod !== period.toLowerCase()
                }"
              >
                {{ period }}
              </button>
            </div>
          </div>
          <div class="h-64">
            <canvas ref="salesChart"></canvas>
          </div>
        </div>

        <!-- Experiencia 3D -->
        <div class="bg-white rounded-lg shadow overflow-hidden">
          <div class="p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Vista 3D</h2>
            <div class="h-64">
              <Zeus3D class="h-full w-full" />
            </div>
          </div>
        </div>
      </div>

      <!-- Tabla de actividad reciente -->
      <div class="bg-white shadow overflow-hidden sm:rounded-lg">
        <div class="px-4 py-5 sm:px-6 border-b border-gray-200">
          <h3 class="text-lg leading-6 font-medium text-gray-900">Actividad Reciente</h3>
          <p class="mt-1 max-w-2xl text-sm text-gray-500">
            Últimas actividades en el sistema
          </p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actividad
                </th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Usuario
                </th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Fecha
                </th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(activity, index) in recentActivities" :key="index">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center">
                    <div class="flex-shrink-0 h-10 w-10">
                      <i :class="[activityIcons[activity.type], 'text-indigo-600 text-lg']"></i>
                    </div>
                    <div class="ml-4">
                      <div class="text-sm font-medium text-gray-900">
                        {{ activity.title }}
                      </div>
                      <div class="text-sm text-gray-500">
                        {{ activity.description }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900">{{ activity.user }}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-500">{{ formatDate(activity.timestamp) }}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="[
                    'px-2 inline-flex text-xs leading-5 font-semibold rounded-full',
                    activity.status === 'completed' ? 'bg-green-100 text-green-800' :
                    activity.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  ]">
                    {{ activity.status === 'completed' ? 'Completado' : activity.status === 'pending' ? 'Pendiente' : 'Error' }}
                  </span>
                </td>
              </tr>
              <tr v-if="recentActivities.length === 0">
                <td colspan="4" class="px-6 py-4 text-center text-sm text-gray-500">
                  No hay actividades recientes
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import api from '@/api';
import { Chart, registerables } from 'chart.js';
import { format, subDays } from 'date-fns';
import { es } from 'date-fns/locale/es';

// Registrar componentes de Chart.js
Chart.register(...registerables);

// Componentes
import SystemStatusBadge from '@/components/SystemStatusBadge.vue';
import Zeus3D from '@/components/Zeus3D.vue';
import DashboardMetric from '@/components/DashboardMetric.vue';

// Estado reactivo
const authStore = useAuthStore();
const router = useRouter();
const selectedPeriod = ref('día'); // Valor por defecto, puede ser 'día', 'semana' o 'mes'
const showUserMenu = ref(false);
const isLoading = ref(true);
const error = ref(null);
const userData = ref(null);
const currentUser = ref(null);
const salesChart = ref(null);

// Datos del dashboard
const metrics = ref([
  { 
    title: 'Ventas Hoy', 
    value: '1,245', 
    icon: 'shopping-cart',
    trend: 'up',
    trendValue: '12%',
    loading: false
  },
  { 
    title: 'Ingresos', 
    value: '$12,548', 
    icon: 'dollar-sign',
    trend: 'down',
    trendValue: '3%'
  },
  { 
    title: 'Clientes Nuevos', 
    value: '24', 
    icon: 'users',
    trend: 'up',
    trendValue: '8%'
  },
  { 
    title: 'Órdenes', 
    value: '156', 
    icon: 'box',
    trend: 'up',
    trendValue: '5%'
  }
]);

// Actividades recientes
const recentActivities = ref([
  {
    id: 1,
    title: 'Nueva orden creada',
    description: 'Orden #1001 por $125.75',
    type: 'order',
    user: 'Juan Pérez',
    timestamp: new Date(),
    status: 'completed'
  },
  {
    id: 2,
    title: 'Error de pago',
    description: 'Error al procesar el pago #1002',
    type: 'error',
    user: 'María García',
    timestamp: subDays(new Date(), 1),
    status: 'error'
  },
  {
    id: 3,
    title: 'Nuevo cliente registrado',
    description: 'Carlos López se ha registrado',
    type: 'user',
    user: 'Sistema',
    timestamp: subDays(new Date(), 2),
    status: 'completed'
  }
]);

// Íconos para las actividades
const activityIcons = {
  order: 'fas fa-shopping-cart',
  error: 'fas fa-exclamation-circle',
  user: 'fas fa-user-plus',
  system: 'fas fa-cog'
};

// Computed properties
const userFullName = computed(() => {
  return authStore.userFullName || 'Usuario';
});

// Métodos
/**
 * Formatea una fecha a un string legible
 * @param {string|Date|undefined} date - Fecha a formatear
 * @returns {string} Fecha formateada
 */
const formatDate = (date) => {
  if (!date) return '';
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return format(dateObj, 'dd/MM/yyyy HH:mm', { locale: es });
  } catch (error) {
    console.error('Error formateando fecha:', error);
    return 'Fecha inválida';
  }
};

const loadUserData = async () => {
  try {
    const userData = await api.getCurrentUser();
    user.value = userData;
  } catch (error) {
    console.error('Error al cargar datos del usuario:', error);
  }
};

const handleLogout = async () => {
  try {
    await authStore.logout();
    router.push('/login');
  } catch (error) {
    console.error('Error al cerrar sesión:', error);
  }
};

// Cerrar menú al hacer clic fuera
const handleClickOutside = (event) => {
  const userMenu = document.querySelector('.user-menu');
  const userMenuButton = document.querySelector('[aria-expanded="true"]');
  
  if (userMenu && userMenuButton && !userMenu.contains(event.target) && !userMenuButton.contains(event.target)) {
    showUserMenu.value = false;
  }
};

// Inicialización del gráfico
const initChart = () => {
  // Destruir gráfico existente si hay uno
  if (salesChart.value) {
    const chartInstance = Chart.getChart(salesChart.value);
    if (chartInstance) {
      chartInstance.destroy();
    }
  }
  if (salesChart.value) {
    const ctx = salesChart.value.getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: Array.from({ length: 7 }, (_, i) => {
          const date = subDays(new Date(), 6 - i);
          return format(date, 'EEE', { locale: es });
        }),
        datasets: [
          {
            label: 'Ventas',
            data: [12, 19, 3, 5, 2, 3, 15],
            borderColor: 'rgb(79, 70, 229)',
            backgroundColor: 'rgba(79, 70, 229, 0.1)',
            tension: 0.4,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              display: true,
              drawBorder: false
            },
            ticks: {
              stepSize: 5
            }
          },
          x: {
            grid: {
              display: false,
              drawBorder: false
            }
          }
        }
      }
    });
  }
};

// Watchers
watch(selectedPeriod, (newPeriod) => {
  console.log('Período seleccionado:', newPeriod);
  // Aquí iría la lógica para actualizar los datos según el período seleccionado
});

// Ciclo de vida
onMounted(() => {
  // Cargar datos iniciales
  const loadData = async () => {
    try {
      isLoading.value = true;
      error.value = null;
      
      // Verificar autenticación
      if (!authStore.isAuthenticated) {
        // Intentar refrescar el token
        const refreshed = await authStore.refreshAccessToken();
        if (!refreshed) {
          throw new Error('Sesión expirada. Por favor, inicia sesión nuevamente.');
        }
      }
      
      // Obtener datos del usuario actual a través de la API
      try {
        userData.value = await api.getCurrentUser();
        console.log('Datos del usuario:', userData.value);
      } catch (userError) {
        console.error('Error al obtener datos del usuario:', userError);
        // Si falla la obtención del usuario, usar datos del store
        if (authStore.user) {
          userData.value = authStore.user;
        } else {
          throw userError;
        }
      }
      
      // Cargar datos adicionales en paralelo
      await Promise.all([
        // getDashboardData(),
        // getRecentActivities()
      ]);
      
      // Inicializar el gráfico después de que los datos estén listos
      nextTick(() => {
        initChart();
      });
    } catch (err) {
      console.error('Error al cargar los datos del dashboard:', err);
      error.value = err.response?.data?.message || err.message || 'Error al cargar los datos del dashboard';
      
      // Redirigir a login si el error es de autenticación
      if (err.response?.status === 401 || err.message.includes('Sesión expirada')) {
        authStore.logout();
        router.push('/login');
      }
    } finally {
      isLoading.value = false;
    }
  };
  
  // Función para reintentar la carga de datos
  const retryLoading = async () => {
    try {
      error.value = null;
      isLoading.value = true;
      await loadData();
    } catch (err) {
      console.error('Error al reintentar la carga:', err);
      error.value = 'No se pudo cargar el dashboard. Por favor, inténtalo de nuevo más tarde.';
    } finally {
      isLoading.value = false;
    }
  };

  loadData();
  
  // Agregar event listener para cerrar el menú al hacer clic fuera
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  // Limpiar event listeners
  document.removeEventListener('click', handleClickOutside);
});
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background-color: #f3f4f6; /* bg-gray-100 */
}

/* Estilos para el menú desplegable */
.user-menu {
  position: absolute;
  right: 0;
  margin-top: 0.5rem;
  width: 12rem;
  border-radius: 0.375rem;
  --tw-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --tw-shadow-colored: 0 10px 15px -3px var(--tw-shadow-color), 0 4px 6px -4px var(--tw-shadow-color);
  box-shadow: var(--tw-ring-offset-shadow, 0 0 #0000), var(--tw-ring-shadow, 0 0 #0000), var(--tw-shadow);
  background-color: #ffffff;
  --tw-ring-offset-shadow: var(--tw-ring-inset) 0 0 0 var(--tw-ring-offset-width) var(--tw-ring-offset-color);
  --tw-ring-shadow: var(--tw-ring-inset) 0 0 0 calc(1px + var(--tw-ring-offset-width)) var(--tw-ring-color);
  box-shadow: var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow, 0 0 #0000);
  --tw-ring-opacity: 1;
  --tw-ring-color: rgb(0 0 0 / var(--tw-ring-opacity));
  --tw-ring-opacity: 0.05;
  outline: 2px solid transparent;
  outline-offset: 2px;
}

/* Estilos para el gráfico */
.chart-container {
  position: relative;
  height: 16rem; /* h-64 */
}

/* Estilos para la tabla */
.table-container {
  overflow-x: auto;
}

/* Estilos para las tarjetas de métricas */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 1.25rem; /* gap-5 */
}

@media (min-width: 640px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

/* Estilos para los botones */
.btn {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border: 1px solid transparent;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 500;
  border-radius: 0.375rem;
  --tw-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --tw-shadow-colored: 0 1px 2px 0 var(--tw-shadow-color);
  box-shadow: var(--tw-ring-offset-shadow, 0 0 #0000), var(--tw-ring-shadow, 0 0 #0000), var(--tw-shadow);
  color: #ffffff;
  background-color: #4f46e5; /* bg-indigo-600 */
}

.btn:hover {
  background-color: #4338ca; /* hover:bg-indigo-700 */
}

.btn:focus {
  outline: 2px solid transparent;
  outline-offset: 2px;
  --tw-ring-offset-shadow: var(--tw-ring-inset) 0 0 0 var(--tw-ring-offset-width) var(--tw-ring-offset-color);
  --tw-ring-shadow: var(--tw-ring-inset) 0 0 0 calc(2px + var(--tw-ring-offset-width)) var(--tw-ring-color);
  box-shadow: var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow, 0 0 #0000);
  --tw-ring-opacity: 1;
  --tw-ring-color: rgb(99 102 241 / var(--tw-ring-opacity));
  --tw-ring-offset-width: 2px;
}

.btn-outline {
  border-color: #d1d5db; /* border-gray-300 */
  color: #374151; /* text-gray-700 */
  background-color: #ffffff; /* bg-white */
}

.btn-outline:hover {
  background-color: #f9fafb; /* hover:bg-gray-50 */
}

.btn-outline:focus {
  --tw-ring-color: #6366f1; /* focus:ring-indigo-500 */
}

/* Estilos para los estados */
.status-badge {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  display: inline-flex;
  font-size: 0.75rem;
  line-height: 1.25rem;
  font-weight: 600;
  border-radius: 9999px;
}

.status-badge.completed {
  background-color: #dcfce7; /* bg-green-100 */
  color: #166534; /* text-green-800 */
}

.status-badge.pending {
  background-color: #fef9c3; /* bg-yellow-100 */
  color: #854d0e; /* text-yellow-800 */
}

.status-badge.error {
  background-color: #fee2e2; /* bg-red-100 */
  color: #991b1b; /* text-red-800 */
}

/* Animaciones */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>