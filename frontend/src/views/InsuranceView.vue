<template>
  <div class="insurance-view">
   <div class="insurance-content">
    <header class="ins-header">
      <router-link to="/dashboard" class="back-link">&larr; Volver al panel</router-link>
      <h1>Seguros</h1>
      <p class="subtitle">Pólizas (Hogar, Comunidad, Coche, Vida, Decesos, Salud) y siniestros de tu empresa.</p>
    </header>

    <p v-if="globalError" class="global-error">{{ globalError }}</p>

    <!-- Listado de pólizas -->
    <section v-if="!selectedPolicy" class="panel">
      <div class="toolbar">
        <h2>Pólizas ({{ policies.length }})</h2>
        <button class="btn-primary" @click="showNewPolicy = !showNewPolicy">
          {{ showNewPolicy ? 'Cancelar' : 'Nueva póliza' }}
        </button>
      </div>

      <form v-if="showNewPolicy" class="inline-form" @submit.prevent="createPolicy">
        <label>
          Cliente *
          <select v-model.number="newPolicy.customer_id" required @change="onCustomerChange">
            <option disabled value="">Selecciona un cliente</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <label>
          DNI/NIF/CIF del cliente *
          <input
            v-model="newPolicy.customer_tax_id"
            type="text"
            placeholder="12345678A"
            required
            :class="{ 'field-invalid': newPolicy.customer_tax_id && !taxIdValid }"
          />
          <span v-if="newPolicy.customer_tax_id && !taxIdValid" class="field-error">DNI/NIF/CIF no válido</span>
        </label>
        <label>
          Ramo *
          <select v-model="newPolicy.branch" required>
            <option disabled value="">Selecciona un ramo</option>
            <option value="hogar">Hogar</option>
            <option value="comunidad">Comunidad</option>
            <option value="coche">Coche</option>
            <option value="vida">Vida</option>
            <option value="decesos">Decesos</option>
            <option value="salud">Salud</option>
          </select>
        </label>
        <label>
          Prima anual (€) *
          <input v-model.number="newPolicy.premium_amount" type="number" step="0.01" min="0.01" required />
        </label>
        <label>
          Fecha de renovación
          <input v-model="newPolicy.renewal_date" type="date" />
        </label>
        <label>
          Estado
          <select v-model="newPolicy.status">
            <option value="draft">Borrador</option>
            <option value="active">Activa</option>
            <option value="cancelled">Cancelada</option>
            <option value="expired">Vencida</option>
          </select>
        </label>

        <fieldset v-if="newPolicy.branch === 'hogar' || newPolicy.branch === 'comunidad'" class="coverages-fieldset">
          <legend>Coberturas</legend>
          <label class="checkbox-label"><input v-model="newPolicy.coverages.hogar" type="checkbox" /> Hogar</label>
          <label class="checkbox-label"><input v-model="newPolicy.coverages.incendio" type="checkbox" /> Incendio</label>
          <label class="checkbox-label"><input v-model="newPolicy.coverages.robo" type="checkbox" /> Robo</label>
          <label>
            Capital responsabilidad civil (€)
            <input v-model.number="newPolicy.coverages.responsabilidad_civil_capital" type="number" step="1" min="0" />
          </label>
        </fieldset>

        <fieldset v-if="newPolicy.branch === 'hogar' || newPolicy.branch === 'comunidad'" class="coverages-fieldset">
          <legend>Bien asegurado</legend>
          <label>
            Dirección
            <input v-model="newPolicy.insured_risk.direccion" type="text" placeholder="Calle, número, ciudad" />
          </label>
          <label>
            m² construidos
            <input v-model.number="newPolicy.insured_risk.m2" type="number" step="1" min="0" />
          </label>
        </fieldset>

        <fieldset v-if="newPolicy.branch === 'coche'" class="coverages-fieldset">
          <legend>Datos del vehículo</legend>
          <label>
            Matrícula *
            <input v-model="newPolicy.insured_risk.matricula" type="text" placeholder="1234ABC" required />
          </label>
          <label>
            Conductor habitual *
            <input v-model="newPolicy.insured_risk.conductor_habitual" type="text" required />
          </label>
          <label>
            Marca / modelo *
            <input v-model="newPolicy.insured_risk.marca_modelo" type="text" placeholder="Seat León" required />
          </label>
        </fieldset>

        <fieldset v-if="newPolicy.branch === 'vida'" class="coverages-fieldset">
          <legend>Datos de la póliza de vida</legend>
          <label>
            Beneficiario *
            <input v-model="newPolicy.insured_risk.beneficiario" type="text" required />
          </label>
          <label>
            Capital asegurado (€) *
            <input v-model.number="newPolicy.insured_risk.capital_asegurado" type="number" step="1" min="0" required />
          </label>
        </fieldset>

        <fieldset v-if="newPolicy.branch === 'salud'" class="coverages-fieldset">
          <legend>Datos de la póliza de salud</legend>
          <label>
            Nº de asegurados *
            <input v-model.number="newPolicy.insured_risk.numero_asegurados" type="number" step="1" min="1" required />
          </label>
          <label class="full-width">
            Cuadro médico *
            <textarea v-model="newPolicy.insured_risk.cuadro_medico" rows="2" placeholder="Centros/médicos incluidos" required></textarea>
          </label>
        </fieldset>

        <label class="full-width">
          Notas
          <textarea v-model="newPolicy.notes" rows="2"></textarea>
        </label>

        <button type="submit" class="btn-small" :disabled="creatingPolicy || !taxIdValid || !newPolicy.branch">
          {{ creatingPolicy ? 'Creando…' : 'Crear póliza' }}
        </button>
      </form>

      <table class="data-table" v-if="policies.length">
        <thead>
          <tr>
            <th>Nº póliza</th>
            <th>Ramo</th>
            <th>Cliente</th>
            <th>Prima</th>
            <th>Estado</th>
            <th>Renovación</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in policies" :key="p.id">
            <td>{{ p.policy_number }}</td>
            <td><span class="tag">{{ branchLabel(p.branch) }}</span></td>
            <td>{{ customerName(p.customer_id) }}</td>
            <td>{{ formatMoney(p.premium_amount) }}</td>
            <td><span class="status-pill" :class="'status-' + p.status">{{ statusLabel(p.status) }}</span></td>
            <td>{{ p.renewal_date || '—' }}</td>
            <td><button class="btn-small" @click="openPolicy(p)">Ver</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Todavía no hay pólizas. Crea la primera con el botón de arriba.</p>
    </section>

    <!-- Detalle de póliza + siniestros -->
    <section v-else class="panel">
      <div class="toolbar">
        <button class="btn-secondary" @click="selectedPolicy = null">&larr; Volver al listado</button>
        <h2>Póliza {{ selectedPolicy.policy_number }}</h2>
      </div>

      <div class="policy-detail">
        <p><strong>Ramo:</strong> <span class="tag">{{ branchLabel(selectedPolicy.branch) }}</span></p>
        <p><strong>Cliente:</strong> {{ customerName(selectedPolicy.customer_id) }}</p>
        <p><strong>Prima:</strong> {{ formatMoney(selectedPolicy.premium_amount) }}</p>
        <p><strong>Estado:</strong> <span class="status-pill" :class="'status-' + selectedPolicy.status">{{ statusLabel(selectedPolicy.status) }}</span></p>
        <p><strong>Inicio:</strong> {{ selectedPolicy.start_date }} <strong>· Renovación:</strong> {{ selectedPolicy.renewal_date || '—' }}</p>
        <p v-if="selectedPolicy.insured_risk?.direccion"><strong>Bien asegurado:</strong> {{ selectedPolicy.insured_risk.direccion }}</p>
        <template v-if="selectedPolicy.branch === 'coche'">
          <p><strong>Matrícula:</strong> {{ selectedPolicy.insured_risk?.matricula || '—' }}
             <strong>· Conductor habitual:</strong> {{ selectedPolicy.insured_risk?.conductor_habitual || '—' }}
             <strong>· Marca/modelo:</strong> {{ selectedPolicy.insured_risk?.marca_modelo || '—' }}</p>
        </template>
        <template v-else-if="selectedPolicy.branch === 'vida'">
          <p><strong>Beneficiario:</strong> {{ selectedPolicy.insured_risk?.beneficiario || '—' }}
             <strong>· Capital asegurado:</strong> {{ selectedPolicy.insured_risk?.capital_asegurado != null ? formatMoney(selectedPolicy.insured_risk.capital_asegurado) : '—' }}</p>
        </template>
        <template v-else-if="selectedPolicy.branch === 'salud'">
          <p><strong>Nº asegurados:</strong> {{ selectedPolicy.insured_risk?.numero_asegurados || '—' }}
             <strong>· Cuadro médico:</strong> {{ selectedPolicy.insured_risk?.cuadro_medico || '—' }}</p>
        </template>
        <p><strong>Coberturas:</strong>
          <span v-if="selectedPolicy.coverages?.hogar" class="tag">Hogar</span>
          <span v-if="selectedPolicy.coverages?.incendio" class="tag">Incendio</span>
          <span v-if="selectedPolicy.coverages?.robo" class="tag">Robo</span>
          <span v-if="selectedPolicy.coverages?.responsabilidad_civil_capital" class="tag">RC {{ selectedPolicy.coverages.responsabilidad_civil_capital }}€</span>
        </p>
      </div>

      <div class="toolbar">
        <h3>Siniestros ({{ claims.length }})</h3>
        <button class="btn-primary" @click="showNewClaim = !showNewClaim">
          {{ showNewClaim ? 'Cancelar' : 'Abrir siniestro' }}
        </button>
      </div>

      <form v-if="showNewClaim" class="inline-form" @submit.prevent="createClaim">
        <label class="full-width">
          Descripción *
          <textarea v-model="newClaim.description" rows="2" required placeholder="Qué ha ocurrido"></textarea>
        </label>
        <label>
          Importe estimado (€)
          <input v-model.number="newClaim.estimated_amount" type="number" step="0.01" min="0" />
        </label>
        <label>
          Adjuntar documento/foto
          <input type="file" @change="onClaimFileSelected" accept="image/*,application/pdf" />
        </label>
        <span v-if="newClaimDocument" class="muted">Adjunto: {{ newClaimDocument.name }}</span>
        <button type="submit" class="btn-small" :disabled="creatingClaim || uploadingFile">
          {{ uploadingFile ? 'Subiendo adjunto…' : (creatingClaim ? 'Abriendo…' : 'Abrir siniestro') }}
        </button>
      </form>

      <table class="data-table" v-if="claims.length">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Descripción</th>
            <th>Estimado</th>
            <th>Resuelto</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in claims" :key="c.id">
            <td>{{ c.claim_date }}</td>
            <td>{{ c.description }}</td>
            <td>{{ c.estimated_amount != null ? formatMoney(c.estimated_amount) : '—' }}</td>
            <td>{{ c.resolved_amount != null ? formatMoney(c.resolved_amount) : '—' }}</td>
            <td><span class="status-pill" :class="'claim-status-' + c.status">{{ claimStatusLabel(c.status) }}</span></td>
            <td class="actions">
              <select v-model="c._nextStatus" class="status-select">
                <option value="open">Abierto</option>
                <option value="investigating">En investigación</option>
                <option value="resolved">Resuelto</option>
                <option value="rejected">Rechazado</option>
              </select>
              <input
                v-if="c._nextStatus === 'resolved'"
                v-model.number="c._resolvedAmount"
                type="number"
                step="0.01"
                min="0"
                placeholder="Importe resuelto"
                class="resolved-input"
              />
              <button class="btn-small" @click="updateClaimStatus(c)">Guardar</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Esta póliza todavía no tiene siniestros.</p>
    </section>
   </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import api from '@/services/api'
