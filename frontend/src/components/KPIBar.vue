<template>
  <section class="kpi-bar" aria-label="Executive KPIs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="kpi-item kpi-card"
      :class="{
        'kpi-item--alert': item.key === 'alerts' && Number(item.value) > 0,
        'kpi-item--clickable': !!item.route,
      }"
      :title="item.route ? `Ver ${item.label}` : item.label"
      @click="onKpiClick(item)"
    >
      <!-- Badge gunmetal uniforme con icono de trazo en plata: el color
           semántico va solo en la cifra (.kpi-value--ok / --warn). -->
      <span class="kpi-icon-badge" aria-hidden="true">
        <svg
          v-if="ICONS[item.key]"
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path v-for="(d, i) in ICONS[item.key]" :key="i" :d="d" />
        </svg>
        <span v-else class="kpi-icon-fallback">{{ item.icon }}</span>
      </span>
      <span class="kpi-text">
        <span class="kpi-value" :class="item.tone ? `kpi-value--${item.tone}` : null">{{ item.value }}</span>
        <span class="kpi-label">{{ item.label }}</span>
      </span>
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

// Iconos por semántica del KPI (trazo, sin relleno).
const ICONS = {
  // Agentes: usuarios
  agents_active: [
    'M16 20v-1.6a3.4 3.4 0 0 0-3.4-3.4H7.4A3.4 3.4 0 0 0 4 18.4V20',
    'M10 11.6a3.3 3.3 0 1 0 0-6.6 3.3 3.3 0 0 0 0 6.6z',
    'M20 20v-1.6a3.4 3.4 0 0 0-2.4-3.25',
    'M15.4 5.1a3.3 3.3 0 0 1 0 6.4',
  ],
  // Tareas: checklist
  tasks_running: [
    'M4 6.5l1.6 1.6L8.5 5.2',
    'M4 12.5l1.6 1.6 2.9-2.9',
    'M4.6 18.4h3.3',
    'M11.5 6.8H20',
    'M11.5 12.8H20',
    'M11.5 18.4H20',
  ],
  // Eficiencia: indicador / gauge
  efficiency: [
    'M4.2 17.5a8.6 8.6 0 1 1 15.6 0',
    'M12 13.6l3.6-4.1',
    'M12 15.1a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z',
    'M7.4 17.5h9.2',
  ],
  // Alertas: triángulo de aviso
  alerts: [
    'M10.3 4.2L2.9 17.1A2 2 0 0 0 4.6 20h14.8a2 2 0 0 0 1.7-2.9L13.7 4.2a2 2 0 0 0-3.4 0z',
    'M12 9.5v4',
    'M12 16.8h.01',
  ],
  // Automatizaciones: rayo
  automations: ['M13 2.8L4.6 13.4h6.6L10.6 21.2 19 10.6h-6.6L13 2.8z'],
  // Sistema: servidor
  system_health: [
    'M5 3.8h14a1.4 1.4 0 0 1 1.4 1.4v4a1.4 1.4 0 0 1-1.4 1.4H5a1.4 1.4 0 0 1-1.4-1.4v-4A1.4 1.4 0 0 1 5 3.8z',
    'M5 13.4h14a1.4 1.4 0 0 1 1.4 1.4v4a1.4 1.4 0 0 1-1.4 1.4H5a1.4 1.4 0 0 1-1.4-1.4v-4A1.4 1.4 0 0 1 5 13.4z',
    'M7.2 7.2h.01',
    'M7.2 16.8h.01',
  ],
}

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
  gap: 12px;
  height: 100%;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

/* Lámina metálica (platino / grafito según tema). */
.kpi-item {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: 11px;
  background: var(--metal-face, var(--zeus-surface));
  border: 1px solid var(--metal-edge, var(--zeus-border));
  border-bottom-color: var(--metal-edge-bottom, var(--zeus-border));
  border-radius: 12px;
  padding: 11px 12px;
  min-width: 0;
  overflow: hidden;
  font: inherit;
  color: inherit;
  text-align: left;
  box-shadow: var(--metal-shadow, var(--zeus-shadow-sm));
}

/* Brillo especular diagonal: sobre el metal y bajo el contenido
   (z-index -1 dentro del contexto aislado); no tapa texto ni clics. */
.kpi-item::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background: var(--metal-sheen, none);
  opacity: var(--metal-sheen-opacity, 0);
  mix-blend-mode: screen;
  pointer-events: none;
}

.kpi-icon-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  flex-shrink: 0;
  background: var(--gun-badge, var(--zeus-raised));
  box-shadow: var(--gun-badge-shadow, none);
  color: var(--gun-icon, var(--zeus-text));
}

.kpi-icon-fallback {
  font-size: 14px;
  line-height: 1;
}

.kpi-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.kpi-item--clickable {
  cursor: pointer;
  transition: transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

.kpi-item--clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--metal-shadow-hover, var(--zeus-shadow-md));
}

.kpi-item--clickable:active {
  transform: translateY(0);
}

.kpi-item:focus-visible {
  outline: 2px solid var(--volt, #2f82f0);
  outline-offset: 2px;
}

/* Alertas pendientes: filo ámbar en el borde (el color va al dato). */
.kpi-item--alert {
  border-color: rgba(239, 162, 29, 0.7);
  border-bottom-color: rgba(239, 162, 29, 0.9);
}

.kpi-value,
.kpi-label {
  /* Nunca se comprimen: si falta alto, crece la tarjeta, no desaparece la cifra. */
  flex-shrink: 0;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink, var(--zeus-text));
  line-height: 1.1;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.kpi-value--ok {
  color: var(--ok-ink, var(--zeus-success-text));
}

.kpi-value--warn {
  color: var(--warn-ink, var(--zeus-warning-text));
}

.kpi-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-2, var(--zeus-text-secondary));
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

@media (max-width: 1200px) and (min-width: 769px) {
  .kpi-item {
    gap: 8px;
    padding: 10px 9px;
  }

  .kpi-icon-badge {
    width: 30px;
    height: 30px;
    border-radius: 9px;
  }

  .kpi-value {
    font-size: 18px;
  }
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
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 6px;
    padding: 10px 6px;
  }

  .kpi-text {
    align-items: center;
  }

  .kpi-icon-badge {
    width: 28px;
    height: 28px;
    border-radius: 8px;
  }

  .kpi-value {
    font-size: 19px;
  }

  .kpi-label {
    font-size: 11px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .kpi-item--clickable,
  .kpi-item--clickable:hover,
  .kpi-item--clickable:active {
    transition: none;
    transform: none;
  }
}
</style>
