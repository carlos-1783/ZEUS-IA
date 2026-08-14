<template>
  <div class="kpi-page-shell">
    <header class="kpi-page-header">
      <router-link class="kpi-back" to="/dashboard">← Dashboard</router-link>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="kpi-subtitle">{{ subtitle }}</p>
    </header>
    <div v-if="loading" class="kpi-loading">Cargando…</div>
    <p v-else-if="error" class="kpi-error">{{ error }}</p>
    <slot v-else />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
</script>

<style scoped>
.kpi-page-shell {
  min-height: 100vh;
  padding: 32px;
  background: var(--zeus-bg, #f7f8fb);
  color: var(--zeus-text, #0f172a);
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
  box-sizing: border-box;
}

.kpi-page-header {
  margin-bottom: 24px;
}

.kpi-back {
  color: var(--zeus-accent, #3b82f6);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  display: inline-block;
  margin-bottom: 12px;
}

.kpi-back:hover {
  text-decoration: underline;
}

.kpi-page-header h1 {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  color: var(--zeus-text, #0f172a);
}

.kpi-subtitle {
  margin: 0;
  color: var(--zeus-text-secondary, #52607a);
  font-size: 14px;
}

.kpi-loading,
.kpi-error {
  padding: 16px;
  border-radius: var(--zeus-radius, 12px);
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e5e9f0);
}

.kpi-error {
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.3);
  background: var(--zeus-warning-soft, #fef6e7);
}
</style>
