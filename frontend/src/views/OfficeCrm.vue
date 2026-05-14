<template>
  <div class="office-crm">
    <header class="crm-header">
      <router-link to="/dashboard" class="back-link">← {{ t('officeCrm.backToDashboard') }}</router-link>
      <h1>{{ t('officeCrm.title') }}</h1>
      <p class="subtitle">{{ t('officeCrm.subtitle') }}</p>
    </header>

    <p v-if="globalError" class="global-error" role="alert">{{ globalError }}</p>

    <div class="crm-layout">
      <section class="panel customers-panel">
        <h2>{{ t('officeCrm.clients') }}</h2>
        <button type="button" class="btn-primary" @click="showNewCustomer = !showNewCustomer">
          {{ showNewCustomer ? t('officeCrm.cancel') : t('officeCrm.newClient') }}
        </button>

        <form v-if="showNewCustomer" class="form-card" @submit.prevent="createCustomer">
          <label>{{ t('officeCrm.name') }} *</label>
          <input v-model="newCustomer.name" required minlength="2" maxlength="100" />
          <label>{{ t('officeCrm.email') }}</label>
          <input v-model="newCustomer.email" type="email" />
          <label>{{ t('officeCrm.phone') }}</label>
          <input v-model="newCustomer.phone" maxlength="20" />
          <label>{{ t('officeCrm.taxId') }}</label>
          <input v-model="newCustomer.tax_id" maxlength="50" />
          <label class="checkbox">
            <input v-model="newCustomer.is_company" type="checkbox" />
            {{ t('officeCrm.isCompany') }}
          </label>
          <button type="submit" class="btn-primary" :disabled="savingCustomer">{{ t('officeCrm.saveClient') }}</button>
        </form>

        <div v-if="loadingCustomers" class="muted">{{ t('officeCrm.loading') }}</div>
        <ul v-else class="customer-list">
          <li
            v-for="c in customers"
            :key="c.id"
            :class="{ active: selectedCustomer?.id === c.id }"
            @click="openCustomer(c)"
          >
            <span class="cust-name">{{ c.name }}</span>
            <span v-if="c.email" class="cust-meta">{{ c.email }}</span>
          </li>
        </ul>
        <p v-if="!loadingCustomers && !customers.length" class="muted">{{ t('officeCrm.noClients') }}</p>
      </section>

      <section v-if="selectedCustomer" class="panel detail-panel">
        <h2>{{ selectedCustomer.name }}</h2>
        <p class="meta-line">
          <span v-if="selectedCustomer.email">{{ selectedCustomer.email }}</span>
          <span v-if="selectedCustomer.phone"> · {{ selectedCustomer.phone }}</span>
        </p>

        <h3>{{ t('officeCrm.records') }}</h3>
        <button type="button" class="btn-secondary" @click="showNewRecord = !showNewRecord">
          {{ showNewRecord ? t('officeCrm.cancel') : t('officeCrm.newRecord') }}
        </button>

        <form v-if="showNewRecord" class="form-card" @submit.prevent="createRecord">
          <label>{{ t('officeCrm.recordTitle') }} *</label>
          <input v-model="newRecord.title" required maxlength="255" />
          <label>{{ t('officeCrm.status') }}</label>
          <select v-model="newRecord.status">
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="closed">closed</option>
          </select>
          <label>{{ t('officeCrm.amount') }}</label>
          <input v-model.number="newRecord.amount" type="number" step="0.01" min="0" />
          <label>{{ t('officeCrm.notes') }}</label>
          <textarea v-model="newRecord.notes" rows="2" />
          <button type="submit" class="btn-primary" :disabled="savingRecord">{{ t('officeCrm.createRecord') }}</button>
        </form>

        <div v-if="loadingRecords" class="muted">{{ t('officeCrm.loading') }}</div>
        <table v-else-if="records.length" class="records-table">
          <thead>
            <tr>
              <th>{{ t('officeCrm.recordTitle') }}</th>
              <th>{{ t('officeCrm.status') }}</th>
              <th>{{ t('officeCrm.amount') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td>{{ r.title }}</td>
              <td>{{ r.status }}</td>
              <td>{{ formatMoney(r.amount) }}</td>
              <td class="actions">
                <button type="button" class="btn-small" @click="openCharge(r)">{{ t('officeCrm.charge') }}</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">{{ t('officeCrm.noRecords') }}</p>

        <div v-if="chargeRecord" class="charge-box">
          <h4>{{ t('officeCrm.chargeTitle') }} — {{ chargeRecord.title }}</h4>
          <form @submit.prevent="submitCharge">
            <label>{{ t('officeCrm.baseAmount') }} (€) *</label>
            <input v-model="chargeForm.base_amount" type="number" step="0.01" min="0.01" required />
            <label>{{ t('officeCrm.paymentMethod') }}</label>
            <select v-model="chargeForm.payment_method">
              <option value="efectivo">efectivo</option>
              <option value="tarjeta">tarjeta</option>
              <option value="bizum">bizum</option>
              <option value="transferencia">transferencia</option>
            </select>
            <label>{{ t('officeCrm.description') }}</label>
            <input v-model="chargeForm.description" maxlength="200" />
            <div class="charge-actions">
              <button type="submit" class="btn-primary" :disabled="charging">{{ t('officeCrm.registerCharge') }}</button>
              <button type="button" class="btn-secondary" @click="chargeRecord = null">{{ t('officeCrm.cancel') }}</button>
            </div>
          </form>
        </div>
      </section>

      <section v-if="selectedCustomer" class="panel activity-panel">
        <h2>{{ t('officeCrm.activity') }}</h2>
        <button type="button" class="btn-secondary" @click="loadActivity">{{ t('officeCrm.refreshActivity') }}</button>
        <div v-if="loadingActivity" class="muted">{{ t('officeCrm.loading') }}</div>
        <ul v-else class="activity-list">
          <li v-for="a in activity" :key="a.id" class="activity-item">
            <time class="activity-time">{{ formatDt(a.created_at) }}</time>
            <span class="activity-action">{{ a.action }}</span>
            <p v-if="a.summary" class="activity-summary">{{ a.summary }}</p>
          </li>
        </ul>
        <p v-if="!loadingActivity && !activity.length" class="muted">{{ t('officeCrm.noActivity') }}</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const { t } = useI18n()

const globalError = ref('')
const loadingCustomers = ref(true)
const loadingRecords = ref(false)
const loadingActivity = ref(false)
const customers = ref([])
const selectedCustomer = ref(null)
const records = ref([])
const activity = ref([])
const showNewCustomer = ref(false)
const showNewRecord = ref(false)
const savingCustomer = ref(false)
const savingRecord = ref(false)
const charging = ref(false)
const chargeRecord = ref(null)

const newCustomer = reactive({
  name: '',
  email: '',
  phone: '',
  tax_id: '',
  is_company: true,
})

const newRecord = reactive({
  title: '',
  status: 'open',
  amount: 0,
  notes: '',
})

const chargeForm = reactive({
  base_amount: '',
  payment_method: 'efectivo',
  description: '',
})

function formatMoney(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { style: 'currency', currency: 'EUR' })
}

function formatDt(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return String(iso)
  }
}

