<template>
  <div class="p-4 max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">WebSocket Connection Tester</h1>
    
    <!-- Token Information -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg border">
      <h2 class="text-lg font-semibold mb-2">Authentication Token</h2>
      <div class="text-sm mb-2">
        <span class="font-medium">Has Token:</span> 
        <span :class="{ 'text-green-600': hasToken, 'text-red-600': !hasToken }">
          {{ hasToken ? 'Yes' : 'No' }}
        </span>
      </div>
      <div v-if="hasToken" class="text-xs overflow-x-auto p-2 bg-gray-100 rounded">
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
              'text-green-600': isConnected,
              'text-yellow-600': connectionStatus === 'connecting' || connectionStatus === 'reconnecting',
              'text-red-600': !isConnected && connectionStatus !== 'connecting' && connectionStatus !== 'reconnecting'
            }">
              {{ connectionStatus }}
            </span>
            <span v-if="isConnected" class="h-3 w-3 rounded-full bg-green-500"></span>
            <span v-else class="h-3 w-3 rounded-full bg-red-500"></span>
          </div>
          <div class="mt-2 text-sm text-gray-600">
            <div>Client ID: {{ clientId || 'N/A' }}</div>
            <div>Last error: {{ lastError?.message || 'None' }}</div>
          </div>
        </div>
        
        <div class="p-4 bg-white rounded-lg border">
          <h3 class="font-semibold mb-2">Connection Controls</h3>
          <div class="flex flex-wrap gap-2">
            <button
              @click="connect"
              :disabled="isConnected || !hasToken"
              :class="[
                'px-3 py-1.5 text-sm rounded',
                isConnected || !hasToken
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              ]"
            >
              Connect
            </button>
            <button
              @click="disconnect"
              :disabled="!isConnected"
              :class="[
                'px-3 py-1.5 text-sm rounded',
                !isConnected
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'bg-red-500 text-white hover:bg-red-600'
              ]"
            >
              Disconnect
            </button>
            <button
              @click="testAuthentication"
              :disabled="!isConnected"
              :class="[
                'px-3 py-1.5 text-sm rounded',
                !isConnected
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'bg-green-500 text-white hover:bg-green-600'
              ]"
            >
              Test Auth
            </button>
            <button
              @click="clearMessages"
              class="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded"
            >
              Clear Log
            </button>
          </div>
        </div>
      </div>
      
      <!-- Message Input -->
      <div class="mb-4">
        <div class="flex gap-2">
          <input
            v-model="messageInput"
            type="text"
            placeholder="Type a message to send..."
            class="flex-1 p-2 border rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            :disabled="!isConnected"
            @keyup.enter="sendMessage"
          />
          <button
            @click="sendMessage"
            :disabled="!isConnected || !messageInput.trim()"
            :class="[
              'px-4 py-2 rounded',
              !isConnected || !messageInput.trim()
                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                : 'bg-blue-500 text-white hover:bg-blue-600'
            ]"
          >
            Send
          </button>
        </div>
      </div>
    </div>
    
    <!-- Message Log -->
    <div class="mt-6">
      <div class="flex justify-between items-center mb-2">
        <h2 class="text-xl font-semibold">Message Log</h2>
        <div class="text-sm text-gray-500">
          Showing {{ filteredMessages.length }} message{{ filteredMessages.length !== 1 ? 's' : '' }}
        </div>
      </div>
      
      <div class="bg-gray-50 rounded-lg border h-96 overflow-y-auto p-4 space-y-2">
        <div v-if="filteredMessages.length === 0" class="text-gray-500 text-center py-8">
          No messages to display
        </div>
        
        <div 
          v-for="(msg, index) in filteredMessages" 
          :key="index"
          :class="[
            'p-3 rounded-lg text-sm',
            msg.direction === 'out' ? 'bg-blue-50 border-l-4 border-blue-400 ml-8' : 'bg-white border',
            msg.type === 'error' ? 'border-red-200 bg-red-50' : ''
          ]"
        >
          <div class="flex justify-between items-start">
            <div>
              <span class="font-medium">{{ msg.timestamp }}</span>
              <span 
                v-if="msg.type === 'error'" 
                class="ml-2 px-2 py-0.5 bg-red-100 text-red-800 text-xs rounded-full"
              >
                Error
              </span>
              <span 
                v-else-if="msg.type === 'auth'" 
                class="ml-2 px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full"
              >
                Auth
              </span>
            </div>
            <span class="text-xs text-gray-500">{{ msg.direction === 'out' ? 'OUTGOING' : 'INCOMING' }}</span>
          </div>
          <div class="mt-1 break-words">
            {{ msg.content }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '@/stores/auth';
import { useRealtimeSystemV2 } from '@/composables/useRealtimeSystemV2';

const authStore = useAuthStore();
const { token } = storeToRefs(authStore);
const messageInput = ref('');

// Use the new WebSocket implementation
const {
  isConnected,
  connectionStatus,
  lastError,
  connect,
  disconnect,
  send: sendWsMessage,
  on: onWebSocketEvent
} = useRealtimeSystemV2();

// Client ID for display purposes
const clientId = ref('N/A');

// Message log
interface LogMessage {
  id: number;
  timestamp: string;
  content: string;
  direction: 'in' | 'out';
  type: 'info' | 'error' | 'auth' | 'message';
}

const messages = ref<LogMessage[]>([]);
let messageId = 0;

// Computed properties
const hasToken = computed(() => !!token.value);
const filteredMessages = computed(() => [...messages.value].reverse());

// Add a message to the log
const addMessage = (
  content: string | any,
  direction: 'in' | 'out' = 'in',
  type: 'info' | 'error' | 'auth' | 'message' = 'info'
) => {
  // Convert objects to formatted strings
  let messageContent = content;
  if (typeof content === 'object') {
    try {
      messageContent = JSON.stringify(content, null, 2);
    } catch (e) {
      messageContent = String(content);
    }
  }

  messages.value.push({
    id: messageId++,
    timestamp: new Date().toLocaleTimeString(),
    content: messageContent,
    direction,
    type
  });

  // Keep only the last 100 messages
  if (messages.value.length > 100) {
    messages.value = messages.value.slice(-100);
  }
};

// Send a message through WebSocket
const sendMessage = async () => {
  if (!messageInput.value.trim() || !isConnected.value) return;

  const message = messageInput.value.trim();
  messageInput.value = '';
  
  addMessage(message, 'out', 'message');
  
  try {
    await sendWsMessage('message', {
      message,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    addMessage(
      `Failed to send message: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'out',
      'error'
    );
  }
};

// Test WebSocket authentication
const testAuthentication = async () => {
  if (!isConnected.value) return;
  
  try {
    addMessage('Testing authentication...', 'out', 'auth');
    
    await sendWsMessage('auth_test', {
      timestamp: new Date().toISOString()
    });
    
    addMessage('Authentication test sent', 'out', 'auth');
  } catch (error) {
    addMessage(
      `Authentication test failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'out',
      'error'
    );
  }
};

// Clear all messages
const clearMessages = () => {
  messages.value = [];
};

// Set up WebSocket event listeners
onMounted(() => {
  // Listen for system status updates
  onWebSocketEvent('system_status', (data: any) => {
    addMessage({
      type: 'system_status',
      data
    }, 'in', 'info');
  });
  
  // Listen for authentication responses
  onWebSocketEvent('auth_response', (data: any) => {
    addMessage({
      type: 'auth_response',
      success: data.success,
      message: data.message || 'Authentication response received'
    }, 'in', data.success ? 'auth' : 'error');
  });
  
  // Listen for errors
  onWebSocketEvent('error', (data: any) => {
    addMessage({
      type: 'error',
      error: data.message || 'Unknown error',
      code: data.code || 'UNKNOWN_ERROR'
    }, 'in', 'error');
  });
  
  // Listen for generic messages
  onWebSocketEvent('message', (data: any) => {
    addMessage(data, 'in', 'message');
  });
});

// Clean up on unmount
onUnmounted(() => {
  disconnect();
});

// Watch connection status changes
watch(connectionStatus, (newStatus) => {
  addMessage(`Connection status changed to: ${newStatus}`, 'in', 'info');
});

// Watch for errors
watch(lastError, (error) => {
  if (error) {
    addMessage(`Error: ${error.message}`, 'in', 'error');
  }
});

// Auto-connect when token becomes available
watch(hasToken, (newVal, oldVal) => {
  if (newVal && !oldVal) {
    // Token was just set, try to connect
    connect().catch(console.error);
  } else if (!newVal && oldVal) {
    // Token was removed, disconnect
    disconnect();
  }
}, { immediate: true });
</script>

<style scoped>
/* Add any custom styles here */
</style>
