<template>
  <div class="payroll-drafts">
    <div class="payroll-header">
      <router-link to="/dashboard" class="back-link">← Volver al Dashboard</router-link>
      <h1>📋 Borradores de nómina</h1>
      <p class="subtitle">Listado de nóminas en borrador. Descarga el PDF para revisión.</p>
    </div>
    <div v-if="loading" class="loading">Cargando…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="!drafts.length" class="empty">No hay borradores de nómina.</div>
    <div v-else class="drafts-list">
      <div
        v-for="d in drafts"
        :key="d.id"
        class="draft-card"
      >
        <div class="draft-info">
          <span class="draft-period">{{ d.month }} {{ d.year }}</span>
          <span class="draft-salary">Bruto: {{ d.gross_salary?.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) }} · Neto est.: {{ d.net_salary_estimated?.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) }}</span>
          <span class="draft-status">{{ d.status }}</span>
        </div>
        <button class="btn-download" @click="downloadDraft(d.id)" :disabled="downloading === d.id">
          {{ downloading === d.id ? 'Descargando…' : 'Descargar PDF' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const loading = ref(true)
const error = ref(null)
const drafts = ref([])
const downloading = ref(null)

async function loadDrafts() {
  loading.value = true
  error.value = null
  try {
    const res = await api.get('/api/v1/payroll/drafts')
    if (res?.success && Array.isArray(res.drafts)) {
      drafts.value = res.drafts
    } else {
      drafts.value = []
    }
  } catch (e) {
    error.value = e?.message || 'Error al cargar borradores'
    drafts.value = []
  } finally {
    loading.value = false
  }
}

async function downloadDraft(id) {
  downloading.value = id
  try {
    const blob = await api.getBlob(`/api/v1/payroll/drafts/${id}/download`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `nomina-borrador-${id}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e?.message || 'Error al descargar'
  } finally {
    downloading.value = null
  }
}

onMounted(loadDrafts)
</script>

<style scoped>
.payroll-drafts {
  max-width: 800px;
  margin: 0 auto;
  padding: 1.5rem;
}
.back-link {
  display: inline-block;
  margin-bottom: 0.75rem;
  color: #2563eb;
  text-decoration: none;
  font-size: 0.9rem;
}
.back-link:hover {
  text-decoration: underline;
}
.payroll-header {
  margin-bottom: 1.5rem;
}
.payroll-header h1 {
  font-size: 1.5rem;
  margin: 0 0 0.25rem 0;
}
.subtitle {
  color: #666;
  margin: 0;
}
.loading, .error, .empty {
  padding: 2rem;
  text-align: center;
  color: #666;
}
.error {
  color: #c00;
}
.drafts-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.draft-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 8px;
  border: 1px solid #eee;
}
.draft-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.draft-period {
  font-weight: 600;
}
.draft-salary {
  font-size: 0.9rem;
  color: #555;
}
.draft-status {
  font-size: 0.8rem;
  color: #888;
}
.btn-download {
  padding: 0.5rem 1rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-download:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn-download:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
