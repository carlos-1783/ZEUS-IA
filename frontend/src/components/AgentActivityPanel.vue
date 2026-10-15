<template>
  <div class="activity-panel">
    <!-- Header: identidad del agente + único punto de entrada a Herramientas/Actividad/Métricas
         (menú ⋮). Sin toggle Texto/Voz aquí — el orbe lleva el suyo propio (micro/teclado). El
         orbe ya no tiene cabecera propia: esta es la única, para no duplicar marco ni identidad. -->
    <div class="panel-header">
      <div class="agent-info">
        <span class="agent-avatar-ring">
          <img :src="agent.image" :alt="agent.name" class="agent-avatar-small" />
        </span>
        <div>
          <h3>{{ agent.name }}</h3>
          <p class="agent-role">{{ agent.role }}</p>
        </div>
      </div>
      <div class="header-menu-wrap">
        <button
          type="button"
          class="header-menu-btn"
          :aria-expanded="menuOpen ? 'true' : 'false'"
          aria-haspopup="menu"
          aria-label="Más paneles"
          title="Más paneles"
          @click="menuOpen = !menuOpen"
        >
          ⋮
        </button>
        <div v-if="menuOpen" class="header-menu" role="menu">
          <button type="button" role="menuitem" @click="selectPanel('tools')">🛠️ Herramientas</button>
          <button type="button" role="menuitem" @click="selectPanel('activity')">📊 Actividad</button>
          <button type="button" role="menuitem" @click="selectPanel('metrics')">📈 Métricas</button>
        </div>
      </div>
    </div>

    <!-- El orbe ES la pantalla principal: sin pestañas. "Herramientas / Actividad / Métricas"
         siguen existiendo tal cual (no se rehacen), solo cambia cómo se llega — desde el menú ⋮
         de arriba, que las despliega como un panel más junto al orbe. -->
    <AgentVoiceOrb
      ref="orbRef"
      :key="agent.name"
      :agent="agent"
      :panel-titles="panelTitles"
      @panel-opened="onPanelOpened"
      @panel-closed="onPanelClosed"
    >
      <template #panel-tools>
        <component :is="currentWorkspace" v-if="currentWorkspace" />
        <div v-else class="no-workspace">
          <p>Workspace no disponible para este agente</p>
        </div>
      </template>

      <template #panel-activity>
        <div class="activity-content">
          <div class="activity-header">
            <label class="days-label" :for="daysSelectId">Periodo</label>
            <select :id="daysSelectId" v-model="activityDays" @change="loadActivities" class="days-selector">
              <option value="1">Últimas 24h</option>
              <option value="7">Última semana</option>
              <option value="30">Último mes</option>
            </select>
          </div>

          <div class="activity-timeline">
            <div
              v-for="activity in activities"
              :key="activity.id"
              class="activity-item"
              :class="activity.priority"
            >
              <div class="activity-icon" :class="activity.status">
                {{ getActivityIcon(activity.action_type) }}
              </div>
              <div class="activity-details">
                <p class="activity-description">{{ activity.description }}</p>
                <div class="activity-meta">
                  <span class="activity-time">{{ formatDateTime(activity.created_at) }}</span>
                  <span class="activity-status" :class="activity.status">
                    {{ getStatusText(activity.status) }}
                  </span>
                </div>
                <div v-if="activity.metrics" class="activity-metrics">
                  <span v-for="(value, key) in activity.metrics" :key="key" class="metric-badge">
                    {{ key }}: {{ value }}
                  </span>
                </div>
              </div>
            </div>

            <div v-if="activities.length === 0" class="empty-state">
              <p>No hay actividades registradas en este período</p>
            </div>
          </div>
        </div>
      </template>

      <template #panel-metrics>
        <div class="metrics-content">
          <div class="metrics-grid">
            <div class="metric-card">
              <div class="metric-label">Total de acciones</div>
              <div class="metric-value">{{ metrics.total_actions || 0 }}</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Tasa de éxito</div>
              <div class="metric-value">{{ (metrics.success_rate || 0).toFixed(1) }}%</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Completadas</div>
              <div class="metric-value success">{{ metrics.completed || 0 }}</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Fallidas</div>
              <div class="metric-value error">{{ metrics.failed || 0 }}</div>
            </div>
          </div>

          <div v-if="metrics.specific_metrics" class="specific-metrics">
            <h5>Métricas Específicas</h5>
            <div class="specific-metrics-grid">
              <div
                v-for="(value, key) in metrics.specific_metrics"
                :key="key"
                class="specific-metric-item"
              >
                <span class="metric-key">{{ formatMetricKey(key) }}</span>
                <span class="metric-val">{{ formatMetricValue(value) }}</span>
              </div>
            </div>
          </div>

          <button @click="loadMetrics" class="btn-refresh-metrics">
            🔄 Actualizar Métricas
          </button>
        </div>
      </template>
    </AgentVoiceOrb>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import PerseoWorkspace from './agent-workspaces/PerseoWorkspace.vue'
