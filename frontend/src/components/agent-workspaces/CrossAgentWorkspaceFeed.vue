<template>
  <section class="cross-agent-feed">
    <header class="caf-header">
      <div>
        <h4>🔗 Flujos ZEUS — {{ agentLabel }}</h4>
        <p class="hint">Contratos RRHH, compliance y handoffs cross-agent (TeamFlow en BD).</p>
      </div>
    </header>
    <TeamFlowPanel :ref="setRef" :agent="agent" />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import TeamFlowPanel from './TeamFlowPanel.vue'

const props = defineProps<{ agent: string }>()

const panelRef = ref<InstanceType<typeof TeamFlowPanel> | null>(null)
const setRef = (el: unknown) => {
  panelRef.value = el as InstanceType<typeof TeamFlowPanel> | null
}

const agentLabel = computed(() => props.agent.toUpperCase())

defineExpose({
  reload: () => panelRef.value?.reload?.(),
})
</script>

<style scoped>
.cross-agent-feed {
  margin-bottom: 24px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #f8fafc;
}
.caf-header h4 {
  margin: 0;
  font-size: 15px;
}
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}
</style>
