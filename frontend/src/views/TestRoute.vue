<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-4">Test Route</h1>
    <div class="space-y-6">
      <!-- Route Info Section -->
      <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-xl font-semibold mb-2">Route Information:</h2>
        <pre class="bg-gray-100 p-4 rounded overflow-auto text-sm">
          {{ JSON.stringify(route, null, 2) }}
        </pre>
      </div>
      
      <!-- Current Path -->
      <div class="bg-white p-4 rounded-lg shadow">
        <h3 class="text-lg font-medium mb-2">Current Path:</h3>
        <code class="bg-gray-100 p-2 rounded block overflow-x-auto">{{ currentPath }}</code>
      </div>
      
      <!-- Navigation Examples -->
      <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-xl font-semibold mb-4">Navigation Examples:</h2>
        
        <div class="space-y-4">
          <!-- Example 1: Using useNavigation -->
          <div class="border-l-4 border-blue-500 pl-4">
            <h3 class="font-medium text-gray-700 mb-2">1. Using useNavigation composable:</h3>
            <button 
              @click="navigateWithParams"
              class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              Navigate with Params & Query
            </button>
            <pre class="mt-2 bg-gray-100 p-2 rounded text-xs">
navigate('Test', {
  params: { id: 'test with spaces' },
  query: { filter: 'some value' }
})</pre>
          </div>
          
          <!-- Example 2: Using router-link with encodeUrlParam -->
          <div class="border-l-4 border-green-500 pl-4 mt-4">
            <h3 class="font-medium text-gray-700 mb-2">2. Using router-link with encodeUrlParam:</h3>
            <router-link 
              :to="dynamicLink"
              class="inline-block px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 text-sm mb-2"
            >
              Dynamic Link with Spaces
            </router-link>
            <pre class="bg-gray-100 p-2 rounded text-xs">
&lt;router-link 
  :to="`/test/${encodeUrlParam('test with spaces')}`"
&gt;
  Link with Spaces
&lt;/router-link&gt;</pre>
          </div>
          
          <!-- Example 3: Using buildUrl -->
          <div class="border-l-4 border-purple-500 pl-4 mt-4">
            <h3 class="font-medium text-gray-700 mb-2">3. Using buildUrl for API calls:</h3>
            <button 
              @click="fetchData"
              class="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600 text-sm"
            >
              Fetch Data with Query Params
            </button>
            <pre class="mt-2 bg-gray-100 p-2 rounded text-xs">
const url = buildUrl('/api/data', {
  filter: 'some value',
  page: 1,
  query: 'test with spaces'
});
// Result: {{ apiExampleUrl }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import { useNavigation } from '@/composables/useNavigation';
import { encodeUrlParam, buildUrl } from '@/utils/url';

const route = useRoute();
const { navigate } = useNavigation();
const currentPath = ref('');

// Example data
const dynamicLink = computed(() => ({
  path: `/test/${encodeUrlParam('test with spaces')}`,
  query: { filter: 'some value' }
}));

const apiExampleUrl = buildUrl('/api/data', {
  filter: 'some value',
  page: 1,
  query: 'test with spaces'
});

// Navigation methods
const navigateWithParams = () => {
  navigate('Test', {
    params: { id: 'test with spaces' },
    query: { filter: 'some value' }
  });
};

// Fetch data example
const fetchData = async () => {
  try {
    const url = buildUrl('/api/data', {
      filter: 'some value',
      page: 1,
      query: 'test with spaces'
    });
    
    // Example fetch call
    // const response = await fetch(url);
    // const data = await response.json();
    
    console.log('Fetching from:', url);
    alert(`Would fetch from: ${url}`);
  } catch (error) {
    console.error('Error fetching data:', error);
  }
};

// Update current path when route changes
const updateCurrentPath = () => {
  currentPath.value = window.location.pathname + window.location.search;
};

// Set up event listeners
onMounted(() => {
  updateCurrentPath();
  window.addEventListener('popstate', updateCurrentPath);  
  window.addEventListener('pushstate', updateCurrentPath);
});

onUnmounted(() => {
  window.removeEventListener('popstate', updateCurrentPath);
  window.removeEventListener('pushstate', updateCurrentPath);
});
</script>

<style scoped>
/* Add any custom styles here */
pre {
  font-family: 'Fira Code', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}
</style>