import RafaelWorkspace from './agent-workspaces/RafaelWorkspace.vue'
import AfroditaWorkspace from './agent-workspaces/AfroditaWorkspace.vue'
import ThalosWorkspace from './agent-workspaces/ThalosWorkspace.vue'
import JusticiaWorkspace from './agent-workspaces/JusticiaWorkspace.vue'
import ZeusCoreWorkspace from './agent-workspaces/ZeusCoreWorkspace.vue'
import AgentVoiceOrb from './agent-workspaces/AgentVoiceOrb.vue'

const props = defineProps({
  agent: {
    type: Object,
    required: true
  }
})

const authStore = useAuthStore()

// Workspaces mapping — SIN rehacer: son los paneles reales que ya existían bajo "Herramientas".
const workspaces = {
  'ZEUS': ZeusCoreWorkspace,
  'PERSEO': PerseoWorkspace,
  'RAFAEL': RafaelWorkspace,
  'AFRODITA': AfroditaWorkspace,
  'THALOS': ThalosWorkspace,
  'JUSTICIA': JusticiaWorkspace
}

const currentWorkspace = computed(() => {
  const agentKey = props.agent.name.split(' ')[0].toUpperCase()
  return workspaces[agentKey] || null
})

const panelTitles = { tools: 'Herramientas', activity: 'Actividad', metrics: 'Métricas' }
const daysSelectId = `days-${Math.random().toString(36).slice(2, 8)}`

// Menú ⋮ de la cabecera: controla el orbe por referencia (único punto de entrada a los paneles).
const orbRef = ref(null)
const menuOpen = ref(false)

function selectPanel(key) {
  menuOpen.value = false
  orbRef.value?.choosePanel(key)
}


// Activities
const activities = ref([])
const activityDays = ref(7)

// Metrics
const metrics = ref({})

let activityPollTimer = null
let metricsPollTimer = null

function onPanelOpened(key) {
  if (key === 'activity') {
    loadActivities()
    activityPollTimer = setInterval(loadActivities, 15000)
  } else if (key === 'metrics') {
    loadMetrics()
    metricsPollTimer = setInterval(loadMetrics, 15000)
  }
}

function onPanelClosed(key) {
  if (key === 'activity' && activityPollTimer) {
    clearInterval(activityPollTimer)
    activityPollTimer = null
  } else if (key === 'metrics' && metricsPollTimer) {
    clearInterval(metricsPollTimer)
    metricsPollTimer = null
  }
}

onUnmounted(() => {
  if (activityPollTimer) clearInterval(activityPollTimer)
  if (metricsPollTimer) clearInterval(metricsPollTimer)
})

// Al cambiar de agente, los datos cargados quedan obsoletos; se recargan si el panel sigue abierto
// (el propio AgentVoiceOrb se remonta por el :key="agent.name", así que el panel vuelve a cerrarse).
watch(() => props.agent.name, () => {
  activities.value = []
  metrics.value = {}
  menuOpen.value = false
})

const loadActivities = async () => {
  try {
    const token = authStore.getToken?.() ?? authStore.token ?? null
    if (!token) {
      console.warn('Sin token para /activities')
      activities.value = []
      return
    }
    const agentName = props.agent.name.split(' ')[0].toUpperCase()
    const api = (await import('@/services/api')).default
    const data = await api.get(
      `/api/v1/activities/${agentName}?days=${activityDays.value}`,
      token
    )
    if (data.success) {
      activities.value = data.activities
      // Fallback operacional: si aún no hay filas en agent_activities,
      // mostrar entregables recientes para no dejar el panel vacío.
      if ((activities.value?.length || 0) === 0) {
        try {
          const outputs = await api.get(`/api/v1/automation/outputs?agent=${encodeURIComponent(agentName)}`, token)
          const files = outputs?.outputs || []
          activities.value = files.slice(0, 20).map((o, idx) => ({
            id: `out-${idx}-${o.filename}`,
            action_type: 'automation_output',
            description: o.title || o.filename || 'Entregable generado',
            status: 'completed',
            priority: 'normal',
            created_at: o.created_at || new Date().toISOString(),
            metrics: { source: 'automation_outputs' },
          }))
        } catch (fallbackErr) {
          console.warn('Fallback automation outputs no disponible', fallbackErr)
        }
      }
    }
  } catch (error) {
    console.error('Error loading activities:', error)
    activities.value = []
  }
}