function errMessage(e) {
  const d = e?.response ? null : e?.message
  if (typeof d === 'string') return d
  return e?.message || t('officeCrm.errorGeneric')
}

async function loadCustomers() {
  globalError.value = ''
  loadingCustomers.value = true
  try {
    const res = await api.get('/api/v1/crm/customers')
    customers.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    globalError.value = errMessage(e)
    customers.value = []
  } finally {
    loadingCustomers.value = false
  }
}

async function createCustomer() {
  savingCustomer.value = true
  globalError.value = ''
  try {
    const body = {
      name: newCustomer.name.trim(),
      email: newCustomer.email?.trim() || null,
      phone: newCustomer.phone?.trim() || null,
      tax_id: newCustomer.tax_id?.trim() || null,
      is_company: newCustomer.is_company,
      is_active: true,
      contacts: [],
    }
    const res = await api.post('/api/v1/customers', body)
    const created = res?.data
    if (created?.id) {
      await loadCustomers()
      const row = customers.value.find((x) => x.id === created.id)
      if (row) await openCustomer(row)
      showNewCustomer.value = false
      newCustomer.name = ''
      newCustomer.email = ''
      newCustomer.phone = ''
      newCustomer.tax_id = ''
    }
  } catch (e) {
    globalError.value = errMessage(e)
  } finally {
    savingCustomer.value = false
  }
}

async function openCustomer(c) {
  globalError.value = ''
  selectedCustomer.value = c
  records.value = []
  activity.value = []
  showNewRecord.value = false
  chargeRecord.value = null
  loadingRecords.value = true
  loadingActivity.value = true
  try {
    const [recRes, actRes] = await Promise.all([
      api.get(`/api/v1/crm/customers/${c.id}/records`),
      api.get(`/api/v1/crm/customers/${c.id}/activity`),
    ])
    records.value = Array.isArray(recRes?.data) ? recRes.data : []
    activity.value = Array.isArray(actRes?.data) ? actRes.data : []
  } catch (e) {
    globalError.value = errMessage(e)
  } finally {
    loadingRecords.value = false
    loadingActivity.value = false
  }
}

async function loadActivity() {
  if (!selectedCustomer.value) return
  loadingActivity.value = true
  try {
    const actRes = await api.get(`/api/v1/crm/customers/${selectedCustomer.value.id}/activity`)
    activity.value = Array.isArray(actRes?.data) ? actRes.data : []
  } catch (e) {
    globalError.value = errMessage(e)
  } finally {
    loadingActivity.value = false
  }
}

