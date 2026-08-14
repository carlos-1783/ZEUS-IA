<template>
  <KpiPageShell title="Agentes activos" subtitle="Olimpo ZEUS — 6 agentes operativos">
    <ul class="kpi-list">
      <li v-for="agent in agents" :key="agent.name" class="kpi-list-item">
        <strong>{{ agent.name }}</strong>
        <span>{{ agent.role }}</span>
        <span class="pill online">Online</span>
      </li>
    </ul>
  </KpiPageShell>
</template>

<script setup>
import KpiPageShell from '@/components/kpi/KpiPageShell.vue'

const agents = [
  { name: 'ZEUS CORE', role: 'Supreme Orchestrator' },
  { name: 'PERSEO', role: 'Growth Strategist' },
  { name: 'RAFAEL', role: 'Fiscal Guardian' },
  { name: 'THALOS', role: 'Cybersecurity Defender' },
  { name: 'JUSTICIA', role: 'Legal & GDPR Advisor' },
  { name: 'AFRODITA', role: 'HR & Logistics Manager' },
]
</script>

<style scoped>
.kpi-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.kpi-list-item {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e5e9f0);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow-sm);
  font-size: 14px;
  color: var(--zeus-text-secondary, #52607a);
  transition: box-shadow var(--zeus-transition, 150ms), border-color var(--zeus-transition, 150ms);
}

.kpi-list-item:hover {
  box-shadow: var(--zeus-shadow);
  border-color: var(--zeus-border-strong, #d7dce5);
}

.kpi-list-item strong {
  color: var(--zeus-text, #0f172a);
}

.pill.online {
  color: #0d9668;
  background: var(--zeus-success-soft, #e9faf3);
  padding: 4px 10px;
  border-radius: var(--zeus-radius-full, 999px);
  font-size: 12px;
  font-weight: 600;
  justify-self: end;
}

@media (max-width: 768px) {
  .kpi-list-item {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