import { validarNifCif } from '@/utils/validatorsEs'

type Customer = { id: number; name: string; tax_id?: string | null }

type Policy = {
  id: number
  policy_number: string
  customer_id: number
  branch: string
  premium_amount: number | string
  status: string
  start_date: string
  renewal_date?: string | null
  coverages: Record<string, any>
  insured_risk?: Record<string, any>
  notes?: string | null
}

type ClaimDoc = { name: string; url: string; content_type?: string; size_bytes?: number }

type Claim = {
  id: number
  policy_id: number
  claim_date: string
  description: string
  status: string
  estimated_amount: number | string | null
  resolved_amount: number | string | null
  documents: ClaimDoc[]
  _nextStatus?: string
  _resolvedAmount?: number | null
}

const globalError = ref('')
const policies = ref<Policy[]>([])
const customers = ref<Customer[]>([])
const selectedPolicy = ref<Policy | null>(null)
const claims = ref<Claim[]>([])

const showNewPolicy = ref(false)
const creatingPolicy = ref(false)
const newPolicy = reactive<any>({
  customer_id: '',
  customer_tax_id: '',
  branch: '',
  premium_amount: null,
  renewal_date: '',
  status: 'active',
  notes: '',
  coverages: { hogar: true, incendio: true, robo: false, responsabilidad_civil_capital: null },
  insured_risk: {
    direccion: '', m2: null,
    matricula: '', conductor_habitual: '', marca_modelo: '',
    beneficiario: '', capital_asegurado: null,
    numero_asegurados: null, cuadro_medico: '',
  },
})

