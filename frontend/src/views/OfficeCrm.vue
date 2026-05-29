<template>
  <div class="office-crm">
    <header class="crm-header">
      <router-link to="/dashboard" class="back-link">← {{ t('officeCrm.backToDashboard') }}</router-link>
      <h1>{{ t('officeCrm.title') }}</h1>
      <p class="subtitle">{{ t('officeCrm.subtitle') }}</p>
    </header>
    <p v-if="globalError" class="global-error">{{ globalError }}</p>

    <section class="panel">
      <div class="toolbar">
        <h2>Clientes</h2>
        <input v-model="clientSearch" placeholder="Buscar cliente..." />
        <button class="btn-secondary" @click="downloadCsv('/api/v1/crm/export/clients', 'clients.csv')">CSV</button>
        <button class="btn-secondary" @click="downloadExcel('clients')">Excel</button>
        <button class="btn-secondary" @click="showImport = true">Importar</button>
        <button class="btn-primary" @click="showNewClient = !showNewClient">Nuevo cliente</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th @click="sortClientsBy('name')">Nombre</th>
            <th>Email</th>
            <th>Teléfono</th>
            <th @click="sortClientsBy('status')">Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in filteredClients" :key="c.id">
            <td><input v-model="c.name" /></td>
            <td><input v-model="c.email" /></td>
            <td><input v-model="c.phone" /></td>
            <td>
              <select v-model="c.status">
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </td>
            <td class="actions">
              <button class="btn-small" @click="saveClient(c)">Guardar</button>
              <button class="btn-small" @click="openCustomer(c)">Ver</button>
            </td>
          </tr>
        </tbody>
      </table>
      <form v-if="showNewClient" class="inline-form" @submit.prevent="createClient">
        <input v-model="newClient.name" placeholder="Nombre *" required />
        <input v-model="newClient.email" type="email" placeholder="Email *" required />
        <input v-model="newClient.phone" placeholder="Teléfono" />
        <button type="submit" class="btn-small">Crear cliente</button>
      </form>
    </section>

    <section class="panel" v-if="selectedCustomer">
      <div class="toolbar">
        <h2>Expedientes · {{ selectedCustomer.name }}</h2>
        <input v-model="caseSearch" placeholder="Buscar expediente..." />
        <button class="btn-secondary" @click="downloadCsv('/api/v1/crm/export/cases', 'cases.csv')">CSV</button>
        <button class="btn-secondary" @click="downloadExcel('cases')">Excel</button>
        <button class="btn-primary" @click="showNewCase = !showNewCase">Nuevo expediente</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Título</th>
            <th>Status</th>
            <th>Monto</th>
            <th>Pagado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filteredCases" :key="r.id">
            <td><input v-model="r.title" /></td>
            <td>
              <select v-model="r.status">
                <option value="open">open</option>
                <option value="in_progress">in_progress</option>
                <option value="paid">paid</option>
                <option value="closed">closed</option>
              </select>
            </td>
            <td><input v-model.number="r.amount" type="number" step="0.01" /></td>
            <td>{{ r.paid ? 'Sí' : 'No' }}</td>
            <td class="actions">
              <button class="btn-small" @click="saveCase(r)">Guardar</button>
              <button class="btn-small" @click="openCharge(r)">Cobrar</button>
            </td>
          </tr>
        </tbody>
      </table>
      <form v-if="showNewCase" class="inline-form" @submit.prevent="createCase">
        <input v-model="newCase.title" placeholder="Título expediente *" required />
        <input v-model.number="newCase.amount" type="number" step="0.01" min="0" placeholder="Importe" />
        <button type="submit" class="btn-small">Crear</button>
      </form>
    </section>

    <section class="panel" v-if="selectedCustomer">
      <div class="toolbar">
        <h2>Cobros</h2>
        <input v-model="paymentSearch" placeholder="Buscar cobro..." />
        <button class="btn-secondary" @click="downloadCsv('/api/v1/crm/export/payments', 'payments.csv')">CSV</button>
        <button class="btn-secondary" @click="downloadExcel('payments')">Excel</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Expediente</th>
            <th>Monto</th>
            <th>Método</th>
            <th>Estado</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in filteredPayments" :key="p.id">
            <td>{{ p.case_title || '—' }}</td>
            <td>{{ formatMoney(p.amount) }}</td>
            <td>{{ p.method_human || p.method }}</td>
            <td>{{ p.status_human || p.status }}</td>
            <td>{{ formatDt(p.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel" v-if="selectedCustomer">
      <div class="toolbar">
        <h2>Actividad reciente</h2>
        <button class="btn-secondary" @click="loadActivity">Actualizar</button>
      </div>
      <ul class="activity-list">
        <li v-for="a in activity" :key="a.id" class="activity-item">
          <time>{{ formatDt(a.created_at) }}</time>
          <strong>{{ a.action_human || a.action }}</strong>
          <p v-if="a.summary">{{ a.summary }}</p>
        </li>
      </ul>
      <p v-if="!activity.length" class="muted">Sin actividad registrada.</p>
    </section>

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

    <CrmCustomerImport v-if="showImport" @close="showImport = false" @imported="loadAll" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
import { isModuleVisible } from '@/utils/companyModules'
import CrmCustomerImport from '@/components/CrmCustomerImport.vue'

type SortDir = 'asc' | 'desc'

type CrmCustomer = {
  id: number
  name: string
  email?: string | null
  phone?: string | null
  is_active?: boolean
  status: 'active' | 'inactive'
}

type CrmCase = {
  id: number
  customer_id: number
  title: string
  status: 'open' | 'in_progress' | 'paid' | 'closed' | string
  amount: number
  paid?: boolean
}

type CrmPayment = {
  id: number
  case_id: number
  case_title?: string
  amount: number
  method: string
  method_human?: string
  status: string
  status_human?: string
  created_at?: string | null
}

type CrmActivity = {
  id: number
  action: string
  action_human?: string
  summary?: string
  created_at?: string
}

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const globalError = ref('')
const sessionExpired = ref(false)
const accessDenied = ref(false)
const customers = ref<CrmCustomer[]>([])
const selectedCustomer = ref<CrmCustomer | null>(null)
const records = ref<CrmCase[]>([])
const payments = ref<CrmPayment[]>([])
const activity = ref<CrmActivity[]>([])
const showImport = ref(false)
const showNewClient = ref(false)
const showNewCase = ref(false)
const newClient = reactive({ name: '', email: '', phone: '' })
const newCase = reactive({ title: '', amount: 0 })
const clientSearch = ref('')
const caseSearch = ref('')
const paymentSearch = ref('')
const clientSort = reactive<{ key: keyof CrmCustomer; dir: SortDir }>({ key: 'name', dir: 'asc' })
const charging = ref(false)
const chargeRecord = ref<CrmCase | null>(null)

const chargeForm = reactive({
  base_amount: '',
  payment_method: 'efectivo',
  description: '',
})

function formatMoney(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { style: 'currency', currency: 'EUR' })
}

function formatDt(iso: unknown): string {
  if (!iso) return '—'
  try {
    const value =
      typeof iso === 'string' || typeof iso === 'number' || iso instanceof Date ? iso : String(iso)
    return new Date(value).toLocaleString()
  } catch {
    return String(iso)
  }
}

async function errMessage(e: any): Promise<string> {
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
  try {
    const res = await api.get('/api/v1/crm/customers')
    customers.value = (Array.isArray(res?.data) ? res.data : []).map((c: Partial<CrmCustomer> & { id: number; name: string }) => ({
      ...c,
      status: c?.is_active === false ? 'inactive' : 'active',
    })) as CrmCustomer[]
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function createClient() {
  if (!newClient.name.trim() || !newClient.email.trim()) {
    globalError.value = 'Nombre y email son obligatorios.'
    return
  }
  try {
    await api.post('/api/v1/crm/customers', {
      name: newClient.name.trim(),
      email: newClient.email.trim(),
      phone: newClient.phone?.trim() || null,
      is_active: true,
      is_company: true,
      contacts: [],
    })
    newClient.name = ''
    newClient.email = ''
    newClient.phone = ''
    showNewClient.value = false
    await loadCustomers()
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function saveClient(client: CrmCustomer) {
  if (!client.email?.trim()) {
    globalError.value = 'El email del cliente es obligatorio.'
    return
  }
  try {
    await api.patch(`/api/v1/crm/customers/${client.id}`, {
      name: client.name,
      email: client.email || null,
      phone: client.phone || null,
      is_active: client.status !== 'inactive',
    })
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function loadActivity() {
  if (!selectedCustomer.value) return
  try {
    const actRes = await api.get(`/api/v1/crm/customers/${selectedCustomer.value.id}/activity`)
    activity.value = Array.isArray(actRes?.data) ? actRes.data : []
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function openCustomer(c: CrmCustomer) {
  selectedCustomer.value = c
  try {
    const [recRes, payRes] = await Promise.all([
      api.get(`/api/v1/crm/customers/${c.id}/records`),
      api.get('/api/v1/crm/table/payments'),
    ])
    records.value = (Array.isArray(recRes?.data) ? recRes.data : []).map((r: CrmCase) => ({
      ...r,
      paid: r.status === 'paid',
    }))
    payments.value = ((Array.isArray(payRes?.data) ? payRes.data : []) as CrmPayment[]).filter((p) =>
      records.value.some((r) => r.id === p.case_id),
    )
    await loadActivity()
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function createCase() {
  if (!selectedCustomer.value || !newCase.title.trim()) return
  try {
    await api.post(`/api/v1/crm/customers/${selectedCustomer.value.id}/records`, {
      title: newCase.title.trim(),
      status: 'open',
      amount: Number(newCase.amount || 0),
    })
    newCase.title = ''
    newCase.amount = 0
    showNewCase.value = false
    await openCustomer(selectedCustomer.value)
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function saveCase(row: CrmCase) {
  try {
    await api.patch(`/api/v1/crm/records/${row.id}`, {
      title: row.title,
      status: row.status,
      amount: Number(row.amount || 0),
    })
    row.paid = row.status === 'paid'
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

function sortClientsBy(key: keyof CrmCustomer) {
  if (clientSort.key === key) {
    clientSort.dir = clientSort.dir === 'asc' ? 'desc' : 'asc'
  } else {
    clientSort.key = key
    clientSort.dir = 'asc'
  }
}

const filteredClients = computed(() => {
  const term = clientSearch.value.trim().toLowerCase()
  return [...customers.value]
    .filter((c) => !term || [c.name, c.email, c.phone].some((v) => String(v || '').toLowerCase().includes(term)))
    .sort((a, b) => {
      const av = String(a?.[clientSort.key] || '').toLowerCase()
      const bv = String(b?.[clientSort.key] || '').toLowerCase()
      return clientSort.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    })
})

const filteredCases = computed(() => {
  const term = caseSearch.value.trim().toLowerCase()
  return records.value.filter((r) =>
    !term || [r.title, r.status, String(r.amount || '')].some((v) => String(v).toLowerCase().includes(term)),
  )
})

const filteredPayments = computed(() => {
  const term = paymentSearch.value.trim().toLowerCase()
  return payments.value.filter((p) =>
    !term || [p.method, p.status, String(p.amount || ''), String(p.case_id || '')].some((v) => String(v).toLowerCase().includes(term)),
  )
})

async function downloadExcel(entity: string) {
  try {
    const blob = await api.getBlob(`/api/v1/office/export/${entity}/excel`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${entity}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

async function downloadCsv(endpoint: string, filename: string) {
  try {
    const blob = await api.getBlob(endpoint)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    globalError.value = await errMessage(e)
  }
}

function openCharge(r: CrmCase) {
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
    if (selectedCustomer.value) {
      await openCustomer(selectedCustomer.value)
    }
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
    globalError.value = t('officeCrm.accessDenied')
    return
  }

  await loadAll()
}

async function loadAll() {
  await loadCustomers()
  if (selectedCustomer.value) {
    const selected = customers.value.find((x) => x.id === selectedCustomer.value!.id)
    if (selected) {
      await openCustomer(selected)
    }
  }
}

onMounted(bootstrapPage)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th,
.data-table td {
  border: 1px solid #e2e8f0;
  padding: 8px;
}
.data-table th {
  cursor: pointer;
  background: #f8fafc;
}
.data-table input,
.data-table select {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 6px;
}
.actions {
  display: flex;
  gap: 6px;
}
.btn-small {
  border: none;
  background: #1d4ed8;
  color: #fff;
  border-radius: 6px;
  padding: 6px 8px;
}
.global-error {
  margin: 12px 0;
  color: #b91c1c;
}
.error-login-link {
  display: inline-block;
  margin-left: 0.5rem;
  color: #2563eb;
  font-weight: 600;
}
.inline-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.inline-form input {
  flex: 1;
  min-width: 140px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px;
}
.activity-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.activity-item {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px 0;
}
.activity-item time {
  display: block;
  font-size: 12px;
  color: #64748b;
}
.muted {
  color: #64748b;
  font-size: 14px;
}
.btn-primary {
  border: none;
  background: #1d4ed8;
  color: #fff;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}
.btn-secondary {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
