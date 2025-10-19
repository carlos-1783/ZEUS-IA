import { ref, onMounted, onUnmounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth';
import { useWebSocket } from './useWebSocket';
import type { 
  SystemStatus, 
  WebSocketMessage} from '../utils/types/websocket';

// Local type for status update event
interface StatusUpdateEvent {
  cpu_usage: number;
  memory_usage: number;
  storage_usage: number;
  network_usage: number;
  active_users: number;
  services: Record<string, 'online' | 'offline' | 'degraded'>;
  last_updated: string;
}

export function useRealtimeSystemV2() {
  const authStore = useAuthStore();
  const { token } = storeToRefs(authStore);
  
  // System status state
  const systemStatus = ref<SystemStatus>({
    cpu_usage: 0,
    memory_usage: 0,
    storage_usage: 0,
    network_usage: 0,
    active_users: 0,
    last_updated: new Date().toISOString(),
    services: {}
  });

  // Custom event handlers
  const eventHandlers = new Map<string, (data: any) => void>();

  // Initialize WebSocket connection
  const { 
    isConnected, 
    status: connectionStatus, 
    error: lastError, 
    connect, 
    disconnect, 
    send 
  } = useWebSocket({
    autoConnect: false, // We'll handle connection manually
    onMessage: (event) => {
      try {
        const message = event.data as WebSocketMessage;
        
        // Handle system status updates
        if (message.type === 'system_status') {
          const statusUpdate = message.data as StatusUpdateEvent;
          systemStatus.value = {
            ...statusUpdate,
            last_updated: new Date().toISOString()
          };
        }
        
        // Call any registered event handlers
        if (message.type && eventHandlers.has(message.type)) {
          const handler = eventHandlers.get(message.type)!;
          handler(message.data);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    },
    onConnect: () => {
      console.log('WebSocket connected, subscribing to system updates');
      // Subscribe to system updates
      send({
        type: 'subscribe',
        channel: 'system_status'
      }).catch(console.error);
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected');
    },
    onError: (event) => {
      console.error('WebSocket error:', event.data);
    }
  });

  // Watch for token changes and connect/disconnect accordingly
  watch(token, (newToken, oldToken) => {
    if (newToken && !oldToken) {
      // Token was just set, connect
      connect().catch(console.error);
    } else if (!newToken && oldToken) {
      // Token was removed, disconnect
      disconnect();
    }
  }, { immediate: true });

  // Connect on mount if we have a token
  onMounted(() => {
    if (token.value) {
      connect().catch(console.error);
    }
    
    // Return a cleanup function that doesn't return a value
    return () => {
      // Cleanup if needed
    };
  });

  // Clean up on unmount
  onUnmounted(() => {
    disconnect();
  });

  // Register an event handler for a specific message type
  const on = <T = any>(eventType: string, handler: (data: T) => void) => {
    eventHandlers.set(eventType, handler);
    
    // Return cleanup function
    return () => {
      eventHandlers.delete(eventType);
    };
  };

  // Send a custom message
  const sendMessage = async <T = any>(
    type: string, 
    data?: T
  ): Promise<void> => {
    const message: WebSocketMessage = { type, data };
    await send(message);
    // No return value needed as per Promise<void> return type
  };

  return {
    // State
    isConnected,
    connectionStatus,
    systemStatus,
    lastError,
    
    // Methods
    connect,
    disconnect,
    send: sendMessage,
    on,
    
    // Alias for backward compatibility
    sendMessage,
    
    // Computed properties for backward compatibility
    isConnectedComputed: isConnected,
    connectionStatusComputed: connectionStatus,
    systemStatusComputed: systemStatus,
    lastErrorComputed: lastError
  };
}

export default useRealtimeSystemV2;