const taxIdValid = computed(() => !!newPolicy.customer_tax_id && validarNifCif(newPolicy.customer_tax_id))

function onCustomerChange() {
  const c = customers.value.find((x) => x.id === newPolicy.customer_id)
  newPolicy.customer_tax_id = c?.tax_id || ''
}

const showNewClaim = ref(false)
const creatingClaim = ref(false)
const uploadingFile = ref(false)
const newClaimDocument = ref<ClaimDoc | null>(null)
const newClaim = reactive<any>({ description: '', estimated_amount: null })

function statusLabel(s: string) {
  return { draft: 'Borrador', active: 'Activa', cancelled: 'Cancelada', expired: 'Vencida' }[s] || s
}
function branchLabel(b: string) {
  return { hogar: 'Hogar', comunidad: 'Comunidad', coche: 'Coche', vida: 'Vida', decesos: 'Decesos', salud: 'Salud' }[b] || b
}
function claimStatusLabel(s: string) {
  return { open: 'Abierto', investigating: 'En investigación', resolved: 'Resuelto', rejected: 'Rechazado' }[s] || s
}
function formatMoney(v: number | string) {
  const n = typeof v === 'string' ? parseFloat(v) : v
  return n.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
}
function customerName(id: number) {
  return customers.value.find((c) => c.id === id)?.name || `Cliente #${id}`
}

