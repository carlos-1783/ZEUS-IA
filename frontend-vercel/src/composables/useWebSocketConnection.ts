import { ref, onUnmounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useWebSocket } from '@/utils/WebSocketService';

export function useWebSocketConnection() {
  const authStore = useAuthStore();
  const { connect, disconnect, isConnected, status, error } = useWebSocket();
  const isConnecting = ref(false);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  let reconnectTimeout: number | null = null;

  const initializeConnection = async () => {
    if (isConnecting.value || isConnected.value) {
      return;
    }

    const token = authStore.token;
    if (!token) {
      console.warn('[useWebSocket] No authentication token available');
      return;
    }

    try {
      isConnecting.value = true;
      console.log('[useWebSocket] Connecting to WebSocket...');
      
      const connected = await connect(token);
      
      if (connected) {
        console.log('[useWebSocket] WebSocket connected successfully');
        reconnectAttempts.value = 0;
      } else {
        console.warn('[useWebSocket] Failed to connect to WebSocket');
        scheduleReconnect();
      }
    } catch (err) {
      console.error('[useWebSocket] Error connecting to WebSocket:', err);
      scheduleReconnect();
    } finally {
      isConnecting.value = false;
    }
  };

  const scheduleReconnect = () => {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      console.warn('[useWebSocket] Max reconnection attempts reached');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 30000);
    reconnectAttempts.value++;

    console.log(`[useWebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`);
    
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
    }
    
    reconnectTimeout = window.setTimeout(() => {
      initializeConnection();
    }, delay);
  };

  const cleanup = () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    disconnect();
  };

  onUnmounted(() => {
    cleanup();
  });

  return {
    isConnected,
    status,
    error,
    initializeConnection,
    cleanup
  };
}
