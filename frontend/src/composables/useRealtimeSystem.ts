import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth';
import { useWebSocket } from '../utils/WebSocketService';
import { 
  WebSocketEvents, 
  type WebSocketEvent, 
  type SystemStatus, 
  type WebSocketMessage, 
  type ConnectionStatus 
} from '../utils/types/websocket';

// Local type for status update event
interface StatusUpdateEvent {
  cpu_usage: number;
  memory_usage: number;
  storage_usage: number;
  network_usage: number;
  active_users: number;
  services: Record<string, 'online' | 'offline' | 'degraded'>;
}

export function useRealtimeSystem() {
  const authStore = useAuthStore();
  const { token } = storeToRefs(authStore);
  
  // Get WebSocket service instance
  const webSocketService = useWebSocket();
  let cleanupCallbacks: (() => void)[] = [];
  
  // Connection status
  const connectionStatus = ref<ConnectionStatus>('disconnected');
  const lastError = ref<Error | null>(null);
  
  // System status
  const systemStatus = ref<SystemStatus>({
    cpu_usage: 0,
    memory_usage: 0,
    storage_usage: 0,
    network_usage: 0,
    active_users: 0,
    last_updated: new Date().toISOString(),
    services: {}
  });
  
  // Reconnection logic
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  
  // Computed properties
  const isConnected = computed(() => connectionStatus.value === 'connected');
  const isConnecting = computed(() => connectionStatus.value === 'connecting');
  const hasError = computed(() => connectionStatus.value === 'error');

  // Handle WebSocket messages
  const handleMessage = (event: WebSocketEvent) => {
    try {
      const message = event.data as WebSocketMessage<StatusUpdateEvent>;
      
      if (message.type === 'status_update') {
        systemStatus.value = {
          ...systemStatus.value,
          ...message.data,
          last_updated: new Date().toISOString()
        };
      }
      
      console.debug('WebSocket message received:', message);
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
      lastError.value = error instanceof Error ? error : new Error(String(error));
    }
  };

  // Connection event handlers
  const handleConnected = () => {
    console.log('WebSocket connected');
    connectionStatus.value = 'connected';
    lastError.value = null;
    reconnectAttempts.value = 0; // Reset reconnect attempts on successful connection
  };

  const handleDisconnected = (event: WebSocketEvent) => {
    const closeEvent = event.data as CloseEvent;
    console.log('[WebSocket] Disconnected', closeEvent?.reason || '');
    connectionStatus.value = 'disconnected';
    
    // Only attempt to reconnect if we have a token and haven't exceeded max attempts
    if (token && token.value && reconnectAttempts.value < maxReconnectAttempts) {
      reconnect();
    }
  };

  const handleError = (error: unknown) => {
    console.error('WebSocket error:', error);
    connectionStatus.value = 'error';
    lastError.value = error instanceof Error ? error : new Error(String(error));
  };

  // Reconnect logic
  const reconnect = async () => {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      console.warn('Max reconnection attempts reached');
      return;
    }
    
    if (connectionStatus.value === 'connected' || connectionStatus.value === 'connecting') {
      return; // Already connected or connecting
    }
    
    console.log(`Attempting to reconnect (${reconnectAttempts.value + 1}/${maxReconnectAttempts})...`);
    connectionStatus.value = 'connecting';
    reconnectAttempts.value++;
    
    try {
      cleanupWebSocketConnection();
      setupWebSocket();
    } catch (error) {
      console.error('Reconnection failed:', error);
      lastError.value = error instanceof Error ? error : new Error(String(error));
      connectionStatus.value = 'error';
      
      // Schedule next reconnection attempt
      if (reconnectAttempts.value < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 30000);
        setTimeout(reconnect, delay);
      }
    }
  };

  // Setup WebSocket connection
  const setupWebSocket = () => {
    if (!token || !token.value) {
      console.warn('No authentication token available for WebSocket connection');
      return;
    }

    try {
      // Connect to WebSocket
      webSocketService.connect(token.value);
      
      // Set up event listeners with proper WebSocketEvents enum values
      const cleanupMessage = webSocketService.addEventListener(WebSocketEvents.MESSAGE, handleMessage);
      const cleanupConnect = webSocketService.addEventListener(WebSocketEvents.CONNECT, () => {
        handleConnected();
        return () => {}; // No-op cleanup
      });
      const cleanupDisconnect = webSocketService.addEventListener(WebSocketEvents.DISCONNECT, handleDisconnected);
      const cleanupError = webSocketService.addEventListener(WebSocketEvents.ERROR, (event) => {
        handleError(event.data);
      });
      
      // Store cleanup callbacks
      cleanupCallbacks = [
        cleanupMessage,
        cleanupConnect,
        cleanupDisconnect,
        cleanupError
      ];
      
      // Initial connection status
      if (webSocketService.isConnected?.value) {
        handleConnected();
      } else {
        connectionStatus.value = 'connecting';
      }
    } catch (error) {
      console.error('Failed to set up WebSocket:', error);
      handleError(error instanceof Error ? error : new Error(String(error)));
    }
  };

  // Clean up WebSocket connection
  const cleanupWebSocketConnection = () => {
    try {
      // Call all cleanup callbacks
      cleanupCallbacks.forEach(cleanup => cleanup());
      cleanupCallbacks = [];
      
      if (webSocketService.isConnected?.value) {
        webSocketService.disconnect();
      }
    } catch (error) {
      console.error('Error during WebSocket cleanup:', error);
    }
  };

  // Watch for token changes to reconnect
  const stopTokenWatch = watch(
    () => (token ? token.value : undefined),
    (newToken, oldToken) => {
      if (newToken && newToken !== oldToken) {
        // Token changed, reconnect
        reconnect();
      } else if (!newToken && oldToken) {
        // Token was removed, disconnect
        cleanupWebSocketConnection();
      }
    },
    { immediate: true }
  );

  // Initialize on mount
  onMounted(() => {
    if (token && token.value) {
      setupWebSocket();
    }
  });
  
  // Clean up on unmount
  onUnmounted(() => {
    cleanupWebSocketConnection();
    stopTokenWatch();
  });

  // Expose reactive state and methods
  return {
    // State
    connectionStatus,
    systemStatus,
    lastError,
    
    // Computed
    isConnected,
    isConnecting,
    hasError,
    
    // Methods
    reconnect,
    forceReconnect: () => {
      reconnectAttempts.value = 0;
      reconnect();
    },
    
    // WebSocket service reference (exposed for testing)
    _webSocketService: webSocketService
  };
}

// Re-export types and WebSocket events
export type { WebSocketEvent, SystemStatus, WebSocketMessage, ConnectionStatus };
export { WebSocketEvents };

// Export the composable function
export default useRealtimeSystem;