async function loadCustomers() {
  try {
    const res = await api.get('/api/v1/crm/customers')
    customers.value = Array.isArray(res) ? res : (res?.data || [])
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudieron cargar los clientes'
  }
}

async function loadPolicies() {
  try {
    const res = await api.get('/api/v1/insurance/policies')
    policies.value = res?.data || []
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudieron cargar las pólizas'
  }
}

function buildInsuredRiskPayload(): Record<string, any> {
  const r = newPolicy.insured_risk
  const branch = newPolicy.branch
  const base: Record<string, any> = {
    ...(r.direccion ? { direccion: r.direccion } : {}),
    ...(r.m2 ? { m2: r.m2 } : {}),
  }
  if (branch === 'coche') {
    return { ...base, matricula: r.matricula, conductor_habitual: r.conductor_habitual, marca_modelo: r.marca_modelo }
  }
  if (branch === 'vida') {
    return { ...base, beneficiario: r.beneficiario, capital_asegurado: r.capital_asegurado }
  }
  if (branch === 'salud') {
    return { ...base, numero_asegurados: r.numero_asegurados, cuadro_medico: r.cuadro_medico }
  }
  return base
}

async function createPolicy() {
  globalError.value = ''
  if (!newPolicy.customer_id || !newPolicy.premium_amount || !newPolicy.branch || !taxIdValid.value) return
  creatingPolicy.value = true
  try {
    const payload = {
      customer_id: newPolicy.customer_id,
      customer_tax_id: newPolicy.customer_tax_id,
      branch: newPolicy.branch,
      premium_amount: newPolicy.premium_amount,
      renewal_date: newPolicy.renewal_date || null,
      status: newPolicy.status,
      notes: newPolicy.notes || null,
      coverages: {
        hogar: !!newPolicy.coverages.hogar,
        incendio: !!newPolicy.coverages.incendio,
        robo: !!newPolicy.coverages.robo,
        ...(newPolicy.coverages.responsabilidad_civil_capital
          ? { responsabilidad_civil_capital: newPolicy.coverages.responsabilidad_civil_capital }
          : {}),
      },
      insured_risk: buildInsuredRiskPayload(),
    }
    await api.post('/api/v1/insurance/policies', payload)
    showNewPolicy.value = false
    Object.assign(newPolicy, {
      customer_id: '', customer_tax_id: '', branch: '', premium_amount: null, renewal_date: '', status: 'active', notes: '',
      coverages: { hogar: true, incendio: true, robo: false, responsabilidad_civil_capital: null },
      insured_risk: {
        direccion: '', m2: null,
        matricula: '', conductor_habitual: '', marca_modelo: '',
        beneficiario: '', capital_asegurado: null,
        numero_asegurados: null, cuadro_medico: '',
      },
    })
    await loadPolicies()
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudo crear la póliza'
  } finally {
    creatingPolicy.value = false
  }
}

