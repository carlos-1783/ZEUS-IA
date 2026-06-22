<template>
  <div class="afrodita-workspace">
    <header class="workspace-header">
      <div>
        <h3>🤝 AFRODITA</h3>
        <p class="subtitle">RRHH · Operaciones · Workspace IA (dominios separados)</p>
        <ThalosExecutionBadge
          v-if="globalStatus"
          class="workspace-badges"
          :global-mode="globalStatus.system_default_mode"
          :control="globalStatus.afrodita_control"
          :data-origin="globalStatus.data_origin"
          :real-execution="globalStatus.real_execution"
        />
      </div>
    </header>

    <nav class="domain-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        role="tab"
        type="button"
        :class="{ active: activeTab === tab.id }"
        :aria-selected="activeTab === tab.id"
        @click="activeTab = tab.id"
      >
        {{ tab.name }}
        <span class="tab-status" :class="tab.statusClass">{{ tab.status }}</span>
      </button>
    </nav>

    <section class="domain-panel">
      <AfroditaToolsPanel v-if="activeTab === 'rrhh'" />
      <AfroditaOpsPanel v-else-if="activeTab === 'ops'" />
      <WorkspacePlaybooks v-else />
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchAfroditaRrhhStatus, type AfroditaStatusResponse } from '@/api/afrodita_workspace_api'
import AfroditaToolsPanel from './AfroditaToolsPanel.vue'
import AfroditaOpsPanel from './AfroditaOpsPanel.vue'
import WorkspacePlaybooks from './WorkspacePlaybooks.vue'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

type TabId = 'rrhh' | 'ops' | 'workspace'

const activeTab = ref<TabId>('rrhh')
const globalStatus = ref<AfroditaStatusResponse | null>(null)

const tabs = [
  { id: 'rrhh' as const, name: 'RRHH', status: 'REAL', statusClass: 'real' },
  { id: 'ops' as const, name: 'OPERACIONES', status: 'REAL_PARTIAL', statusClass: 'partial' },
  { id: 'workspace' as const, name: 'WORKSPACE', status: 'SIMULATION_LAYER', statusClass: 'sim' },
]

onMounted(async () => {
  try {
    globalStatus.value = await fetchAfroditaRrhhStatus()
  } catch {
    /* optional */
  }
})
</script>

<style scoped>
.afrodita-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 32px 48px 64px;
  background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 55%);
  min-height: calc(100vh - 96px);
  max-width: 98%;
  width: calc(100% - 24px);
  margin: 0 auto 24px;
}

.workspace-header h3 {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.subtitle {
  font-size: 15px;
  color: #475569;
  margin: 4px 0 0;
}

.workspace-badges {
  margin-top: 10px;
}

.domain-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  border-bottom: 1px solid rgba(148, 163, 184, 0.35);
  padding-bottom: 8px;
}

.domain-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid transparent;
  border-radius: 10px 10px 0 0;
  background: transparent;
  color: #475569;
  font-weight: 600;
  cursor: pointer;
}

.domain-tabs button.active {
  background: #fff;
  border-color: rgba(148, 163, 184, 0.35);
  border-bottom-color: #fff;
  color: #0f172a;
  margin-bottom: -1px;
}

.tab-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 6px;
  font-weight: 700;
}

.tab-status.real { background: #dcfce7; color: #15803d; }
.tab-status.partial { background: #fef3c7; color: #b45309; }
.tab-status.sim { background: #f1f5f9; color: #64748b; }

.domain-panel {
  min-height: 200px;
}

@media (max-width: 600px) {
  .afrodita-workspace {
    padding: 20px 16px 80px;
  }
}
</style>
