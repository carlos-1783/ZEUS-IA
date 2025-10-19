<!-- SystemStatusBadge.vue -->
<template>
  <div class="system-status-badge" :class="statusClass" :title="tooltip">
    <span class="status-dot"></span>
    <span class="status-text">{{ statusText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useWebSocket } from '@/utils/WebSocketService';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const { status, error, connect, disconnect, cleanup } = useWebSocket();
const lastError = ref<Error | null>(null);

// Status text and styling
const statusText = computed(() => {
  switch (status.value) {
    case 'connected': return 'Connected';
    case 'connecting': return 'Connecting...';
    case 'reconnecting': return 'Reconnecting...';
    case 'error': return 'Connection Error';
    default: return 'Disconnected';
  }
});

const statusClass = computed(() => ({
  'status-connected': status.value === 'connected',
  'status-connecting': status.value === 'connecting',
  'status-reconnecting': status.value === 'reconnecting',
  'status-error': status.value === 'error',
  'status-disconnected': status.value === 'disconnected'
}));

const tooltip = computed(() => {
  if (error.value) {
    return `Error: ${error.value.message}`;
  }
  if (lastError.value) {
    return `Error: ${lastError.value.message}`;
  }
  return statusText.value;
});

// Handle errors
watch(error, (newError) => {
  if (newError) {
    lastError.value = newError;
  }
});

// Connect when component mounts and auth is available
const connectIfAuthenticated = () => {
  try {
    console.log("[SystemStatusBadge] Verificando autenticación...");
    
    // Verificar si el store está inicializado
    if (!authStore) {
      console.error('[SystemStatusBadge] authStore no está disponible');
      return;
    }
    
    console.log("[SystemStatusBadge] Token en authStore:", 
      authStore.token ? `${authStore.token.substring(0, 10)}...` : 'null/undefined');
    console.log("[SystemStatusBadge] isAuthenticated:", authStore.isAuthenticated);
    
    if (authStore.isAuthenticated && authStore.token) {
      console.log("[SystemStatusBadge] Intentando conectar WebSocket...");
      connect(authStore.token).catch((err) => {
        const error = err instanceof Error ? err : new Error(String(err));
        console.error('[SystemStatusBadge] Error al conectar WebSocket:', error);
        lastError.value = error;
        
        // Si es un error de red, no intentar reconectar automáticamente
        if (error.message.includes('Network error') || error.message.includes('Tiempo de conexión agotado')) {
          console.log('[SystemStatusBadge] Error de red detectado, no se intentará reconectar automáticamente');
        }
      });
    } else {
      console.log('[SystemStatusBadge] Usuario no autenticado o token no disponible, no se puede conectar WebSocket');
    }
  } catch (error) {
    const err = error instanceof Error ? error : new Error(String(error));
    console.error('[SystemStatusBadge] Error en connectIfAuthenticated:', err);
    lastError.value = err;
  }
};

// Watch for auth changes y reconectar automáticamente
watch(
  () => authStore.token,
  (newToken, oldToken) => {
    try {
      console.log('[SystemStatusBadge] Cambio de token detectado', {
        oldToken: oldToken ? '***TOKEN_ANTERIOR***' : 'null',
        newToken: newToken ? '***NUEVO_TOKEN***' : 'null',
        isAuthenticated: authStore.isAuthenticated
      });
      
      // Si no hay token nuevo y había uno anterior, desconectar
      if (!newToken && oldToken) {
        console.log('[SystemStatusBadge] Token eliminado, desconectando WebSocket...');
        disconnect();
        return;
      }
      
      // Si hay un token nuevo y el usuario está autenticado, conectar
      if (newToken && authStore.isAuthenticated) {
        console.log('[SystemStatusBadge] Token nuevo detectado, intentando conectar WebSocket...');
        connect(newToken).catch((err) => {
          const error = err instanceof Error ? err : new Error(String(err));
          console.error('[SystemStatusBadge] Error al conectar con el nuevo token:', error);
          lastError.value = error;
        });
      }
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error('[SystemStatusBadge] Error en el watch de token:', err);
      lastError.value = err;
    }
  },
  { immediate: true }
);

// Lifecycle hooks
onMounted(() => {
  connectIfAuthenticated();
});

// Cleanup on unmount
onUnmounted(() => {
  cleanup();
});
</script>

<style scoped>
.system-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-connected .status-dot {
  background-color: #10b981; /* Green */
}

.status-connecting .status-dot,
.status-reconnecting .status-dot {
  background-color: #f59e0b; /* Yellow */
  animation: pulse 2s infinite;
}

.status-error .status-dot {
  background-color: #ef4444; /* Red */
}

.status-disconnected .status-dot {
  background-color: #9ca3af; /* Gray */
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

.status-text {
  color: inherit;
}

/* Status colors */
.status-connected {
  color: #10b981;
  background-color: rgba(16, 185, 129, 0.1);
}

.status-connecting,
.status-reconnecting {
  color: #f59e0b;
  background-color: rgba(245, 158, 11, 0.1);
}

.status-error {
  color: #ef4444;
  background-color: rgba(239, 68, 68, 0.1);
}

.status-disconnected {
  color: #9ca3af;
  background-color: rgba(156, 163, 175, 0.1);
}
</style>