<template>
  <div class="thalos-badges" :class="{ inline: inline }">
    <span v-if="showGlobal && globalMode" class="badge global" :class="modeClass(globalMode)">
      {{ globalMode }}
    </span>
    <span v-if="moduleBadge" class="badge module" :class="uiClass(moduleBadge)">
      {{ moduleBadge }}
    </span>
    <span v-if="dataOrigin" class="badge origin" :title="'Origen de datos'">
      {{ originLabel }}
    </span>
    <span v-if="realExecution !== undefined" class="badge exec" :class="realExecution ? 'real' : 'sim'">
      {{ realExecution ? 'Ejecución real' : 'Sin ejecución real' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  extractControlMetadata,
} from '@/api/thalos_workspace_api'

const props = withDefaults(
  defineProps<{
    globalMode?: string | null
    control?: unknown
    moduleBadge?: string | null
    dataOrigin?: string | null
    realExecution?: boolean
    showGlobal?: boolean
    inline?: boolean
  }>(),
  {
    globalMode: null,
    moduleBadge: null,
    dataOrigin: null,
    realExecution: undefined,
    showGlobal: true,
    inline: false,
  }
)

const resolvedControl = computed(() => {
  const c = extractControlMetadata(props.control)
  if (c) return c
  if (props.control && typeof props.control === 'object') {
    const raw = props.control as unknown as Record<string, unknown>
    if (typeof raw.ui_badge === 'string') {
      return {
        execution_mode: String(raw.execution_mode || ''),
        data_origin: String(raw.data_origin || ''),
        real_execution: Boolean(raw.real_execution),
        module: String(raw.module || ''),
        ui_badge: String(raw.ui_badge),
        flags: (raw.flags as Record<string, boolean>) || {},
      }
    }
  }
  return null
})

const moduleBadge = computed(() => props.moduleBadge ?? resolvedControl.value?.ui_badge ?? null)
const dataOrigin = computed(() => props.dataOrigin ?? resolvedControl.value?.data_origin ?? null)
const realExecution = computed(() =>
  props.realExecution !== undefined ? props.realExecution : resolvedControl.value?.real_execution
)

const originLabel = computed(() => {
  const o = dataOrigin.value
  if (!o) return ''
  const map: Record<string, string> = {
    backend: 'Backend',
    user_input: 'Entrada usuario',
    mock: 'Simulado',
    mixed: 'Mixto',
  }
  return map[o] || o
})

const modeClass = (mode: string) => {
  if (mode === 'REAL_ACTIVE') return 'active'
  if (mode === 'REAL_SAFE' || mode === 'READ_ONLY') return 'safe'
  return 'simulation'
}

const uiClass = (badge: string) => {
  if (badge === 'REAL') return 'real'
  if (badge === 'PARCIAL') return 'partial'
  if (badge === 'NONE') return 'none'
  return 'simulated'
}
</script>

<style scoped>
.thalos-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.thalos-badges.inline {
  display: inline-flex;
}
.badge {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 3px 8px;
  border-radius: 999px;
  text-transform: uppercase;
}
.badge.global.simulation {
  background: #e2e8f0;
  color: #475569;
}
.badge.global.safe {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge.global.active {
  background: #dcfce7;
  color: #15803d;
}
.badge.module.real {
  background: #0f766e;
  color: #fff;
}
.badge.module.partial {
  background: #fef3c7;
  color: #b45309;
}
.badge.module.simulated {
  background: #f1f5f9;
  color: #64748b;
}
.badge.module.none {
  background: #e5e7eb;
  color: #6b7280;
}
.badge.origin {
  background: #f8fafc;
  color: #334155;
  border: 1px solid #e2e8f0;
  text-transform: none;
}
.badge.exec.real {
  background: #ecfdf5;
  color: #047857;
}
.badge.exec.sim {
  background: #fff7ed;
  color: #c2410c;
}
</style>
