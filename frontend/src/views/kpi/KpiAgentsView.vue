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
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  font-size: 14px;
}

.pill.online {
  color: #10b981;
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .kpi-list-item {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
