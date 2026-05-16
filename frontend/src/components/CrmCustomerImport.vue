<template>
  <div class="import-overlay" @click.self="close">
    <div class="import-modal" role="dialog" aria-labelledby="import-title">
      <header class="import-header">
        <h2 id="import-title">{{ t('officeCrm.import.title') }}</h2>
        <button type="button" class="import-close" :aria-label="t('officeCrm.cancel')" @click="close">×</button>
      </header>

      <p v-if="error" class="import-error" role="alert">{{ error }}</p>

      <section v-if="step === 'upload'" class="import-step">
        <p class="import-hint">{{ t('officeCrm.import.hint') }}</p>
        <label class="import-file-label">
          <input
            ref="fileInput"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            class="import-file-input"
            @change="onFileSelected"
          />
          <span class="btn-secondary">{{ t('officeCrm.import.chooseFile') }}</span>
          <span v-if="selectedFile" class="import-filename">{{ selectedFile.name }}</span>
        </label>
        <div class="import-actions">
          <button type="button" class="btn-primary" :disabled="!selectedFile || loading" @click="runPreview">
            {{ loading ? t('officeCrm.loading') : t('officeCrm.import.analyze') }}
          </button>
          <button type="button" class="btn-secondary" @click="close">{{ t('officeCrm.cancel') }}</button>
        </div>
      </section>

      <section v-else-if="step === 'mapping'" class="import-step">
        <p class="import-meta">
          {{ t('officeCrm.import.rowsFound', { count: totalRows, file: previewData?.filename || '' }) }}
        </p>

        <div class="import-mapping">
          <h3>{{ t('officeCrm.import.mapColumns') }}</h3>
          <div v-for="field in mappingFields" :key="field.key" class="mapping-row">
            <label>{{ field.label }}</label>
            <select v-model="mapping[field.key]">
              <option :value="null">{{ t('officeCrm.import.columnNone') }}</option>
              <option v-for="col in columns" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
        </div>

        <div v-if="previewRows.length" class="import-preview">
          <h3>{{ t('officeCrm.import.preview') }}</h3>
          <div class="preview-table-wrap">
            <table class="preview-table">
              <thead>
                <tr>
                  <th>{{ t('officeCrm.name') }}</th>
                  <th>{{ t('officeCrm.email') }}</th>
                  <th>{{ t('officeCrm.phone') }}</th>
                  <th>{{ t('officeCrm.taxId') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in previewRows" :key="i">
                  <td>{{ row.name || '—' }}</td>
                  <td>{{ row.email || '—' }}</td>
                  <td>{{ row.phone || '—' }}</td>
                  <td>{{ row.tax_id || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="import-actions">
          <button type="button" class="btn-secondary" @click="step = 'upload'">{{ t('officeCrm.import.back') }}</button>
          <button type="button" class="btn-primary" :disabled="!mapping.name || loading" @click="runImport">
            {{ loading ? t('officeCrm.loading') : t('officeCrm.import.confirm') }}
          </button>
        </div>
      </section>

      <section v-else-if="step === 'done'" class="import-step import-done">
        <p class="import-success">{{ result?.message }}</p>
        <ul class="import-stats">
          <li>{{ t('officeCrm.import.imported', { count: result?.imported ?? 0 }) }}</li>
          <li>{{ t('officeCrm.import.skipped', { count: result?.skipped ?? 0 }) }}</li>
          <li v-if="result?.skipped_duplicates">
            {{ t('officeCrm.import.skippedDuplicates', { count: result.skipped_duplicates }) }}
          </li>
        </ul>
        <ul v-if="result?.errors?.length" class="import-warnings">
          <li v-for="(err, i) in result.errors.slice(0, 10)" :key="i">{{ err }}</li>
        </ul>
        <div class="import-actions">
          <button type="button" class="btn-primary" @click="finish">{{ t('officeCrm.import.done') }}</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const emit = defineEmits(['close', 'imported'])

const { t } = useI18n()

const step = ref('upload')
const loading = ref(false)
const error = ref('')
const selectedFile = ref(null)
const fileInput = ref(null)
const previewData = ref(null)
const result = ref(null)

const columns = ref([])
const previewRows = ref([])
const totalRows = ref(0)

const mapping = reactive({
  name: null,
  email: null,
  phone: null,
  notes: null,
  tax_id: null,
})

const mappingFields = computed(() => [
  { key: 'name', label: t('officeCrm.name') + ' *' },
  { key: 'email', label: t('officeCrm.email') },
  { key: 'phone', label: t('officeCrm.phone') },
  { key: 'tax_id', label: t('officeCrm.taxId') },
  { key: 'notes', label: t('officeCrm.notes') },
])

function close() {
  emit('close')
}

function onFileSelected(ev) {
  const f = ev.target?.files?.[0]
  selectedFile.value = f || null
  error.value = ''
}

async function parseError(e) {
  if (e?.response) {
    try {
      const body = await e.response.clone().json()
      if (body?.detail) {
        return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* ignore */
    }
  }
  return e?.message || t('officeCrm.errorGeneric')
}

function applySuggested(suggested) {
  mapping.name = suggested?.name ?? null
  mapping.email = suggested?.email ?? null
  mapping.phone = suggested?.phone ?? null
  mapping.notes = suggested?.notes ?? null
  mapping.tax_id = suggested?.tax_id ?? null
}

async function runPreview() {
  if (!selectedFile.value) return
  loading.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const res = await api.postFormData('/api/v1/crm/import/preview', fd)
    previewData.value = res
    columns.value = res?.columns || []
    previewRows.value = res?.preview_rows || []
    totalRows.value = res?.total_rows ?? 0
    applySuggested(res?.suggested_mapping)
    if (!mapping.name && columns.value.length) {
      mapping.name = columns.value[0]
    }
    step.value = 'mapping'
  } catch (e) {
    error.value = await parseError(e)
  } finally {
    loading.value = false
  }
}

async function runImport() {
  if (!selectedFile.value || !mapping.name) return
  loading.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    fd.append(
      'mapping',
      JSON.stringify({
        name: mapping.name,
        email: mapping.email,
        phone: mapping.phone,
        notes: mapping.notes,
        tax_id: mapping.tax_id,
      }),
    )
    const res = await api.postFormData('/api/v1/crm/import/clients', fd)
    result.value = res
    step.value = 'done'
  } catch (e) {
    error.value = await parseError(e)
  } finally {
    loading.value = false
  }
}

function finish() {
  emit('imported')
  close()
}
</script>