async function openPolicy(p: Policy) {
  selectedPolicy.value = p
  showNewClaim.value = false
  await loadClaims(p.id)
}

async function loadClaims(policyId: number) {
  try {
    const res = await api.get(`/api/v1/insurance/policies/${policyId}/claims`)
    claims.value = (res?.data || []).map((c: Claim) => ({ ...c, _nextStatus: c.status, _resolvedAmount: c.resolved_amount }))
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudieron cargar los siniestros'
  }
}

async function onClaimFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingFile.value = true
  globalError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.postFormData('/api/v1/upload', formData)
    newClaimDocument.value = {
      name: file.name,
      url: res.url,
      content_type: res.content_type,
      size_bytes: res.size_bytes,
    }
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudo subir el adjunto'
  } finally {
    uploadingFile.value = false
  }
}

async function createClaim() {
  if (!selectedPolicy.value || !newClaim.description) return
  globalError.value = ''
  creatingClaim.value = true
  try {
    await api.post('/api/v1/insurance/claims', {
      policy_id: selectedPolicy.value.id,
      description: newClaim.description,
      estimated_amount: newClaim.estimated_amount || null,
      documents: newClaimDocument.value ? [newClaimDocument.value] : [],
    })
    showNewClaim.value = false
    newClaim.description = ''
    newClaim.estimated_amount = null
    newClaimDocument.value = null
    await loadClaims(selectedPolicy.value.id)
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudo abrir el siniestro'
  } finally {
    creatingClaim.value = false
  }
}

