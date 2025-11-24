<template>
  <div class="websocket-test">
    <h1>WebSocket Connection Test</h1>
    
    <div class="connection-status">
      <h3>Connection Status:</h3>
      <div class="status-indicator" :class="statusClass">
        {{ connectionStatus }}
      </div>
      <button 
        @click="toggleConnection" 
        :disabled="isConnecting"
        class="connect-btn"
      >
        {{ isConnected ? 'Disconnect' : 'Connect' }}
      </button>
      <button 
        @click="sendTestMessage" 
        :disabled="!isConnected"
        class="test-btn"
      >
        Send Test Message
      </button>
    </div>

    <div class="message-log">
      <h3>Message Log:</h3>
      <div class="log-entries">
        <div 
          v-for="(entry, index) in messageLog" 
          :key="index"
          class="log-entry"
          :class="entry.type"
        >
          <span class="timestamp">[{{ entry.timestamp }}]</span>
          <span class="message">{{ entry.message }}</span>
          <span v-if="entry.error" class="error">Error: {{ entry.error }}</span>
        </div>
      </div>
    </div>

    <div class="token-info" v-if="authStore.token">
      <h3>JWT Token:</h3>
      <div class="token-preview">
        {{ tokenPreview }}
      </div>
      <button 
        @click="copyToken"
        class="copy-btn"
      >
        Copy Token
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useWebSocket } from '@/utils/WebSocketService';
import { getWebSocketUrl } from '@/config';

const authStore = useAuthStore();
const messageLog = ref<Array<{
  type: 'info' | 'sent' | 'received' | 'error';
  message: string;
  timestamp: string;
  error?: string;
}>>([]);

const WEBSOCKET_BASE_URL = getWebSocketUrl();

const {
  status: connectionStatus,
  isConnected,
  connect,
  disconnect,
  error: socketError
} = useWebSocket();

// Get the WebSocket instance for sending messages
const socket = ref<WebSocket | null>(null);

// Watch for connection status changes to get the socket instance
watch(connectionStatus, (newStatus) => {
  if (newStatus === 'connected' && !socket.value) {
    // Store the socket instance when connected
    socket.value = new WebSocket(`${WEBSOCKET_BASE_URL}?token=${authStore.token}`);
  } else if (newStatus === 'disconnected' || newStatus === 'error') {
    socket.value = null;
  }
  
  if (newStatus === 'connected') {
    logMessage('WebSocket connected successfully', 'info');
  } else if (newStatus === 'disconnected') {
    logMessage('WebSocket disconnected', 'info');
  } else if (newStatus === 'error') {
    logMessage('WebSocket connection error', 'error');
  }
});

const isConnecting = ref(false);

const statusClass = computed(() => ({
  'status-connected': isConnected.value,
  'status-connecting': isConnecting.value,
  'status-disconnected': !isConnected.value && !isConnecting.value
}));

const tokenPreview = computed(() => {
  if (!authStore.token) return 'No token available';
  const token = authStore.token;
  return `${token.substring(0, 15)}...${token.substring(token.length - 15)}`;
});

const logMessage = (message: string, type: 'info' | 'sent' | 'received' | 'error' = 'info', error?: unknown) => {
  const entry = {
    type,
    message,
    timestamp: new Date().toISOString().split('T')[1].split('.')[0],
    error: error instanceof Error ? error.message : String(error)
  };
  messageLog.value.unshift(entry);
  console.log(`[${entry.type}] ${entry.message}`, error || '');
};

// Connection status changes are now handled in the watcher above

const toggleConnection = () => {
  console.log("Token en authStore en toggleConnection (WebSocketTest):", authStore.token);
  if (isConnected.value) {
    disconnect();
  } else {
    connect(authStore.token);
  }
};

const sendTestMessage = () => {
  if (!isConnected.value || !socket.value) {
    logMessage('Not connected to WebSocket server', 'error');
    return;
  }
  
  const testMessage = {
    type: 'test',
    data: 'This is a test message',
    timestamp: new Date().toISOString()
  };
  
  try {
    socket.value.send(JSON.stringify(testMessage));
    logMessage(`Sent: ${JSON.stringify(testMessage)}`, 'sent');
  } catch (err) {
    logMessage('Failed to send message', 'error', err);
  }
};

const copyToken = async () => {
  if (!authStore.token) return;
  
  try {
    await navigator.clipboard.writeText(authStore.token);
    logMessage('Token copied to clipboard', 'info');
  } catch (error) {
    logMessage('Failed to copy token', 'error', error);
  }
};

watch(socketError, (newError) => {
  if (newError) {
    logMessage(`Error: ${newError.message}`, 'error');
  }
});

onMounted(() => {
  console.log("Token en authStore antes de conectar (WebSocketTest):", authStore.token);
  connect(authStore.token);
});

onUnmounted(() => {
  disconnect();
});

onMounted(() => {
  if (authStore.isAuthenticated) {
    logMessage('User is authenticated, ready to connect', 'info');
  } else {
    logMessage('User is not authenticated. Please log in to test WebSocket connection.', 'error');
  }
});
</script>

<style scoped>
.websocket-test {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

h1 {
  color: #2c3e50;
  margin-bottom: 24px;
  text-align: center;
}

.connection-status {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.status-indicator {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 16px;
  font-weight: 600;
  margin: 10px 0;
  color: white;
}

.status-connected {
  background-color: #10b981;
}

.status-connecting {
  background-color: #f59e0b;
  animation: pulse 2s infinite;
}

.status-disconnected {
  background-color: #ef4444;
}

button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  margin-right: 10px;
  transition: all 0.2s;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.connect-btn {
  background-color: #3b82f6;
  color: white;
}

.connect-btn:not(:disabled):hover {
  background-color: #2563eb;
}

.test-btn {
  background-color: #10b981;
  color: white;
}

.test-btn:not(:disabled):hover {
  background-color: #059669;
}

.copy-btn {
  background-color: #8b5cf6;
  color: white;
  margin-top: 10px;
}

.copy-btn:hover {
  background-color: #7c3aed;
}

.message-log {
  background-color: #1e293b;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Courier New', Courier, monospace;
}

.log-entries {
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
}

.log-entry {
  padding: 8px 12px;
  border-radius: 4px;
  background-color: #334155;
  font-size: 14px;
  word-break: break-word;
}

.log-entry.sent {
  border-left: 3px solid #3b82f6;
}

.log-entry.received {
  border-left: 3px solid #10b981;
}

.log-entry.error {
  border-left: 3px solid #ef4444;
  color: #fca5a5;
}

.timestamp {
  color: #94a3b8;
  margin-right: 8px;
  font-size: 0.9em;
}

.token-info {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-top: 20px;
}

.token-preview {
  font-family: 'Courier New', Courier, monospace;
  background-color: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 4px;
  margin: 10px 0;
  word-break: break-all;
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>
