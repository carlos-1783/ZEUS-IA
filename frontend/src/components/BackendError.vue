<template>
  <div v-if="showError" class="backend-error-overlay">
    <div class="backend-error-container">
      <div class="backend-error-icon">⚠️</div>
      <h2 class="backend-error-title">Error de Conexión</h2>
      <p class="backend-error-message">
        {{ errorMessage }}
      </p>
      <div class="backend-error-actions">
        <button @click="retry" class="btn-retry">Reintentar</button>
        <button @click="dismiss" class="btn-dismiss">Cerrar</button>
      </div>
      <div class="backend-error-details" v-if="showDetails">
        <p><strong>URL del backend:</strong> {{ backendUrl || 'No configurada' }}</p>
        <p><strong>Error:</strong> {{ errorDetails }}</p>
      </div>
      <button @click="showDetails = !showDetails" class="btn-toggle-details">
        {{ showDetails ? 'Ocultar' : 'Mostrar' }} detalles
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const props = defineProps<{
  error?: Error | null
  backendUrl?: string
}>()

const showError = ref(false)
const showDetails = ref(false)
const errorMessage = ref('No se pudo conectar con el servidor.')
const errorDetails = ref('')

const backendUrl = computed(() => {
  if (props.backendUrl) return props.backendUrl
  const envUrl = import.meta.env.VITE_API_BASE_URL
  return envUrl || 'http://localhost:8000 (desarrollo)'
})

const checkBackend = async () => {
  try {
    const api = (await import('@/services/api')).default
    await api.get('/health')
    showError.value = false
    return true
  } catch (err: any) {
    showError.value = true
    errorDetails.value = err.message || 'Error desconocido'
    
    if (err.message?.includes('fetch')) {
      errorMessage.value = 'No se pudo conectar con el servidor. Verifica que el backend esté ejecutándose.'
    } else if (err.status === 401) {
      errorMessage.value = 'Sesión expirada. Por favor, inicia sesión nuevamente.'
    } else {
      errorMessage.value = `Error del servidor: ${err.message || 'Error desconocido'}`
    }
    
    return false
  }
}

const retry = async () => {
  await checkBackend()
  if (!showError.value) {
    // Recargar página si conexión exitosa
    window.location.reload()
  }
}

const dismiss = () => {
  showError.value = false
}

onMounted(() => {
  // Verificar backend al montar
  checkBackend()
  
  // Verificar periódicamente (cada 30 segundos)
  setInterval(checkBackend, 30000)
})

// Exponer método para verificación manual
defineExpose({
  checkBackend,
  showError: () => { showError.value = true },
  hideError: () => { showError.value = false }
})
</script>

<style scoped>
.backend-error-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.backend-error-container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  max-width: 500px;
  width: 100%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.backend-error-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 20px;
}

.backend-error-title {
  font-size: 24px;
  font-weight: bold;
  color: #dc2626;
  text-align: center;
  margin-bottom: 15px;
}

.backend-error-message {
  font-size: 16px;
  color: #374151;
  text-align: center;
  margin-bottom: 25px;
  line-height: 1.5;
}

.backend-error-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 20px;
}

.btn-retry,
.btn-dismiss {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-retry {
  background: #3b82f6;
  color: white;
}

.btn-retry:hover {
  background: #2563eb;
}

.btn-dismiss {
  background: #6b7280;
  color: white;
}

.btn-dismiss:hover {
  background: #4b5563;
}

.backend-error-details {
  background: #f3f4f6;
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 15px;
  font-size: 12px;
  color: #6b7280;
}

.backend-error-details p {
  margin: 5px 0;
}

.btn-toggle-details {
  width: 100%;
  padding: 8px;
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-toggle-details:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}
</style>
