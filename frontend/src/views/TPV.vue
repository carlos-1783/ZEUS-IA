<template>
  <div class="tpv-container">
    <!-- Botón de vuelta al Dashboard - Siempre visible, posición fija top-left -->
    <button @click="goToDashboard" class="back-to-dashboard-btn fixed-top-left">
      <span class="btn-icon">📊</span>
      <span class="btn-label">Volver al Dashboard</span>
    </button>

    <!-- Header del TPV -->
    <div class="tpv-header">
      <div class="tpv-title-section">
        <h1 class="tpv-title">💳 TPV Universal Enterprise</h1>
        <p class="tpv-subtitle">Sistema de Punto de Venta</p>
      </div>
      <div class="tpv-status" v-if="tpvStatus">
        <span class="status-badge" :class="{ online: tpvStatus.success }">
          {{ tpvStatus.success ? '● Online' : '○ Offline' }}
        </span>
      </div>
    </div>

    <!-- Contenido principal del TPV -->
    <div class="tpv-content">
      <!-- Panel de información del negocio -->
      <div class="business-info-panel" v-if="tpvStatus">
        <div class="info-card">
          <h3>📋 Perfil de Negocio</h3>
          <p v-if="tpvStatus.business_profile">
            <strong>Tipo:</strong> {{ tpvStatus.business_profile }}
          </p>
          <p>
            <strong>Productos:</strong> {{ tpvStatus.products_count || 0 }}
          </p>
        </div>

        <div class="info-card">
          <h3>🔗 Integraciones</h3>
          <div class="integration-badges">
            <span 
              v-for="(enabled, name) in tpvStatus.integrations" 
              :key="name"
              class="integration-badge"
              :class="{ active: enabled }"
            >
              {{ name }}: {{ enabled ? '✓' : '✗' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Panel principal - Aquí iría la interfaz completa del TPV -->
      <div class="tpv-main-panel">
        <div class="welcome-message">
          <h2>Bienvenido al TPV Universal Enterprise</h2>
          <p>Este módulo está integrado con el ecosistema ZEUS-IA.</p>
          <p>Las ventas se procesan automáticamente con RAFAEL para contabilidad.</p>
        </div>

        <!-- Acciones rápidas -->
        <div class="quick-actions">
          <button @click="checkStatus" class="action-btn primary">
            🔍 Verificar Estado
          </button>
          <button @click="openProducts" class="action-btn secondary">
            📦 Gestión de Productos
          </button>
          <button @click="openSales" class="action-btn secondary">
            💰 Realizar Venta
          </button>
        </div>

        <!-- Mensaje de carga -->
        <div v-if="loading" class="loading-message">
          <p>Cargando información del TPV...</p>
        </div>

        <!-- Mensaje de error -->
        <div v-if="error" class="error-message">
          <p>❌ Error: {{ error }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// Estado
const tpvStatus = ref(null)
const loading = ref(false)
const error = ref(null)

// Navegar al Dashboard
const goToDashboard = () => {
  router.push('/dashboard')
}

// Cargar estado del TPV
const checkStatus = async () => {
  loading.value = true
  error.value = null
  
  try {
    const token = authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }

    const response = await fetch('/api/v1/tpv', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    tpvStatus.value = data
    console.log('✅ Estado del TPV cargado:', data)
  } catch (err) {
    console.error('Error cargando estado del TPV:', err)
    error.value = err.message || 'Error desconocido'
  } finally {
    loading.value = false
  }
}

// Acciones del TPV (placeholders - se implementarán después)
const openProducts = () => {
  console.log('Abrir gestión de productos')
  // TODO: Implementar vista de productos
}

const openSales = () => {
  console.log('Abrir módulo de ventas')
  // TODO: Implementar interfaz de ventas
}

// Cargar estado al montar
onMounted(() => {
  checkStatus()
})
</script>

<style scoped>
.tpv-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #0a0e1a 0%, #1a1f2e 100%);
  color: #fff;
  padding: 20px;
  position: relative;
}

.back-to-dashboard-btn.fixed-top-left {
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 1000;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
}

.tpv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 30px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  margin: 80px 20px 30px 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.back-to-dashboard-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
}

.back-to-dashboard-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.5);
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.back-to-dashboard-btn:active {
  transform: translateY(0);
}

.btn-icon {
  font-size: 1.2rem;
}

.btn-label {
  white-space: nowrap;
}

.tpv-title-section {
  flex: 1;
  text-align: center;
}

.tpv-title {
  font-size: 2rem;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.tpv-subtitle {
  color: rgba(255, 255, 255, 0.6);
  margin: 5px 0 0;
  font-size: 0.9rem;
}

.tpv-status {
  display: flex;
  align-items: center;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 0.85rem;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #fca5a5;
}

.status-badge.online {
  background: rgba(16, 185, 129, 0.2);
  border-color: rgba(16, 185, 129, 0.5);
  color: #6ee7b7;
}

.tpv-content {
  max-width: 1400px;
  margin: 0 auto;
}

.business-info-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.info-card {
  padding: 25px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.info-card h3 {
  margin: 0 0 15px;
  color: #fff;
  font-size: 1.2rem;
}

.info-card p {
  margin: 10px 0;
  color: rgba(255, 255, 255, 0.8);
}

.integration-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.integration-badge {
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  text-transform: capitalize;
}

.integration-badge.active {
  background: rgba(16, 185, 129, 0.2);
  border-color: rgba(16, 185, 129, 0.3);
  color: #6ee7b7;
}

.tpv-main-panel {
  padding: 40px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.welcome-message {
  text-align: center;
  margin-bottom: 40px;
}

.welcome-message h2 {
  font-size: 1.8rem;
  margin: 0 0 15px;
  color: #fff;
}

.welcome-message p {
  color: rgba(255, 255, 255, 0.7);
  margin: 10px 0;
  font-size: 1rem;
}

.quick-actions {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
}

.action-btn {
  padding: 15px 30px;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.action-btn.primary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
}

.action-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.5);
}

.action-btn.secondary {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  color: #fff;
}

.action-btn.secondary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(139, 92, 246, 0.5);
}

.loading-message,
.error-message {
  margin-top: 30px;
  padding: 20px;
  border-radius: 10px;
  text-align: center;
}

.loading-message {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #93c5fd;
}

.error-message {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

/* Responsive */
@media (max-width: 768px) {
  .tpv-header {
    flex-direction: column;
    gap: 20px;
    text-align: center;
    margin-top: 100px;
  }

  .back-to-dashboard-btn.fixed-top-left {
    position: fixed;
    top: 10px;
    left: 10px;
    right: auto;
    padding: 10px 16px;
    font-size: 0.85rem;
  }

  .back-to-dashboard-btn .btn-label {
    display: none;
  }

  .back-to-dashboard-btn .btn-icon {
    font-size: 1.5rem;
  }

  .tpv-title {
    font-size: 1.5rem;
  }

  .business-info-panel {
    grid-template-columns: 1fr;
  }

  .quick-actions {
    flex-direction: column;
  }

  .action-btn {
    width: 100%;
  }
}
</style>

