import { ref } from 'vue'

export interface Notification {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration?: number
}

const notifications = ref<Notification[]>([])

export function useNotifications() {
  const showNotification = (
    type: 'success' | 'error' | 'warning' | 'info',
    message: string,
    duration: number = 4000
  ) => {
    const notification: Notification = {
      id: Date.now() + Math.random(),
      type,
      message,
      duration
    }
    
    notifications.value.push(notification)
    
    // Auto-remover después de la duración
    setTimeout(() => {
      removeNotification(notification.id)
    }, duration)
    
    return notification.id
  }
  
  const removeNotification = (id: number) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }
  
  const success = (message: string, duration?: number) => {
    return showNotification('success', message, duration)
  }
  
  const error = (message: string, duration?: number) => {
    return showNotification('error', message, duration)
  }
  
  const warning = (message: string, duration?: number) => {
    return showNotification('warning', message, duration)
  }
  
  const info = (message: string, duration?: number) => {
    return showNotification('info', message, duration)
  }
  
  return {
    notifications,
    showNotification,
    removeNotification,
    success,
    error,
    warning,
    info
  }
}
