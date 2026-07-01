<template>
  <section class="teamflow-panel">
    <header class="tf-header">
      <div>
        <h5>🔗 TeamFlow</h5>
        <p class="hint">Flujos cross-agent desde BD — contratos, facturas y handoffs.</p>
      </div>
      <button class="refresh-btn" :disabled="loading" @click="reload">
        {{ loading ? '…' : 'Actualizar' }}
      </button>
    </header>

    <p v-if="error" class="tf-error">{{ error }}</p>

    <ul v-if="items.length" class="tf-list">
      <li
        v-for="item in items"
        :key="item.id"
        :class="{ active: selectedId === item.id }"
        @click="selectedId = item.id"
      >
        <div class="tf-title">{{ item.title }}</div>
        <div class="tf-meta">
          <span class="status" :class="item.status">{{ item.status }}</span>
          <span v-if="item.source_agent" class="route">{{ item.source_agent }} → {{ item.target_agent || '—' }}</span>
          <span class="date">{{ formatDate(item.created_at) }}</span>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading" class="tf-empty">Sin flujos TeamFlow para {{ agentLabel }}.</p>

    <div v-if="selected" class="tf-detail">
      <ZeusDocumentRenderer v-if="docPayload" :doc="docPayload" />
      <pre v-else class="tf-raw">{{ formatContent(selected.content) }}</pre>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchTeamFlowItems, type TeamFlowItem } from '@/api/teamflow_api'
import ZeusDocumentRenderer from '@/components/documents/ZeusDocumentRenderer.vue'

const props = defineProps<{
  agent: string
}>()

const items = ref<TeamFlowItem[]>([])
const selectedId = ref<string | null>(null)
const loading = ref(false)
const error = ref('')

const agentLabel = computed(() => props.agent.toUpperCase())

const selected = computed(() => items.value.find((i) => i.id === selectedId.value) || null)

const docPayload = computed(() => {
  const c = selected.value?.content
  if (!c) return null
  if (c.legal_document || c.document_id) {
    return {
      agent_source: 'AFRODITA',
      legal_document: c.legal_document,
      employee: { full_name: c.employee_name },
      role: c.role,
      salary: c.salary,
      contract_id: c.document_id,
    }
  }
  return null
})

const formatDate = (iso?: string | null) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const formatContent = (content: Record<string, unknown>) => JSON.stringify(content, null, 2)

const reload = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchTeamFlowItems({ agent: props.agent, limit: 50 })
    items.value = res.items || []
    if (items.value.length && !selectedId.value) {
      selectedId.value = items.value[0].id
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.agent,
  () => {
    selectedId.value = null
    void reload()
  },
)

onMounted(() => {
  void reload()
  window.addEventListener('zeus:teamflow-refresh', reload)
})
onUnmounted(() => {
  window.removeEventListener('zeus:teamflow-refresh', reload)
})

defineExpose({ reload })
</script>

<style scoped>
.teamflow-panel {
  margin-top: 20px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(99, 102, 241, 0.25);
  background: rgba(99, 102, 241, 0.04);
}
.tf-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.tf-header h5 { margin: 0; font-size: 15px; }
.hint { margin: 4px 0 0; font-size: 12px; color: #64748b; }
.refresh-btn {
  border: 1px solid rgba(99, 102, 241, 0.35);
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
}
.tf-list { list-style: none; margin: 0; padding: 0; }
.tf-list li {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
  cursor: pointer;
  background: #fff;
}
.tf-list li.active { border-color: #6366f1; background: rgba(99, 102, 241, 0.08); }
.tf-title { font-weight: 600; font-size: 13px; }
.tf-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; font-size: 11px; color: #64748b; }
.status { font-weight: 700; text-transform: uppercase; }
.status.pending { color: #b45309; }
.status.in_progress { color: #2563eb; }
.status.completed { color: #15803d; }
.tf-detail { margin-top: 12px; }
.tf-raw {
  font-size: 11px;
  background: #f8fafc;
  padding: 10px;
  border-radius: 8px;
  overflow: auto;
  max-height: 240px;
}
.tf-empty, .tf-error { font-size: 13px; color: #64748b; }
.tf-error { color: #b91c1c; }
</style>
