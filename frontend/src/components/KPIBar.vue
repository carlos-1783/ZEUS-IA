<template>
  <section class="kpi-bar" aria-label="Executive KPIs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="kpi-item kpi-card"
      :class="{
        'kpi-item--alert': item.key === 'alerts' && item.value !== '0' && item.value !== 0,
        'kpi-item--clickable': !!item.route,
      }"
      :title="item.route ? `Ver ${item.label}` : item.label"
      @click="onKpiClick(item)"
    >
      <span class="kpi-icon" aria-hidden="true">{{ item.icon }}</span>
      <span class="kpi-value">{{ item.value }}</span>
      <span class="kpi-label">{{ item.label }}</span>
    </button>
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineProps({
  items: {
    type: Array,
    required: true,
  },
})

const router = useRouter()

const onKpiClick = (item) => {
  if (item?.route) {
    router.push(item.route)
  }
}
</script>

<style scoped>
.kpi-bar {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  height: 100%;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.kpi-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  background: linear-gradient(135deg, rgba(26, 31, 46, 0.95) 0%, rgba(15, 20, 25, 0.95) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 6px 4px;
  min-width: 0;
  overflow: hidden;
  font: inherit;
  color: inherit;
  text-align: center;
}

.kpi-item--clickable {
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.kpi-item--clickable:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.45);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
}

.kpi-item--clickable:active {
  transform: translateY(0);
}

.kpi-item--alert {
  border-color: rgba(245, 158, 11, 0.45);
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.15);
}

.kpi-icon {
  font-size: 14px;
  line-height: 1;
}

.kpi-value {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.kpi-label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.55);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-align: center;
  line-height: 1.2;
}

@media (max-width: 768px) {
  .kpi-bar {
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(2, auto);
    gap: 8px;
    height: auto;
  }

  .kpi-item,
  .kpi-card {
    padding: 8px;
  }

  .kpi-value {
    font-size: 12px;
  }

  .kpi-label {
    font-size: 9px;
  }

  .kpi-icon {
    font-size: 12px;
  }
}
</style>
