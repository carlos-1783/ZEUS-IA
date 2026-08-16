<template>
  <div class="zeus-workspace">
    <header class="workspace-header">
      <div>
        <h3>ZEUS CORE Workspace</h3>
        <p class="subtitle">Bootstrap de análisis para construir el modelo operativo antes de activar ejecución.</p>
      </div>
      <div class="actions">
        <button class="btn-primary" :disabled="running" @click="runBootstrap">
          {{ running ? 'Construyendo…' : 'Construir workspace' }}
        </button>
        <button class="btn-secondary" :disabled="loading" @click="loadWorkspace">
          {{ loading ? 'Actualizando…' : 'Actualizar' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section v-if="latest" class="workspace-card">
      <div class="workspace-meta">
        <strong>{{ latest.title || 'ZEUS CORE Workspace Bootstrap' }}</strong>
        <span v-if="createdAt">Generado: {{ createdAt }}</span>
      </div>

      <div class="summary-grid" v-if="summary">
        <div class="summary-item">
          <span class="label">Modo</span>
          <span class="value">{{ modeLabel }}</span>
        </div>
        <div class="summary-item">
          <span class="label">Agentes detectados</span>
          <span class="value">{{ summary.available_agents || 0 }}/{{ summary.total_agents || 0 }}</span>
        </div>
        <div class="summary-item">
          <span class="label">Punto de partida</span>
          <span class="value">{{ entrypointLabel }}</span>
        </div>
      </div>

      <div v-if="agentRows.length" class="agents-list">
        <h4>Resumen operativo de agentes</h4>
        <div v-for="row in agentRows" :key="row.name" class="agent-row">
          <div class="agent-row-head">
            <strong>{{ row.name }}</strong>
            <span :class="['badge', row.available ? 'ok' : 'warn']">
              {{ row.available ? 'Disponible' : 'No detectado' }}
            </span>
          </div>
          <p class="purpose"><strong>Para qué sirve:</strong> {{ row.purpose }}</p>
          <p class="targets"><strong>Endpoints detectados:</strong> {{ row.discoveredTargets }}</p>
          <p class="caps"><strong>Qué puede hacer ya:</strong> {{ row.real }}</p>
          <p class="caps"><strong>Qué depende de contexto o configuración:</strong> {{ row.partial }}</p>
        </div>
      </div>
    </section>

    <section v-else class="empty-state">
      <p>ZEUS CORE aún no tiene workspace generado. Pulsa <strong>Construir workspace</strong>.</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'

const loading = ref(false)
const running = ref(false)
const error = ref('')
const latest = ref<any | null>(null)

const createdAt = computed(() => {
  const raw = latest.value?.created_at || latest.value?.document_payload?.created_at
  if (!raw) return ''
  try {
    return new Date(raw).toLocaleString('es-ES')
  } catch {
    return String(raw)
  }
})

const brain = computed(() => latest.value?.document_payload?.content?.zeus_brain || null)
const summary = computed(() => brain.value?.summary || null)

const agentPurposeMap: Record<string, string> = {
  AFRODITA: 'Operaciones internas y RRHH.',
  RAFAEL: 'Fiscalidad, puntuación de riesgo y análisis.',
  THALOS: 'Monitorización, eventos y alertas.',
  JUSTICIA: 'Auditoría, cumplimiento normativo y revisión legal.',
  PERSEO: 'Asistente inteligente, chat y tareas creativas.',
}

const capabilityLabelsEs: Record<string, string> = {
  create_employee: 'Crear empleados',
  qr_checkin: 'Fichaje por QR',
  list_schedules: 'Consultar horarios',
  inventory_ops: 'Gestión de inventario',
  workspace_reads: 'Consultar workspace',
  create_client_via_cross_agent: 'Alta de cliente vía otros agentes',
  ops_routes: 'Rutas operativas',
  generate_invoice_pdf: 'Generar PDF de factura',
  generate_model_303: 'Generar modelo 303',
  payment_risk_scoring: 'Evaluar riesgo de cobro',
  scan_flow: 'Flujos de escaneo (QR/NFC/DNI)',
  tax_summary: 'Resumen fiscal',
  workspace_forms: 'Formularios del workspace',
  monitoring: 'Monitorización activa',
  alerts: 'Alertas',
  event_audit: 'Auditoría de eventos',
  workspace_items: 'Elementos del workspace',
  active_execution_guarded: 'Ejecución activa (protegida por flags)',
  system_audit: 'Auditoría del sistema',
  documents_read: 'Consulta de documentos',
  compliance_review: 'Revisión de cumplimiento',
  read_only_mixed_tools: 'Herramientas mixtas en solo lectura',
  llm_chat: 'Chat con IA',
  video_edit_jobs: 'Trabajos de edición de vídeo',
  audit_report: 'Informes de auditoría',
  assistant_fallbacks: 'Respuestas de respaldo del asistente',
  ai_generation_depends_on_provider: 'Generación IA según proveedor externo',
}

const modeLabelsEs: Record<string, string> = {
  analysis_only: 'Solo análisis (sin ejecución)',
}

const entrypointLabelsEs: Record<string, string> = {
  '/api/v1/zeus-core/workspace-bootstrap': 'Bootstrap de análisis del workspace',
}

const translateCapability = (key: string) => {
  const normalized = key.trim().toLowerCase()
  return capabilityLabelsEs[normalized] || key.replaceAll('_', ' ')
}

const toHumanList = (value: string) => {
  if (!value || value === '—') return '—'
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => translateCapability(item))
    .join(', ')
}

const modeLabel = computed(() => {
  const mode = summary.value?.mode
  return (mode && modeLabelsEs[mode]) || modeLabelsEs.analysis_only
})

const entrypointLabel = computed(() => {
  const ep = summary.value?.recommended_entrypoint
  return (ep && entrypointLabelsEs[ep]) || entrypointLabelsEs['/api/v1/zeus-core/workspace-bootstrap']
})

const agentRows = computed(() => {
  const agents = brain.value?.agents || {}
  return Object.entries(agents).map(([name, info]: any) => ({
    name,
    available: Boolean(info?.available),
    purpose: agentPurposeMap[name] || 'Capacidades operativas del agente.',
    discoveredTargets: (info?.discovered_targets || []).join(' · ') || 'Sin endpoints detectados',
    real: toHumanList((info?.capabilities_real || []).join(', ')),
    partial: toHumanList((info?.capabilities_partial || []).join(', ')),
  }))
})

async function loadWorkspace() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/api/v1/workspace/list?agent_name=ZEUS%20CORE&limit=20')
    const items = Array.isArray(res?.items) ? res.items : []
    latest.value = items[0] || null
  } catch (e: any) {
    error.value = e?.message || 'No se pudo cargar el workspace de ZEUS CORE'
    latest.value = null
  } finally {
    loading.value = false
  }
}

