<template>
  <div class="p-4 max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">WebSocket Connection Tester</h1>
    
    <!-- Token Information -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg border">
      <h2 class="text-lg font-semibold mb-2">Authentication Token</h2>
      <div class="text-sm mb-2">
        <span class="font-medium">Has Token:</span> 
        <span :class="{ 'text-green-600': authStore.token, 'text-red-600': !authStore.token }">
          {{ authStore.token ? 'Yes' : 'No' }}
        </span>
      </div>
      <div v-if="authStore.token" class="text-xs overflow-x-auto p-2 bg-gray-100 rounded">
        <div class="font-mono break-all">{{ authStore.token }}</div>
      </div>
      <div v-else class="text-yellow-600 text-sm">
        Please log in first to test WebSocket connection
      </div>
    </div>
    
    <div class="mb-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div class="p-4 bg-white rounded-lg border">
          <h3 class="font-semibold mb-2">Connection Status</h3>
          <div class="flex items-center gap-2">
            <span class="font-medium">Status:</span>
            <span :class="{
              'text-green-600': status === 'connected',
              'text-yellow-600': status === 'connecting' || status === 'reconnecting',
              'text-red-600': status === 'disconnected' || status === 'error'
            }">
              {{ status }}
            </span>
            <span v-if="isConnected" class="h-3 w-3 rounded-full bg-green-500"></span>
            <span v-else class="h-3 w-3 rounded-full bg-red-500"></span>
          </div>
          <div class="mt-2 text-sm text-gray-600">
            <div>Client ID: {{ clientId || 'N/A' }}</div>
            <div>Last error: {{ lastError || 'None' }}</div>
          </div>
        </div>
        
        <div class="p-4 bg-white rounded-lg border">
          <h3 class="font-semibold mb-2">Connection Details</h3>
          <div class="space-y-1 text-sm">
            <div><span class="font-medium">WebSocket URL:</span> 
              <span class="text-blue-600 font-mono text-xs">{{ wsUrl || 'Not connected' }}</span>
            </div>
            <div><span class="font-medium">Last Activity:</span> {{ lastActivity || 'Never' }}</div>
            <div><span class="font-medium">Messages Sent:</span> {{ messageCount.sent }}</div>
            <div><span class="font-medium">Messages Received:</span> {{ messageCount.received }}</div>
          </div>
        </div>
      </div>
      
      <div class="flex flex-wrap gap-2 mb-4">
        <button 
          @click="connectWebSocket" 
          :disabled="isConnected || isLoading || !authStore.token" 
          class="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          title="Connect to WebSocket server"
        >
          {{ isLoading ? 'Connecting...' : 'Connect' }}
        </button>
        <button 
          @click="disconnectWebSocket" 
          :disabled="!isConnected" 
          class="px-4 py-2 bg-red-600 text-white rounded disabled:opacity-50"
          title="Disconnect from WebSocket server"
        >
          Disconnect
        </button>
        <button 
          @click="testAuthentication" 
          :disabled="!isConnected" 
          class="px-4 py-2 bg-green-600 text-white rounded disabled:opacity-50"
          title="Test WebSocket authentication"
        >
          Test Auth
        </button>
        <button 
          @click="clearMessages" 
          class="px-4 py-2 bg-gray-600 text-white rounded"
          title="Clear message log"
        >
          Clear Log
        </button>
      </div>
      
      <div class="mt-4">
        <div class="flex gap-2 mb-2">
          <input 
            v-model="message" 
            type="text" 
            placeholder="Type a message..." 
            class="flex-1 p-2 border rounded"
            @keyup.enter="sendMessage"
          >
          <button 
            @click="sendMessage" 
            :disabled="!isConnected" 
            class="px-4 py-2 bg-green-600 text-white rounded disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
    
    <div class="mt-6">
      <div class="flex justify-between items-center mb-2">
        <h2 class="text-xl font-semibold">Message Log</h2>
        <div class="text-sm text-gray-500">
          Showing {{ filteredMessages.length }} of {{ messages.length }} messages
        </div>
      </div>
      
      <div class="border rounded p-4 h-96 overflow-y-auto bg-gray-50">
        <div v-if="messages.length === 0" class="text-gray-500 text-center py-8">
          No messages yet. Connect and send a message!
        </div>
        
        <div v-else>
          <div v-for="(msg, index) in filteredMessages" :key="index" 
               class="mb-3 p-3 bg-white rounded border hover:shadow transition-shadow"
               :class="{ 
                 'border-green-200': msg.direction === 'in', 
                 'border-blue-200': msg.direction === 'out',
                 'border-red-200': msg.type === 'error'
               }">
            <div class="flex justify-between text-xs text-gray-500 mb-1">
              <span>{{ msg.timestamp }}</span>
              <span class="font-mono px-2 py-0.5 rounded" 
                    :class="{
                      'bg-green-100 text-green-800': msg.direction === 'in',
                      'bg-blue-100 text-blue-800': msg.direction === 'out',
                      'bg-red-100 text-red-800': msg.type === 'error'
                    }">
                {{ (msg.type || 'info').toUpperCase() }}
              </span>
            </div>
            <div class="font-mono text-sm break-words"
                 :class="{
                   'text-green-700': msg.direction === 'in',
                   'text-blue-700': msg.direction === 'out',
                   'text-red-700': msg.type === 'error'
                 }">
              <pre v-if="typeof msg.data === 'object'">{{ JSON.stringify(msg.data, null, 2) }}</pre>
              <template v-else>{{ msg.text || msg.data || 'No content' }}</template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, type Ref } from 'vue';
