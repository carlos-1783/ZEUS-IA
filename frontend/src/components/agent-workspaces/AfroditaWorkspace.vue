<template>
  <div class="afrodita-workspace">
    <header class="workspace-header">
      <div>
        <h3>🤝 AFRODITA</h3>
        <p class="subtitle">RRHH · Operaciones · Workspace IA (dominios separados)</p>
        <ThalosExecutionBadge
          v-if="globalStatus || zeusStatus"
          class="workspace-badges"
          :global-mode="zeusStatus?.execution_mode ?? globalStatus?.execution_mode"
          :real-execution="verifiedReal"
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
      <AfroditaWorkspacePanel v-else :connected="workspaceConnected" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  executionModeLabel,
  fetchAfroditaStatus,
  type AfroditaExecutionMode,
  type AfroditaTruthStatus,
} from '@/api/afrodita_workspace_api'
import {
  fetchZeusExecutionStatus,
  moduleStatusLabel,
  type ZeusExecutionStatus,
  type ZeusModuleStatus,
} from '@/api/zeus_status_api'
import { isVerifiedReal } from '@/utils/zeus_safe_lock'
import AfroditaToolsPanel from './AfroditaToolsPanel.vue'
import AfroditaOpsPanel from './AfroditaOpsPanel.vue'
import AfroditaWorkspacePanel from './AfroditaWorkspacePanel.vue'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

type TabId = 'rrhh' | 'ops' | 'workspace'

const activeTab = ref<TabId>('rrhh')
const globalStatus = ref<AfroditaTruthStatus | null>(null)
const zeusStatus = ref<ZeusExecutionStatus | null>(null)

const verifiedReal = computed(() => isVerifiedReal(zeusStatus.value ?? globalStatus.value))

const modeLabel = computed(() => {
  const zeusMode = zeusStatus.value?.execution_mode
  if (zeusMode) return executionModeLabel(zeusMode)
  return executionModeLabel(globalStatus.value?.execution_mode)
})

const workspaceConnected = computed(
  () => globalStatus.value?.workspace?.connected === true
)

const workspaceTabLabel = computed(() => {
  const wsMod = zeusStatus.value?.modules?.workspace
  if (wsMod?.status) return moduleStatusLabel(wsMod.status)
  const ws = globalStatus.value?.workspace
  if (!ws?.enabled) return 'UNKNOWN'
  if (ws.connected) return wsMod?.status ? moduleStatusLabel(wsMod.status) : 'UNKNOWN'
  if (ws.status === 'ERROR') return 'ERROR'
  return 'UNKNOWN'
})

const tabModuleStatus = (tabId: TabId): ZeusModuleStatus | AfroditaExecutionMode | undefined => {
  const mods = zeusStatus.value?.modules
  if (mods) {
    if (tabId === 'rrhh') return mods.rrhh?.status
    if (tabId === 'ops') return mods.ops?.status
    return mods.workspace?.status
  }
  if (tabId === 'workspace') {
    return zeusStatus.value?.modules?.workspace?.status
  }
  return globalStatus.value?.execution_mode
}

const tabLabel = (tabId: TabId) => {
  const mod = tabModuleStatus(tabId)
  if (tabId === 'workspace') return workspaceTabLabel.value
  return moduleStatusLabel(mod) || modeLabel.value
}

const tabClass = (tabId: TabId) => {
  const mod = tabModuleStatus(tabId)
  if (mod === 'REAL' || mod === 'REAL_WITH_OUTPUT') return 'real'
  if (mod === 'ERROR') return 'error'
  if (mod === 'PARTIAL_REAL' || mod === 'EMPTY_REAL') return 'partial'
  return statusClassFor(globalStatus.value?.execution_mode)
}

const statusClassFor = (mode: AfroditaExecutionMode | undefined) => {
  if (mode === 'REAL') return 'real'
  if (mode === 'ERROR') return 'error'
  return 'sim'
}

const tabs = computed(() => {
  return [
    { id: 'rrhh' as const, name: 'RRHH', status: tabLabel('rrhh'), statusClass: tabClass('rrhh') },
    { id: 'ops' as const, name: 'OPERACIONES', status: tabLabel('ops'), statusClass: tabClass('ops') },
    {
      id: 'workspace' as const,
      name: 'WORKSPACE',
      status: tabLabel('workspace'),
      statusClass: tabClass('workspace'),
    },
  ]
})

onMounted(async () => {
  try {
    const [afrodita, zeus] = await Promise.all([
      fetchAfroditaStatus(),
      fetchZeusExecutionStatus().catch(() => null),
    ])
    globalStatus.value = afrodita
    zeusStatus.value = zeus
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
.tab-status.partial { background: #e0e7ff; color: #4338ca; }
.tab-status.sim { background: #fef3c7; color: #b45309; }
.tab-status.error { background: #fee2e2; color: #b91c1c; }

.domain-panel {
  min-height: 200px;
}

@media (max-width: 600px) {
  .afrodita-workspace {
    padding: 20px 16px 80px;
  }
}
</style>
