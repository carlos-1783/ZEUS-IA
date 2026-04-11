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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getBackendLivenessUrl } from '@/utils/backendLivenessUrl'

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
  if (envUrl) return envUrl
  if (import.meta.env.DEV) return 'http://localhost:8000 (vía proxy /api/v1)'
  return 'mismo origen que la app'
})

const LIVENESS_TIMEOUT_MS = 12000
const RETRY_DELAYS_MS = [0, 1800, 3800, 6500]

let pollId: ReturnType<typeof setInterval> | undefined

/**
 * Comprueba disponibilidad con reintentos (Railway: cold start + migraciones → 502 intermitente).
 * No envía Authorization: el health no lo requiere y evita competir con refresh de token.
 */
const checkBackend = async (): Promise<boolean> => {
  const url = getBackendLivenessUrl()
  let lastDetail = ''

  for (let i = 0; i < RETRY_DELAYS_MS.length; i++) {
    const wait = RETRY_DELAYS_MS[i]
    if (wait > 0 && (RETRY_DELAYS_MS[i - 1] ?? 0) < wait) {
      await new Promise((r) => setTimeout(r, wait - (RETRY_DELAYS_MS[i - 1] ?? 0)))
    }
    try {
      const ac = new AbortController()
      const timer = setTimeout(() => ac.abort(), LIVENESS_TIMEOUT_MS)
      const res = await fetch(url, {
        method: 'GET',
        signal: ac.signal,
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      })
      clearTimeout(timer)

      if (res.ok) {
        showError.value = false
        return true
      }

      lastDetail = `HTTP ${res.status}`
      try {
        const j = await res.json()
        lastDetail = (j?.detail as string) || (j?.message as string) || lastDetail
      } catch {
        /* ignore */
      }

      if (res.status === 401) {
        showError.value = true
        errorDetails.value = lastDetail
        errorMessage.value = 'Sesión expirada. Por favor, inicia sesión nuevamente.'
        return false
      }
    } catch (err: any) {
      lastDetail =
        err?.name === 'AbortError'
          ? `Tiempo de espera (${LIVENESS_TIMEOUT_MS / 1000}s) en ${url}`
          : err?.message || 'Error desconocido'
    }
  }

  showError.value = true
  errorDetails.value = lastDetail

  if (/abort|timeout|tiempo de espera/i.test(lastDetail)) {
    errorMessage.value =
      'El servidor tardó demasiado en responder (puede estar arrancando). Espera unos segundos y pulsa Reintentar.'
  } else if (/502|503|504/i.test(lastDetail)) {
    errorMessage.value =
      'El servidor no respondió a tiempo (502/503). Suele pasar al despertar el servicio en Railway; reintenta en unos segundos.'
  } else if (/failed to fetch|network|load failed/i.test(lastDetail)) {
    errorMessage.value =
      'No se pudo conectar con el servidor. Comprueba la red y que la URL del API sea correcta.'
  } else {
    errorMessage.value = `Error del servidor: ${lastDetail}`
  }

  return false
}

const retry = async () => {
  await checkBackend()
  if (!showError.value) {
    window.location.reload()
  }
}

const dismiss = () => {
  showError.value = false
}

onMounted(() => {
  window.setTimeout(() => {
    void checkBackend()
  }, 600)
  pollId = window.setInterval(() => {
    void checkBackend()
  }, 60000)
})

onUnmounted(() => {
  if (pollId) window.clearInterval(pollId)
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
