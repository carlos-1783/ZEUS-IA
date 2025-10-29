<template>
  <div class="agent-avatar" :class="[`agent-${agentName.toLowerCase()}`, size]">
    <div class="avatar-container">
      <!-- Imagen del avatar -->
      <img
        v-if="avatarImage"
        :src="avatarImage"
        :alt="`${agentName} Avatar`"
        class="avatar-image"
        @error="handleImageError"
      />
      
      <!-- Fallback icon si no hay imagen -->
      <div v-else class="avatar-icon">
        {{ agentIcon }}
      </div>
      
      <!-- Status indicator -->
      <div class="status-indicator" :class="status"></div>
      
      <!-- Badge de notificaciones -->
      <div v-if="notifications > 0" class="notification-badge">
        {{ notifications > 99 ? '99+' : notifications }}
      </div>
    </div>
    
    <!-- Nombre y rol -->
    <div v-if="showInfo" class="agent-info">
      <div class="agent-name">{{ agentName }}</div>
      <div class="agent-role">{{ agentRole }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  agentName: string
  agentRole?: string
  avatarImage?: string
  status?: 'online' | 'offline' | 'busy' | 'idle'
  size?: 'small' | 'medium' | 'large'
  showInfo?: boolean
  notifications?: number
}

const props = withDefaults(defineProps<Props>(), {
  status: 'online',
  size: 'medium',
  showInfo: false,
  notifications: 0
})

const imageError = ref(false)

// Íconos por agente
const agentIcons: Record<string, string> = {
  'PERSEO': '📈',
  'RAFAEL': '📊',
  'ZEUS CORE': '⚡',
  'THALOS': '🛡️',
  'JUSTICIA': '⚖️'
}

const agentIcon = computed(() => {
  return agentIcons[props.agentName.toUpperCase()] || '🤖'
})

const handleImageError = () => {
  imageError.value = true
}
</script>

<style scoped>
.agent-avatar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-container {
  position: relative;
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
}

.avatar-container:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Tamaños */
.small .avatar-container {
  width: 40px;
  height: 40px;
}

.medium .avatar-container {
  width: 64px;
  height: 64px;
}

.large .avatar-container {
  width: 96px;
  height: 96px;
}

/* Imagen */
.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* Fallback icon */
.avatar-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5em;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.small .avatar-icon {
  font-size: 1.2em;
}

.large .avatar-icon {
  font-size: 2.5em;
}

/* Bordes por agente */
.agent-perseo .avatar-container {
  border: 3px solid #4A90E2;
}

.agent-rafael .avatar-container {
  border: 3px solid #E74C3C;
}

.agent-zeus_core .avatar-container {
  border: 3px solid #FFD700;
}

.agent-thalos .avatar-container {
  border: 3px solid #9B59B6;
}

.agent-justicia .avatar-container {
  border: 3px solid #34495E;
}

/* Status indicator */
.status-indicator {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid white;
}

.large .status-indicator {
  width: 16px;
  height: 16px;
}

.status-indicator.online {
  background: #2ECC71;
  animation: pulse 2s infinite;
}

.status-indicator.offline {
  background: #95A5A6;
}

.status-indicator.busy {
  background: #E74C3C;
}

.status-indicator.idle {
  background: #F39C12;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

/* Notification badge */
.notification-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #E74C3C;
  color: white;
  font-size: 10px;
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* Agent info */
.agent-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.agent-name {
  font-weight: bold;
  font-size: 14px;
  color: #2C3E50;
}

.agent-role {
  font-size: 12px;
  color: #7F8C8D;
}
</style>

