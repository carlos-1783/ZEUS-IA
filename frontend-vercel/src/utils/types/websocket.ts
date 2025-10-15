// WebSocket types
import type { Ref } from 'vue';

// System status type
export interface SystemStatus {
  cpu_usage: number;
  memory_usage: number;
  storage_usage: number;
  network_usage: number;
  active_users: number;
  last_updated: string;
  services: Record<string, 'online' | 'offline' | 'degraded'>;
}

// WebSocket message type
export interface WebSocketMessage<T = any> {
  type: string;
  data: T;
  timestamp?: number;
  [key: string]: any; // Allow additional properties
}

// WebSocket event type
export interface WebSocketEvent<T = any> {
  type: string;
  data: T;
  timestamp?: string;
  code?: string | number;
  reason?: string;
  wasClean?: boolean;
  clientId?: string;
  [key: string]: any; // Allow additional properties
}

// WebSocket event types
export enum WebSocketEvents {
  // Connection events
  CONNECT = 'connect',
  DISCONNECT = 'disconnect',
  RECONNECT = 'reconnect',
  RECONNECTING = 'reconnecting',
  
  // Message events
  MESSAGE = 'message',
  SYSTEM_STATUS = 'system_status',
  AUTH_RESPONSE = 'auth_response',
  
  // Error events
  ERROR = 'error',
  AUTH_ERROR = 'auth_error',
  CONNECTION_ERROR = 'connection_error',
  
  // Status updates
  STATUS_UPDATE = 'status_update',
  
  // Custom events
  CUSTOM = 'custom'
}

// Connection status type
export type ConnectionStatus = 
  | 'disconnected'  // Not connected
  | 'connecting'    // Connection in progress
  | 'connected'     // Successfully connected and authenticated
  | 'reconnecting'  // Attempting to reconnect
  | 'error';        // Connection error occurred

// WebSocket service interface
export interface WebSocketService {
  // Connection state
  status: Ref<ConnectionStatus>;
  isConnected: Ref<boolean>;
  error: Ref<Error | null>;
  clientId: string;
  
  // Connection management
  connect: (token: string) => Promise<boolean>;
  disconnect: () => void;
  
  // Message handling
  send: (data: unknown) => Promise<void>;
  
  // Event handling
  addEventListener: <T = any>(
    event: WebSocketEvents | string, 
    handler: (event: WebSocketEvent<T>) => void
  ) => void;
  
  removeEventListener: <T = any>(
    event: WebSocketEvents | string, 
    handler: (event: WebSocketEvent<T>) => void
  ) => void;
}