import { useWebSocket } from '@/utils/WebSocketService';
import { useAuthStore } from '@/stores/auth';
import type { WebSocketEvent } from '@/utils/types/websocket';
import { WebSocketEvents } from '@/utils/types/websocket';
import { getWebSocketUrl } from '@/config';

const authStore = useAuthStore();
const webSocket = useWebSocket();
const { 
  status, 
  isConnected, 
  connect, 
  disconnect, 
  send, 
  error: wsError
} = webSocket;

// Get clientId from the webSocket instance if it exists
const clientId = ref<string>('');

// Watch for clientId changes if it's a ref
if ('clientId' in webSocket && webSocket.clientId) {
  const clientIdSource = webSocket.clientId as Ref<string> | Readonly<Ref<string>>;
  watch(clientIdSource, (newId) => {
    clientId.value = newId;
  });
}

// State
const message = ref('');
const messages = ref<Array<{ 
  text?: string; 
  data?: any;
  direction?: 'in' | 'out'; 
  timestamp: string;
  type?: 'info' | 'error' | 'auth' | 'message';
}>>([]);

const isLoading = ref(false);
const lastError = ref<string | null>(null);
const lastActivity = ref<string | null>(null);
const wsUrl = ref<string | null>(null);
const messageCount = ref({ sent: 0, received: 0 });

// Computed
const filteredMessages = computed(() => {
  return [...messages.value].reverse(); // Show newest first
});

