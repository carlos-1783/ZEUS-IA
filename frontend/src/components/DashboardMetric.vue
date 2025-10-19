<template>
  <div class="bg-white overflow-hidden shadow rounded-lg">
    <div class="p-5">
      <div class="flex items-center">
        <div 
          class="flex-shrink-0 rounded-md p-3"
          :class="{
            'bg-indigo-100': !loading,
            'bg-gray-200': loading,
            'animate-pulse': loading
          }"
        >
          <i 
            v-if="!loading"
            :class="['fas', `fa-${icon}`, 'text-indigo-600 text-lg']"
          ></i>
          <div v-else class="h-6 w-6"></div>
        </div>
        <div class="ml-5 w-0 flex-1">
          <dl>
            <dt class="text-sm font-medium text-gray-500 truncate">
              {{ loading ? 'Cargando...' : title }}
            </dt>
            <dd>
              <div class="text-lg font-medium text-gray-900">
                {{ loading ? '...' : value }}
              </div>
            </dd>
          </dl>
        </div>
      </div>
      
      <!-- Trend indicator -->
      <div v-if="!loading && trend" class="mt-4 flex items-center">
        <span 
          :class="[
            'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
            trend === 'up' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          ]"
        >
          <i 
            :class="[
              'mr-1',
              trend === 'up' ? 'fa-arrow-up' : 'fa-arrow-down'
            ]"
          ></i>
          {{ trendValue }}
        </span>
        <span class="ml-2 text-sm text-gray-500">
          vs. período anterior
        </span>
      </div>
      
      <!-- Skeleton loader -->
      <div v-else-if="loading" class="mt-4">
        <div class="h-4 bg-gray-200 rounded w-3/4"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    required: true
  },
  icon: {
    type: String,
    required: true
  },
  trend: {
    type: String,
    validator: value => ['up', 'down', null, undefined].includes(value),
    default: null
  },
  trendValue: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
});
</script>

<style scoped>
/* Estilos específicos del componente */
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