async function updateClaimStatus(c: Claim) {
  globalError.value = ''
  try {
    const payload: any = { status: c._nextStatus }
    if (c._nextStatus === 'resolved' && c._resolvedAmount != null) {
      payload.resolved_amount = c._resolvedAmount
    }
    await api.patch(`/api/v1/insurance/claims/${c.id}`, payload)
    if (selectedPolicy.value) await loadClaims(selectedPolicy.value.id)
  } catch (e: any) {
    globalError.value = e?.detail || e?.message || 'No se pudo actualizar el siniestro'
  }
}

onMounted(async () => {
  await Promise.all([loadCustomers(), loadPolicies()])
})
</script>

<style scoped>
/* Sistema de diseño Ronda 2 (ver zeus-light-system.css): bandas metálicas
   obligatorias en toda la vista, un único botón con acento gradiente por
   pantalla (Nueva póliza / Abrir siniestro — el resto queda en
   .btn-secondary blanco/borde, incluidas las acciones repetidas por fila
   como "Ver"/"Guardar"). */
/* El fondo de bandas metalicas (var(--zeus-bg)) va en el contenedor a
   ANCHO COMPLETO. Dos causas del mismo sintoma ("franja oscura en los
   bordes"), corregidas ambas aqui:
   1) Este contenedor tenia su propio max-width/margin:0 auto (ya
      corregido moviendolo a .insurance-content, el wrapper interior).
   2) #app (global, src/style.css) tiene max-width:1280px + margin:0
      auto sobre un body con fondo OSCURO (#0b0f19, src/assets/styles/
      index.css) -- en cualquier viewport mas ancho que 1280px, ese
      fondo oscuro asoma FUERA de #app, con independencia de lo que
      haga este componente por dentro. TPV.vue y AdminPanel.vue lo
      evitan con position:fixed + width:100vw (escapan del todo del
      flujo/caja de #app); aqui, al ser una pagina de scroll normal (no
      un "app" de pantalla completa), se usa el truco de "breakout"
      estandar (100vw + left:50%/margin-left:-50vw) para que el fondo
      rompa el max-width del padre sin salir del flujo del documento. */
