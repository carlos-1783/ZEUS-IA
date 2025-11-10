import { ref, readonly, onBeforeUnmount } from 'vue';
import { WebSocketEvents, type WebSocketEvent, type ConnectionStatus } from './types/websocket';
import config from '@/config';

type EventListener<T = any> = (event: WebSocketEvent<T>) => void;

// Estado reactivo
const status = ref<ConnectionStatus>('disconnected');
const isConnected = ref(false);
const error = ref<Error | null>(null);

// Instancia de WebSocket
let ws: WebSocket | null = null;

// Estado de reconexión
let reconnectAttempts = 0;
const maxReconnectAttempts = 3; // Reducir intentos de reconexión
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
let lastToken: string | null = null;
let heartbeatInterval: ReturnType<typeof setInterval> | null = null;

// Mapa de listeners de eventos
const listeners: Record<string, Set<EventListener>> = {};

// Inicializar listeners para cada tipo de evento
Object.values(WebSocketEvents).forEach(event => {
  listeners[event] = new Set();
});

// Función para limpiar recursos (no usar onBeforeUnmount aquí)
const cleanup = () => {
  if (ws) {
    ws.close(1000, 'Componente desmontado');
    ws = null;
  }
  
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
};

// Create the WebSocket service instance
const webSocketService = {
  // Métodos de manejo de eventos
  addEventListener<T = any>(
    event: WebSocketEvents | string,
    handler: EventListener<T>
  ): () => void {
    const eventType = event as WebSocketEvents;
    if (!listeners[eventType]) {
      listeners[eventType] = new Set();
    }
    listeners[eventType].add(handler as EventListener);
    
    return () => {
      this.removeEventListener(event, handler);
    };
  },
  
  removeEventListener<T = any>(
    event: WebSocketEvents | string,
    handler: EventListener<T>
  ): void {
    const eventType = event as WebSocketEvents;
    if (listeners[eventType]) {
      listeners[eventType].delete(handler as EventListener);
    }
  },
  
  // Emitir evento a los listeners registrados
  emit<T = any>(eventType: WebSocketEvents | string, data: T): void {
    const event: WebSocketEvent<T> = { 
      type: eventType, 
      data, 
      timestamp: new Date().toISOString()
    };
    
    const eventListeners = listeners[eventType as WebSocketEvents];
    if (eventListeners) {
      eventListeners.forEach(handler => {
        try {
          handler(event);
        } catch (err) {
          console.error(`Error en el manejador del evento ${eventType}:`, err);
        }
      });
    }
  },

  // Método privado para reconexión - OPTIMIZADO PARA EVITAR VIOLACIONES
  _scheduleReconnect(): void {
    if (reconnectAttempts >= maxReconnectAttempts) {
      console.error('Número máximo de intentos de reconexión alcanzado');
      status.value = 'error';
      return;
    }
    
    // REDUCIR DELAYS PARA EVITAR VIOLACIONES DE RENDIMIENTO
    const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 3000); // MÁXIMO 3 SEGUNDOS
    reconnectAttempts++;
    
    status.value = 'reconnecting';
    console.log(`Intentando reconectar en ${delay}ms (intento ${reconnectAttempts}/${maxReconnectAttempts})`);
    
    // USAR requestAnimationFrame PARA EVITAR BLOQUEOS
    reconnectTimeout = setTimeout(() => {
      requestAnimationFrame(() => {
        if (lastToken) {
          this.connect(lastToken).catch(err => {
            console.error('Error al reconectar:', err);
            if (reconnectAttempts < maxReconnectAttempts) {
              this._scheduleReconnect();
            }
          });
        }
      });
    }, delay);
  },

  // Conectar al WebSocket
  async connect(token: string): Promise<boolean> {
    try {
      // Cerrar conexión existente si la hay
      if (ws) {
        this.disconnect();
      }

      // Validar token
      if (!token || token.trim() === '') {
        throw new Error('No se proporcionó un token de autenticación válido');
      }

      // Verificar que el token no esté expirado (básico)
      try {
        const tokenPayload = JSON.parse(atob(token.split('.')[1]));
        const now = Math.floor(Date.now() / 1000);
        if (tokenPayload.exp && tokenPayload.exp < now) {
          throw new Error('El token de autenticación ha expirado');
        }
      } catch (err) {
        console.warn('No se pudo validar el token:', err);
        // Continuar con la conexión de todos modos
      }

      lastToken = token;
      status.value = 'connecting';
      error.value = null;
      
      // Generar un client_id único
      const clientId = `client-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      
      let wsUrl = (config.ws.url || '').trim();
      if (!wsUrl) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/api/v1/ws`;
      }
      const normalizedWsUrl = wsUrl.replace(/\/$/, '');

      // Añadir el token como query parameter
      const url = new URL(`${normalizedWsUrl}/${clientId}`);
      url.searchParams.set('token', token);

      return new Promise<boolean>((resolve, reject) => {
        console.log('Conectando a WebSocket:', url.toString());
        console.log('Token being sent:', token ? `${token.substring(0, 20)}...` : 'null');
        console.log('Client ID:', clientId);
        
        try {
          ws = new WebSocket(url.toString());
          
          // Asegurarse de que las credenciales se envíen
          ws.binaryType = 'arraybuffer';
          
          // Configurar timeout para la conexión - REDUCIDO PARA EVITAR VIOLACIONES
          const connectionTimeout = setTimeout(() => {
            if (ws && ws.readyState === WebSocket.CONNECTING) {
              console.warn('WebSocket connection timeout');
              ws.close(4000, 'Connection timeout');
              const errorMsg = 'Tiempo de conexión agotado';
              error.value = new Error(errorMsg);
              status.value = 'error';
              reject(new Error(errorMsg));
            }
          }, 5000); // REDUCIDO A 5 SEGUNDOS PARA EVITAR VIOLACIONES

          ws.onopen = () => {
            clearTimeout(connectionTimeout);
            console.log('✅ WebSocket connected successfully');
            console.log('WebSocket readyState:', ws?.readyState);
            console.log('WebSocket URL:', ws?.url);
            isConnected.value = true;
            status.value = 'connected';
            reconnectAttempts = 0; // Reset reconnection attempts on successful connection
            
            // Iniciar heartbeat para mantener la conexión activa
            this._startHeartbeat();
            
            this.emit(WebSocketEvents.CONNECT, { type: WebSocketEvents.CONNECT });
            resolve(true);
          };

          ws.onclose = (event) => {
            clearTimeout(connectionTimeout);
            console.log('❌ WebSocket closed', {
              code: event.code,
              reason: event.reason,
              wasClean: event.wasClean,
              type: event.type
            });
            isConnected.value = false;
            
            // Determinar el estado basado en el código de cierre
            if (event.code === 1000) {
              // Cierre normal
              status.value = 'disconnected';
            } else if (event.code === 4000) {
              // Timeout
              status.value = 'error';
              error.value = new Error('Tiempo de conexión agotado');
            } else if (event.code === 1006) {
              // Conexión cerrada anormalmente
              status.value = 'error';
              error.value = new Error('Conexión cerrada inesperadamente');
            } else if (event.code === 1008) {
              // Policy violation (token inválido)
              status.value = 'error';
              error.value = new Error('Token de autenticación inválido o expirado');
            } else {
              // Otros errores
              status.value = 'error';
              error.value = new Error(`Conexión cerrada con código: ${event.code}`);
            }
            
            // Only attempt to reconnect if this wasn't an intentional close or policy violation
            if (event.code !== 1000 && event.code !== 1001 && event.code !== 1008) {
              console.warn(`WebSocket closed unexpectedly: ${event.reason || 'Code: ' + event.code}`);
              error.value = new Error(`Conexión cerrada: ${event.reason || 'Código: ' + event.code}`);
              this._scheduleReconnect();
            }
            
            this.emit(WebSocketEvents.DISCONNECT, { 
              type: WebSocketEvents.DISCONNECT, 
              code: event.code,
              reason: event.reason,
              wasClean: event.wasClean
            });
          };

          ws.onerror = (errorEvent) => {
            console.error('🚨 WebSocket error:', errorEvent);
            console.error('WebSocket readyState during error:', ws?.readyState);
            console.error('WebSocket URL during error:', ws?.url);
            error.value = new Error('Error en la conexión WebSocket');
            this.emit(WebSocketEvents.ERROR, { 
              type: WebSocketEvents.ERROR, 
              error: errorEvent 
            });
            
            // Only reject if we're still in the connection phase
            if (status.value === 'connecting') {
              reject(new Error('Error en la conexión WebSocket'));
            }
          };

          ws.onmessage = (event) => {
            try {
              console.log('WebSocket message received:', event.data);
              const data = typeof event.data === 'string' 
                ? JSON.parse(event.data) 
                : event.data;
              this.emit(data.type || 'message', data);
            } catch (e) {
              console.error('Error al procesar mensaje WebSocket:', e, event.data);
            }
          };
        } catch (err) {
          console.error('Error creating WebSocket:', err);
          error.value = err instanceof Error ? err : new Error('Error al crear la conexión WebSocket');
          status.value = 'error';
          reject(err);
        }
      });
    } catch (err) {
      status.value = 'error';
      error.value = err instanceof Error ? err : new Error(String(err));
      throw error.value;
    }
  },

  // Desconectar el WebSocket
  disconnect(): void {
    // Detener heartbeat
    this._stopHeartbeat();
    
    if (ws) {
      try {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close(1000, 'User disconnected');
        }
        ws.onopen = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws = null;
      } catch (err) {
        console.error('Error al desconectar WebSocket:', err);
      }
    }
    
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    
    status.value = 'disconnected';
    isConnected.value = false;
  },

  // Enviar mensaje a través del WebSocket
  async send(data: unknown): Promise<void> {
    if (!ws) {
      throw new Error('WebSocket no inicializado');
    }
    
    if (ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket no está conectado');
    }
    
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    ws.send(message);
  },
  
  // Getters para el estado actual
  get currentStatus(): ConnectionStatus {
    return status.value;
  },
  
  get isConnected(): boolean {
    return isConnected.value;
  },
  
  get currentError(): Error | null {
    return error.value;
  },
  
  // Iniciar heartbeat
  _startHeartbeat() {
    // Limpiar heartbeat anterior si existe
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
    }
    
    // Performance: Heartbeat DESHABILITADO para evitar setInterval warnings
    // heartbeatInterval = setInterval(() => {
    //   if (ws && ws.readyState === WebSocket.OPEN) {
    //     try {
    //       ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
    //       console.log('📡 Heartbeat enviado');
    //     } catch (err) {
    //       console.error('Error enviando heartbeat:', err);
    //     }
    //   }
    // }, 30000); // 30 segundos
  },

  // Detener heartbeat
  _stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  },

  // Método de limpieza
  cleanup() {
    this._stopHeartbeat();
    cleanup();
  },

  // Composable para componentes Vue
  useWebSocket() {
    // Retornar función de limpieza para que el componente la use
    const componentCleanup = () => {
      // No desconectamos automáticamente, solo limpiamos listeners
      // para permitir que otros componentes sigan usando la conexión
      Object.values(WebSocketEvents).forEach(event => {
        listeners[event].clear();
      });
    };

    return {
      connect: webSocketService.connect.bind(webSocketService),
      disconnect: webSocketService.disconnect.bind(webSocketService),
      send: webSocketService.send.bind(webSocketService),
      addEventListener: webSocketService.addEventListener.bind(webSocketService),
      removeEventListener: webSocketService.removeEventListener.bind(webSocketService),
      cleanup: componentCleanup,
      status: readonly(status),
      isConnected: readonly(isConnected),
      error: readonly(error)
    };
  }
};

// Export the webSocketService as default
export default webSocketService;

// Export the useWebSocket function for direct import
export const useWebSocket = webSocketService.useWebSocket.bind(webSocketService);
