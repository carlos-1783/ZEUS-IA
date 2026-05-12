<template>
  <div class="settings-page">
    <header class="settings-page-header">
      <button type="button" class="back-btn" @click="goBack">{{ $t('userSettings.back') }}</button>
      <h1>{{ $t('userSettings.pageTitle') }}</h1>
    </header>
    <div class="settings-page-grid">
      <UserAppSettings />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import UserAppSettings from '@/components/UserAppSettings.vue'
import { useSettingsStore } from '@/stores/settings'

const router = useRouter()
const settingsStore = useSettingsStore()

onMounted(() => {
  void settingsStore.bootstrapFromBackend()
})

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/dashboard')
}
</script>

<style scoped>
.settings-page {
  min-height: 100vh;
  padding: 24px 20px 48px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  color: #fff;
}

.settings-page-header {
  max-width: 720px;
  margin: 0 auto 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-page-header h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}

.back-btn {
  align-self: flex-start;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  cursor: pointer;
  font-size: 0.9rem;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}

.settings-page-grid {
  max-width: 720px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}
</style>
