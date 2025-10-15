import { ref, onUnmounted } from 'vue';
import { WebSocketEvents, type WebSocketEvent } from '../utils/types/websocket';
import webSocketService from '../utils/WebSocketServiceV2';
import { tokenService } from '../api';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  onMessage?: (event: WebSocketEvent) => void;
  onConnect?: (event: WebSocketEvent) => void;
  onDisconnect?: (event: WebSocketEvent) => void;
  onError?: (event: WebSocketEvent) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { 
    autoConnect = true,
    onMessage,
    onConnect,
    onDisconnect,
    onError 
  } = options;

  const isConnected = ref(webSocketService.isConnected);
  const status = ref(webSocketService.status);
  const error = ref(webSocketService.error);
  const clientId = ref(webSocketService.clientId);

  // Message handler
  const handleMessage = (event: WebSocketEvent) => {
    onMessage?.(event);
  };

  // Connect handler
  const handleConnect = (event: WebSocketEvent) => {
    isConnected.value = true;
    status.value = 'connected';
    onConnect?.(event);
  };

  // Disconnect handler
  const handleDisconnect = (event: WebSocketEvent) => {
    isConnected.value = false;
    status.value = 'disconnected';
    onDisconnect?.(event);
  };

  // Error handler
  const handleError = (event: WebSocketEvent) => {
    error.value = event.data?.error || new Error('WebSocket error occurred');
    onError?.(event);
  };

  // Connect to WebSocket
  const connect = async () => {
    if (!tokenService.getToken()) {
      console.warn('[useWebSocket] No authentication token available');
      return false;
    }

    try {
      await webSocketService.connect();
      return true;
    } catch (err) {
      console.error('[useWebSocket] Connection error:', err);
      error.value = err instanceof Error ? err : new Error('Failed to connect to WebSocket');
      return false;
    }
  };

  // Disconnect from WebSocket
  const disconnect = () => {
    webSocketService.disconnect();
  };

  // Send message
  const send = async (data: unknown) => {
    try {
      await webSocketService.send(data);
      return true;
    } catch (err) {
      console.error('[useWebSocket] Send error:', err);
      error.value = err instanceof Error ? err : new Error('Failed to send message');
      return false;
    }
  };

  // Set up event listeners
  const setupListeners = () => {
    webSocketService.addEventListener(WebSocketEvents.MESSAGE, handleMessage);
    webSocketService.addEventListener(WebSocketEvents.CONNECT, handleConnect);
    webSocketService.addEventListener(WebSocketEvents.DISCONNECT, handleDisconnect);
    webSocketService.addEventListener(WebSocketEvents.ERROR, handleError);
    webSocketService.addEventListener(WebSocketEvents.STATUS_UPDATE, (event) => {
      status.value = event.data.status;
    });
  };

  // Clean up event listeners
  const cleanupListeners = () => {
    webSocketService.removeEventListener(WebSocketEvents.MESSAGE, handleMessage);
    webSocketService.removeEventListener(WebSocketEvents.CONNECT, handleConnect);
    webSocketService.removeEventListener(WebSocketEvents.DISCONNECT, handleDisconnect);
    webSocketService.removeEventListener(WebSocketEvents.ERROR, handleError);
  };

  // Initialize
  setupListeners();

  // Auto-connect if enabled
  if (autoConnect) {
    connect().catch(console.error);
  }

  // Clean up on component unmount
  onUnmounted(() => {
    cleanupListeners();
    disconnect();
  });

  return {
    // State
    isConnected,
    status,
    error,
    clientId,
    
    // Methods
    connect,
    disconnect,
    send,
    
    // Raw service for advanced usage
    service: webSocketService
  };
}

export default useWebSocket;