.insurance-view {
  position: relative;
  left: 50%;
  right: 50%;
  width: 100vw;
  margin-left: -50vw;
  margin-right: -50vw;
  overflow: hidden;
  min-height: 100vh;
  font-family: var(--zeus-font-sans, system-ui, -apple-system, sans-serif);
  color: var(--zeus-text, #0f172a);
  background-image: var(--zeus-bg);
  box-sizing: border-box;
}
.insurance-view::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}
.insurance-content {
  position: relative;
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
.insurance-content > * { position: relative; }
.ins-header { margin-bottom: 20px; }
.back-link { color: var(--zeus-accent, #4f46e5); text-decoration: none; font-size: 14px; font-weight: 500; }
.back-link:hover { text-decoration: underline; }
.ins-header h1 { margin: 8px 0 4px; font-size: var(--zeus-text-xl, 24px); color: var(--zeus-text, #0f172a); }
.subtitle { color: var(--zeus-text-secondary, #52607a); margin: 0; }
.global-error {
  background: var(--zeus-danger-soft, #fdecea);
  color: #b71c1c;
  padding: 10px 14px;
  border-radius: var(--zeus-radius-sm, 4px);
  margin-bottom: 16px;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.panel {
  background: var(--zeus-surface, #fff);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius, 12px);
  box-shadow: var(--zeus-shadow, 0 1px 3px rgba(15, 23, 42, 0.06));
  padding: 16px;
  margin-bottom: 20px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.toolbar h2, .toolbar h3 { margin: 0; flex: 1; color: var(--zeus-text, #0f172a); }

/* Único botón vibrante de la vista: alterna la pantalla de creación
   (Nueva póliza / Abrir siniestro). */
.btn-primary {
  cursor: pointer;
  border: none;
  background: var(--zeus-accent-gradient, linear-gradient(135deg, #14b8a6 0%, #8b5cf6 50%, #ec4899 100%));
  color: #ffffff;
  padding: 10px 18px;
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--zeus-accent-gradient-shadow, 0 2px 8px rgba(0, 0, 0, 0.15));
  transition: box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.btn-primary:hover { box-shadow: var(--zeus-accent-gradient-shadow-hover, 0 4px 14px rgba(0, 0, 0, 0.22)); transform: translateY(-1px); }
.btn-primary:active { transform: translateY(0) scale(0.97); }

/* Todos los demás botones: secundario blanco/borde, sin gradiente. */
.btn-secondary, .btn-small {
  cursor: pointer;
  border: 1px solid #D1D5DB;
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  padding: 8px 14px;
  border-radius: var(--zeus-radius-sm, 8px);
  font-size: 14px;
  box-shadow: none;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}
.btn-secondary:hover, .btn-small:hover { border-color: #9aa2af; }
.btn-small { padding: 5px 10px; font-size: 13px; }
.data-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.data-table th, .data-table td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--zeus-border, #eee);
  font-size: 14px;
  color: var(--zeus-text, #0f172a);
}
.data-table th { color: var(--zeus-text-secondary, #52607a); font-weight: 600; }
.status-pill {
  padding: 2px 8px;
  border-radius: var(--zeus-radius-full, 10px);
  font-size: 12px;
  background: var(--zeus-bg-flat, #eee);
}
.status-active, .claim-status-resolved { background: var(--zeus-success-soft, #d4edda); color: #155724; }
.status-draft, .claim-status-open { background: var(--zeus-warning-soft, #fff3cd); color: #856404; }
.status-cancelled, .claim-status-rejected { background: var(--zeus-danger-soft, #f8d7da); color: #721c24; }
.status-expired { background: #e2e3e5; color: #383d41; }
.claim-status-investigating { background: var(--zeus-info-soft, #d1ecf1); color: #0c5460; }
.tag {
  display: inline-block;
  background: var(--zeus-accent-soft, #eef1ff);
  color: var(--zeus-accent, #4f46e5);
  padding: 2px 8px;
  border-radius: var(--zeus-radius-full, 10px);
  font-size: 12px;
  margin-right: 4px;
}
.inline-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  background: var(--zeus-bg-subtle, #fafafa);
  border: 1px solid var(--zeus-border, #eee);
  border-radius: var(--zeus-radius-sm, 8px);
  margin-bottom: 12px;
  align-items: flex-end;
}
.inline-form label {
  display: flex;
  flex-direction: column;
  font-size: 13px;
  gap: 4px;
  color: var(--zeus-text-secondary, #52607a);
}
.inline-form input, .inline-form select, .inline-form textarea {
  padding: 6px 8px;
  border: 1px solid var(--zeus-border-strong, #ccc);
  border-radius: var(--zeus-radius-sm, 4px);
  font-size: 14px;
  color: var(--zeus-text, #0f172a);
  background: #ffffff;
  font-family: inherit;
}
.full-width { width: 100%; }
.coverages-fieldset {
  border: 1px solid var(--zeus-border, #ddd);
  border-radius: var(--zeus-radius-sm, 4px);
  padding: 8px 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.checkbox-label { flex-direction: row !important; align-items: center; gap: 6px !important; }
.muted { color: var(--zeus-text-muted, #8792a6); font-size: 14px; }
.field-invalid { border-color: #b71c1c !important; }
.field-error { color: #b71c1c; font-size: 12px; }
.policy-detail p { margin: 4px 0; }
.actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.status-select { padding: 4px 6px; font-size: 13px; border: 1px solid var(--zeus-border-strong, #ccc); border-radius: var(--zeus-radius-sm, 4px); }
.resolved-input { width: 110px; padding: 4px 6px; font-size: 13px; border: 1px solid var(--zeus-border-strong, #ccc); border-radius: var(--zeus-radius-sm, 4px); }
</style>