async function runBootstrap() {
  running.value = true
  error.value = ''
  try {
    await api.post('/api/v1/zeus-core/workspace-bootstrap', {
      analysis_only: true,
      persist_artifact: true,
    })
    await loadWorkspace()
  } catch (e: any) {
    error.value = e?.message || 'No se pudo construir el workspace de ZEUS CORE'
  } finally {
    running.value = false
  }
}

onMounted(loadWorkspace)
</script>

<style scoped>
.zeus-workspace {
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  color: var(--zeus-text, #0f172a);
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.subtitle {
  margin: 6px 0 0;
  color: var(--zeus-text-secondary, #52607a);
}

.actions {
  display: flex;
  gap: 10px;
}

.btn-primary,
.btn-secondary {
  border: none;
  border-radius: var(--zeus-radius-sm, 10px);
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  transition: transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

/* ZEUS CORE es el orquestador del sistema, sin un color de identidad
   propio distinto del resto — usa el acento gradiente compartido en su
   accion primaria (mismo tratamiento que el anillo de su avatar en el
   modal). */
.btn-primary {
  background: var(--zeus-accent-gradient, linear-gradient(135deg, #14b8a6 0%, #8b5cf6 40%, #ec4899 70%, #f97316 100%));
  color: #fff;
  box-shadow: var(--zeus-accent-gradient-shadow, 0 2px 10px rgba(139, 92, 246, 0.35));
}

.btn-primary:hover:not(:disabled) {
  box-shadow: var(--zeus-accent-gradient-shadow-hover, 0 4px 18px rgba(139, 92, 246, 0.45));
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--zeus-surface, #fff);
  color: var(--zeus-text, #0f172a);
  border: 1px solid var(--zeus-border, #e1e5eb);
  box-shadow: var(--zeus-shadow-sm);
}

.btn-secondary:hover:not(:disabled) {
  border-color: var(--zeus-border-strong, #cdd3db);
  transform: translateY(-1px);
}

.btn-primary:active:not(:disabled),
.btn-secondary:active:not(:disabled) {
  transform: translateY(0);
  transition-duration: var(--zeus-dur-press, 100ms);
}

.error-banner,
.workspace-card,
.empty-state {
  border-radius: var(--zeus-radius-lg, 14px);
  padding: 16px;
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e1e5eb);
  box-shadow: var(--zeus-shadow-sm);
}

.error-banner {
  color: #b91c1c;
  background: var(--zeus-danger-soft, #fdecec);
  border-color: rgba(248, 113, 113, 0.35);
}

.workspace-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  padding: 12px;
  border-radius: var(--zeus-radius, 12px);
  background: var(--zeus-bg-subtle, #eef1f6);
}

.label {
  display: block;
  font-size: 12px;
  color: var(--zeus-text-muted, #8792a6);
  margin-bottom: 6px;
}

.value {
  font-weight: 700;
  color: var(--zeus-text, #0f172a);
}

.mono {
  font-family: var(--zeus-font-mono, monospace);
  font-size: 12px;
}

.agents-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-row {
  padding: 12px;
  border-radius: var(--zeus-radius, 12px);
  background: var(--zeus-bg-subtle, #eef1f6);
}

.agent-row-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 6px;
}

.badge {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
}

/* !important necesario: css_system_enforcer_v1.css fuerza .badge global
   a gris plano con !important; con dos clases (.badge.ok) esta regla ya
   gana por especificidad, pero se marca !important explicito para no
   depender del orden de carga entre hojas de estilo. */
.badge.ok {
  background: var(--zeus-success-soft, #e9faf3) !important;
  color: #0d9668 !important;
}

.badge.warn {
  background: var(--zeus-warning-soft, #fef6e7) !important;
  color: #b45309 !important;
}

.purpose,
.targets,
.caps {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--zeus-text-secondary, #52607a);
}

@media (prefers-reduced-motion: reduce) {
  .btn-primary:hover:not(:disabled),
  .btn-secondary:hover:not(:disabled),
  .btn-primary:active:not(:disabled),
  .btn-secondary:active:not(:disabled) {
    transform: none;
  }
}
</style>