const loadMetrics = async () => {
  try {
    const token = authStore.getToken?.() ?? authStore.token ?? null
    if (!token) {
      console.warn('Sin token para /activities/.../metrics')
      metrics.value = {}
      return
    }
    const agentName = props.agent.name.split(' ')[0].toUpperCase()
    const api = (await import('@/services/api')).default
    const data = await api.get(
      `/api/v1/activities/${agentName}/metrics?days=30`,
      token
    )
    if (data.success) {
      metrics.value = data
    }
  } catch (error) {
    console.error('Error loading metrics:', error)
    metrics.value = {}
  }
}

const getActivityIcon = (actionType) => {
  const icons = {
    campaign_created: '📢',
    invoice_sent: '📄',
    security_scan: '🔍',
    threat_blocked: '🛡️',
    document_reviewed: '⚖️',
    optimization: '⚡',
    backup_created: '💾',
    default: '📌'
  }
  return icons[actionType] || icons.default
}

const getStatusText = (status) => {
  const texts = {
    completed: 'Completado',
    success: 'Completado',
    executed: 'Ejecutado',
    failed: 'Fallido',
    pending: 'Pendiente',
    needs_confirmation: 'Pendiente de confirmar',
    needs_more_data: 'Faltan datos',
    not_understood: 'No entendido',
    rejected: 'Rechazado',
    audit_failed: 'Auditoría fallida',
    blocked_no_company: 'Bloqueado: sin empresa',
    blocked_client_origin: 'Bloqueado',
    blocked_missing_handler: 'Bloqueado'
  }
  return texts[status] || status
}

const formatDateTime = (date) => {
  return new Date(date).toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatMetricKey = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatMetricValue = (value) => {
  if (typeof value === 'number') {
    return value.toLocaleString('es-ES')
  }
  return value
}

// Producción: no inyectar mock automático para no ocultar problemas reales.
</script>

<style scoped>
.activity-panel {
  /* Superficie "metal cepillado" — capas de gradiente (veta + barrido de
     luz diagonal + brillo/sombra de esquina) sobre la base platino, más
     grano SVG en ::before. Sistema validado en preview-rafael.html antes
     de aplicarse aquí; ver tokens zeus-metal y zeus-noise-svg en
     zeus-light-system.css. Los bloques de contenido (tarjetas, header)
     siguen flotando encima como superficies blancas con sombra. */
  position: relative;
  overflow-x: hidden;
  background-image: var(--zeus-metal-bg);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-lg, 16px);
  box-shadow: var(--zeus-shadow-lg);
  padding: 32px;
  height: auto;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  width: 100%;
  color: var(--zeus-text, #0f172a);
}

.activity-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}

.activity-panel > * {
  position: relative;
}

