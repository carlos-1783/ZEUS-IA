<template>
  <div class="office-crm">
    <header class="crm-header">
      <router-link to="/dashboard" class="back-link">← {{ t('officeCrm.backToDashboard') }}</router-link>
      <h1>{{ t('officeCrm.title') }}</h1>
      <p class="subtitle">{{ t('officeCrm.subtitle') }}</p>
    </header>

    <p v-if="accessDenied" class="access-denied" role="alert">{{ accessDeniedMessage }}</p>
    <p v-else-if="globalError" class="global-error" role="alert">
      {{ globalError }}
      <router-link v-if="sessionExpired" :to="{ name: 'AuthLogin', query: { redirect: '/office-crm' } }" class="error-login-link">
        {{ t('officeCrm.loginAgain') }}
      </router-link>
    </p>

    <div v-if="!accessDenied" class="crm-layout">
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
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
import { isModuleVisible } from '@/utils/companyModules'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const globalError = ref('')
const sessionExpired = ref(false)
const accessDenied = ref(false)
const accessDeniedMessage = computed(() => t('officeCrm.accessDenied'))
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

async function errMessage(e) {
  if (e?.status === 401) {
    sessionExpired.value = true
    return t('officeCrm.sessionExpired')
  }
  if (e?.status === 403) {
    return t('officeCrm.accessDenied')
  }
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

async function loadCustomers() {
  globalError.value = ''
  loadingCustomers.value = true
  try {
    const res = await api.get('/api/v1/crm/customers')
    customers.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    globalError.value = await errMessage(e)
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
    const res = await api.post('/api/v1/crm/customers', body)
    const created = res?.id != null ? res : res?.data
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
    globalError.value = await errMessage(e)
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
    globalError.value = await errMessage(e)
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
    globalError.value = await errMessage(e)
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
    globalError.value = await errMessage(e)
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
    globalError.value = await errMessage(e)
  } finally {
    charging.value = false
  }
}

async function bootstrapPage() {
  sessionExpired.value = false
  accessDenied.value = false
  globalError.value = ''

  await authStore.initialize()
  if (!authStore.getToken?.() && !authStore.token) {
    router.push({ name: 'AuthLogin', query: { redirect: '/office-crm' } })
    return
  }

  const canCrm = isModuleVisible(authStore.modules, 'crm', {
    isSuperuser: authStore.isAdmin,
    isEmployee: authStore.isEmployee,
  })
  if (!canCrm) {
    accessDenied.value = true
    loadingCustomers.value = false
    return
  }

  await loadCustomers()
}

onMounted(bootstrapPage)
</script>

<style scoped>
.error-login-link {
  display: inline-block;
  margin-left: 0.5rem;
  color: #2563eb;
  font-weight: 600;
}
</style>
