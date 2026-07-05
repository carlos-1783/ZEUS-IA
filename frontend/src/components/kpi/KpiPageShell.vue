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
  padding: 24px;
  background: #0a0e1a;
  color: #fff;
  box-sizing: border-box;
}

.kpi-page-header {
  margin-bottom: 24px;
}

.kpi-back {
  color: #3b82f6;
  text-decoration: none;
  font-size: 14px;
  display: inline-block;
  margin-bottom: 12px;
}

.kpi-back:hover {
  text-decoration: underline;
}

.kpi-page-header h1 {
  margin: 0 0 8px;
  font-size: 28px;
}

.kpi-subtitle {
  margin: 0;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

.kpi-loading,
.kpi-error {
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
}

.kpi-error {
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
</style>