/* Header */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--zeus-border, #e5e9f0);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar-ring {
  display: block;
  width: 54px;
  height: 54px;
  padding: 3px;
  border-radius: 50%;
  background: var(--zeus-accent-gradient, linear-gradient(135deg, #14b8a6 0%, #8b5cf6 40%, #ec4899 70%, #f97316 100%));
  box-shadow: var(--zeus-accent-gradient-shadow, 0 2px 10px rgba(139, 92, 246, 0.35));
  flex-shrink: 0;
}

.agent-avatar-small {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--zeus-surface, #fff);
}

.agent-info h3 {
  margin: 0;
  font-size: 18px;
  color: var(--zeus-text, #0f172a);
}

.agent-role {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--zeus-text-muted, #8792a6);
}

.header-menu-wrap {
  position: relative;
  flex-shrink: 0;
}

.header-menu-btn {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--zeus-border, #e5e9f0);
  background: var(--zeus-surface, #fff);
  color: var(--zeus-text, #0f172a);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.header-menu-btn:focus-visible {
  outline: none;
  box-shadow: var(--zeus-shadow-focus, 0 0 0 3px rgba(106, 92, 255, 0.3));
}

.header-menu {
  position: absolute;
  top: 44px;
  right: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  min-width: 180px;
  padding: 6px;
  border-radius: var(--zeus-radius, 12px);
  border: 1px solid var(--zeus-border, #e5e9f0);
  background: var(--zeus-surface, #fff);
  box-shadow: var(--zeus-shadow-lg, 0 12px 32px rgba(15, 23, 42, 0.18));
}

.header-menu button {
  text-align: left;
  padding: 9px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--zeus-text, #0f172a);
  font-size: 13px;
  cursor: pointer;
}

.header-menu button:hover {
  background: var(--zeus-bg-subtle, #eef1f6);
}

/* Actividad (dentro del deck del orbe) */
.activity-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.days-label {
  font-size: 12px;
  color: var(--zeus-text-muted, #8792a6);
}

.days-selector {
  padding: 8px 12px;
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e5e9f0);
  border-radius: 6px;
  color: var(--zeus-text, #0f172a);
  cursor: pointer;
}

.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.activity-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: var(--zeus-bg-subtle, #eef1f6);
  border-left: 3px solid #3b82f6;
  border-radius: 8px;
  transition: all 0.2s;
}

.activity-item:hover {
  background: var(--zeus-accent-soft, #eef1ff);
}

.activity-item.high {
  border-left-color: #eab308;
}

.activity-item.critical {
  border-left-color: #ef4444;
}

.activity-icon {
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  flex-shrink: 0;
}

.activity-icon.failed {
  background: rgba(239, 68, 68, 0.2);
}

.activity-details {
  flex: 1;
}

.activity-description {
  margin: 0 0 8px;
  color: var(--zeus-text, #0f172a);
  font-size: 14px;
}

.activity-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.activity-time {
  font-size: 12px;
  color: var(--zeus-text-muted, #8792a6);
}

.activity-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--zeus-success-soft, #e9faf3);
  color: #0d9668;
  font-weight: 600;
}

.activity-status.failed,
.activity-status.audit_failed {
  background: var(--zeus-danger-soft, #fdecec);
  color: var(--zeus-danger, #dc2626);
}

.activity-status.needs_confirmation,
.activity-status.needs_more_data,
.activity-status.not_understood,
.activity-status.rejected,
.activity-status.blocked_no_company,
.activity-status.blocked_client_origin,
.activity-status.blocked_missing_handler {
  background: var(--zeus-warning-soft, #fef6e7);
  color: var(--zeus-warning, #f59e0b);
}

.activity-metrics {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.metric-badge {
  font-size: 11px;
  padding: 4px 8px;
  background: var(--zeus-accent-soft, #eef1ff);
  color: var(--zeus-accent, #3b82f6);
  border-radius: 4px;
  font-weight: 600;
}

/* Métricas (dentro del deck del orbe) */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background: var(--zeus-bg-subtle, #eef1f6);
  border: 1px solid var(--zeus-border, #e5e9f0);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: var(--zeus-text-secondary, #52607a);
  margin-bottom: 8px;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-value.success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-value.error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.specific-metrics {
  margin-top: 24px;
}

.specific-metrics h5 {
  margin: 0 0 16px;
  font-size: 16px;
  color: var(--zeus-text, #0f172a);
}

.specific-metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.specific-metric-item {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: var(--zeus-bg-subtle, #eef1f6);
  border-radius: 8px;
}

.metric-key {
  font-size: 13px;
  color: var(--zeus-text-secondary, #52607a);
}

.metric-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--zeus-accent, #3b82f6);
}

.btn-refresh-metrics {
  width: 100%;
  padding: 12px;
  background: var(--zeus-accent-soft, #eef1ff);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: var(--zeus-accent, #3b82f6);
  border-radius: 8px;
  cursor: pointer;
  margin-top: 20px;
  font-weight: 600;
}

.btn-refresh-metrics:hover {
  background: rgba(59, 130, 246, 0.15);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--zeus-text-muted, #8792a6);
}

.no-workspace {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--zeus-text-muted, #8792a6);
  font-size: 16px;
}

/* Responsive */
@media (max-width: 768px) {
  .activity-panel {
    height: auto;
    min-height: unset;
    max-height: calc(100vh - 140px);
    width: 100%;
    padding: 18px 14px;
  }

  .metrics-grid,
  .specific-metrics-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    gap: 16px;
  }
}
</style>