// Add a message to the log
const addMessage = (
  content: string | any, 
  direction: 'in' | 'out' = 'in', 
  type: 'info' | 'error' | 'auth' | 'message' = 'info'
) => {
  const timestamp = new Date().toLocaleString();
  
  // Update last activity
  lastActivity.value = timestamp;
  
  // Add to messages
  const message = {
    timestamp,
    type,
    direction,
    ...(typeof content === 'string' ? { text: content } : { data: content })
  };
  
  messages.value.push(message);
  
  // Update message count
  if (direction === 'out') {
    messageCount.value.sent++;
  } else {
    messageCount.value.received++;
  }
  
  // Auto-scroll to bottom
  setTimeout(() => {
    const container = document.querySelector('.overflow-y-auto');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, 50);
};

const connectWebSocket = async () => {
  if (!authStore.token) {
    addMessage('Error: No authentication token available. Please log in first.', 'in', 'error');
    return false;
  }
  
  try {
    isLoading.value = true;
    lastError.value = null;
    
    // Log connection attempt
    addMessage(`Connecting to WebSocket server...`, 'out', 'info');
    
    // Store the WebSocket URL for display
    const baseUrl = getWebSocketUrl();
    const cleanBaseUrl = baseUrl.replace(/\/$/, '');
    wsUrl.value = clientId.value ? `${cleanBaseUrl}/${clientId.value}` : cleanBaseUrl;
    
    // Connect with the token
    const success = await connect(authStore.token);
    
    if (success) {
      addMessage('Successfully connected to WebSocket server', 'in', 'info');
      
      // Test authentication after a short delay
      setTimeout(() => {
        testAuthentication();
      }, 500);
    } else {
      addMessage('Failed to connect to WebSocket server', 'in', 'error');
    }
    
    return success;
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error('WebSocket connection error:', error);
    lastError.value = errorMsg;
    addMessage(`Connection error: ${errorMsg}`, 'in', 'error');
    return false;
  } finally {
    isLoading.value = false;
  }
};

const disconnectWebSocket = () => {
  try {
    disconnect();
    addMessage('Disconnected from WebSocket server', 'in', 'info');
    wsUrl.value = null;
    return true;
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    addMessage(`Disconnection error: ${errorMsg}`, 'in', 'error');
    return false;
  }
};

const sendMessage = () => {
  if (!message.value.trim() || !isConnected.value) return;
  
  const msg = message.value;
  try {
    send({
      type: 'test_message',
      content: msg,
      timestamp: new Date().toISOString()
    });
    
    addMessage(msg, 'out', 'message');
    message.value = '';
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Failed to send message';
    addMessage(`Error sending message: ${errorMsg}`, 'in', 'error');
  }
};

// Test WebSocket authentication
const testAuthentication = async () => {
  if (!isConnected.value) {
    addMessage('Not connected to WebSocket server', 'in', 'error');
    return false;
  }
  
  try {
    const testMsg = {
      type: 'auth_test',
      timestamp: new Date().toISOString()
    };
    
    addMessage('Sending authentication test message...', 'out', 'auth');
    send(testMsg);
    return true;
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Failed to send auth test';
    addMessage(`Auth test error: ${errorMsg}`, 'in', 'error');
    return false;
  }
};

// Clear all messages
const clearMessages = () => {
  messages.value = [];
  messageCount.value = { sent: 0, received: 0 };
};

// Handle incoming WebSocket messages
const handleMessage = (event: WebSocketEvent) => {
  try {
    console.log('[WebSocket] Message received:', event);
    
    // Handle different types of messages
    if (event.type === 'auth_response') {
      if (event.data.authenticated) {
        addMessage('Successfully authenticated with WebSocket server', 'in', 'auth');
      } else {
        const errorMsg = event.data.error || 'Authentication failed';
        addMessage(`Authentication error: ${errorMsg}`, 'in', 'error');
      }
    } else if (event.type === 'error') {
      addMessage(`Server error: ${event.data?.message || 'Unknown error'}`, 'in', 'error');
    } else {
      // Regular message
      addMessage(event.data, 'in', 'message');
    }
  } catch (error) {
    console.error('Error handling WebSocket message:', error);
    addMessage(
      `Error processing message: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'in',
      'error'
    );
  }
};

// Watch for WebSocket status changes
watch(status, (newStatus: string) => {
  addMessage(`Connection status changed to: ${newStatus}`, 'in', 'info');
  
  if (newStatus === 'connected') {
    lastActivity.value = new Date().toISOString();
  } else if (newStatus === 'error' && wsError.value) {
    lastError.value = typeof wsError.value === 'string' ? wsError.value : 'Unknown WebSocket error';
    addMessage(`WebSocket error: ${lastError.value}`, 'in', 'error');
  }
});

// Watch for connection state changes
watch(isConnected, (connected: boolean) => {
  if (connected) {
    addMessage('WebSocket connected successfully', 'in', 'info');
  } else if (status.value !== 'connecting') {
    addMessage('WebSocket disconnected', 'in', 'info');
  }
});

// Initialize component
onMounted(() => {
  // Add message listener when component is mounted
  const { addEventListener } = useWebSocket();
  addEventListener(WebSocketEvents.MESSAGE, handleMessage);
  
  // Log initial state
  addMessage('WebSocket test component initialized', 'in', 'info');
  
  // Auto-connect if we have a token
  if (authStore.token) {
    connectWebSocket();
  }
});

// Clean up on unmount
onUnmounted(() => {
  const { removeEventListener } = useWebSocket();
  removeEventListener(WebSocketEvents.MESSAGE, handleMessage);
  
  // Disconnect when component is unmounted
  if (isConnected.value) {
    disconnectWebSocket();
  }
});
</script>