async function createRecord() {
  if (!selectedCustomer.value) return
  savingRecord.value = true
  globalError.value = ''
  try {
    const body = {
      title: newRecord.title.trim(),
      status: newRecord.status,
      amount: newRecord.amount,
      notes: newRecord.notes?.trim() || null,
    }
    await api.post(`/api/v1/crm/customers/${selectedCustomer.value.id}/records`, body)
    newRecord.title = ''
    newRecord.status = 'open'
    newRecord.amount = 0
    newRecord.notes = ''
    showNewRecord.value = false
    const recRes = await api.get(`/api/v1/crm/customers/${selectedCustomer.value.id}/records`)
    records.value = Array.isArray(recRes?.data) ? recRes.data : []
    await loadActivity()
  } catch (e) {
    globalError.value = errMessage(e)
  } finally {
    savingRecord.value = false
  }
}

function openCharge(r) {
  chargeRecord.value = r
  chargeForm.base_amount = r.amount && Number(r.amount) > 0 ? String(r.amount) : '10'
  chargeForm.payment_method = 'efectivo'
  chargeForm.description = r.title
}

async function submitCharge() {
  if (!chargeRecord.value) return
  charging.value = true
  globalError.value = ''
  try {
    const amt = Number(String(chargeForm.base_amount).replace(',', '.'))
    if (!amt || amt <= 0) {
      globalError.value = t('officeCrm.invalidAmount')
      return
    }
    await api.post(`/api/v1/crm/records/${chargeRecord.value.id}/charge`, {
      base_amount: amt,
      payment_method: chargeForm.payment_method,
      description: chargeForm.description || chargeRecord.value.title,
      iva_rate: 21,
      consumption_type: 'onsite',
    })
    chargeRecord.value = null
    const recRes = await api.get(`/api/v1/crm/customers/${selectedCustomer.value.id}/records`)
    records.value = Array.isArray(recRes?.data) ? recRes.data : []
    await loadActivity()
  } catch (e) {
    globalError.value = errMessage(e)
  } finally {
    charging.value = false
  }
}

onMounted(loadCustomers)
</script>

<style scoped>
.office-crm {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.25rem 1rem 2rem;
  color: #e8eaed;
}
.crm-header {
  margin-bottom: 1.25rem;
}
.back-link {
  color: #8ab4f8;
  text-decoration: none;
  font-size: 0.9rem;
}
.back-link:hover {
  text-decoration: underline;
}
h1 {
  margin: 0.5rem 0 0.25rem;
  font-size: 1.5rem;
}
.subtitle {
  margin: 0;
  opacity: 0.8;
  font-size: 0.95rem;
}
.global-error {
  background: rgba(242, 139, 130, 0.15);
  border: 1px solid #f28b82;
  color: #f28b82;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.crm-layout {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  gap: 1rem;
}
@media (max-width: 960px) {
  .crm-layout {
    grid-template-columns: 1fr;
  }
}
.panel {
  background: #1e1f24;
  border: 1px solid #3c4043;
  border-radius: 10px;
  padding: 1rem;
}
.panel h2 {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
}
.panel h3,
.panel h4 {
  margin: 1rem 0 0.5rem;
  font-size: 1rem;
}
.btn-primary,
.btn-secondary,
.btn-small {
  cursor: pointer;
  border-radius: 6px;
  padding: 0.45rem 0.85rem;
  font-size: 0.875rem;
  border: none;
  margin: 0.25rem 0.25rem 0.25rem 0;
}
.btn-primary {
  background: #8ab4f8;
  color: #202124;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-secondary {
  background: #3c4043;
  color: #e8eaed;
}
.btn-small {
  background: #5f6368;
  color: #fff;
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
}
.form-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0.75rem 0;
  padding: 0.75rem;
  background: #292a2e;
  border-radius: 8px;
}
.form-card label {
  font-size: 0.8rem;
  margin-top: 0.35rem;
}
.form-card input,
.form-card select,
.form-card textarea {
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #5f6368;
  background: #202124;
  color: #e8eaed;
}
.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.customer-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  max-height: 420px;
  overflow-y: auto;
}
.customer-list li {
  padding: 0.55rem 0.5rem;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.customer-list li:hover {
  background: #292a2e;
}
.customer-list li.active {
  border-color: #8ab4f8;
  background: rgba(138, 180, 248, 0.12);
}
.cust-name {
  display: block;
  font-weight: 600;
}
.cust-meta {
  font-size: 0.8rem;
  opacity: 0.75;
}
.meta-line {
  font-size: 0.9rem;
  opacity: 0.85;
  margin: 0 0 1rem;
}
.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  margin-top: 0.5rem;
}
.records-table th,
.records-table td {
  text-align: left;
  padding: 0.45rem 0.35rem;
  border-bottom: 1px solid #3c4043;
}
.actions {
  white-space: nowrap;
}
.charge-box {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #292a2e;
  border-radius: 8px;
}
.charge-actions {
  margin-top: 0.5rem;
}
.activity-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  max-height: 480px;
  overflow-y: auto;
}
.activity-item {
  padding: 0.6rem 0;
  border-bottom: 1px solid #3c4043;
}
.activity-time {
  display: block;
  font-size: 0.75rem;
  opacity: 0.7;
}
.activity-action {
  font-weight: 600;
  font-size: 0.85rem;
}
.activity-summary {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  opacity: 0.9;
}
.muted {
  opacity: 0.65;
  font-size: 0.9rem;
}
</style>
