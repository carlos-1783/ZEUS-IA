<template>
  <div class="setup-wrap">
    <div class="setup-card">
      <h1>Configuración inicial ZEUS</h1>
      <p class="subtitle">
        Completa estos datos una vez para activar automatizaciones de PERSEO, Control Horario y operación diaria.
      </p>

      <div class="stepper">
        <span :class="{ active: step === 1 }">1. Operación</span>
        <span :class="{ active: step === 2 }">2. Canales</span>
        <span :class="{ active: step === 3 }">3. Validación</span>
      </div>

      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="success" class="success">{{ success }}</div>

      <section v-if="step === 1" class="section">
        <label>Empleados</label>
        <input v-model.number="form.employees_count" type="number" min="0" max="100000" />

        <div v-if="form.employees_count > 0" class="employees-grid">
          <label v-for="(emp, idx) in form.employees" :key="`emp-${idx}`">
            Empleado {{ idx + 1 }} - Nombre
            <input v-model.trim="emp.full_name" type="text" placeholder="Nombre y apellidos" />
            <select v-model="emp.role_title">
              <option v-for="role in employeeRoles" :key="`role-${idx}-${role}`" :value="role">{{ role }}</option>
            </select>
            <input v-model.trim="emp.phone" type="text" placeholder="+34600111222" />
          </label>
        </div>

        <label class="check">
          <input v-model="form.uses_tpv" type="checkbox" />
          Usamos TPV en el local
        </label>

        <label>Horario del negocio</label>
        <textarea
          v-model="form.business_hours"
          placeholder="Ej: L-V 08:00-22:00, S-D 10:00-00:00"
          rows="3"
        />
      </section>

      <section v-if="step === 2" class="section">
        <label>Canales sociales activos</label>
        <div class="channels">
          <label v-for="c in availableChannels" :key="c" class="check">
            <input v-model="form.social_channels" type="checkbox" :value="c" />
            {{ c }}
          </label>
        </div>
        <div v-if="form.social_channels.length" class="social-links">
          <label v-for="c in form.social_channels" :key="`link-${c}`">
            URL de {{ c }}
            <input
              v-model.trim="form.social_links[c]"
              type="text"
              :placeholder="`https://.../${c}`"
            />
          </label>
        </div>

        <label>WhatsApp del negocio</label>
        <input v-model.trim="form.whatsapp_number" type="text" placeholder="+34600111222" />

        <label>Email del gestor fiscal (RAFAEL) *</label>
        <input
          v-model.trim="form.email_gestor_fiscal"
          type="email"
          placeholder="gestor@asesoria.com"
          autocomplete="email"
        >
        <p class="hint">
          RAFAEL enviará facturación y documentos fiscales a este correo (vía Gmail del servidor) tras tu aprobación.
        </p>
        <label class="check">
          <input v-model="form.autoriza_envio_documentos_a_asesores" type="checkbox">
          Autorizo el envío de borradores fiscales a mi gestor
        </label>

        <label>Política control horario (opcional)</label>
        <textarea
          v-model="form.control_horario_policy"
          placeholder="Ej: fichaje en local y remoto con geolocalización para comerciales"
          rows="3"
        />

        <h3 class="section-title">Datos de facturación</h3>

        <label>Nombre completo / razón social *</label>
        <input
          v-model.trim="form.legal_name"
          type="text"
          placeholder="Ej: Restauración Zeus S.L."
        >

        <label>CIF/NIF de la empresa *</label>
        <input
          v-model.trim="form.tax_id"
          type="text"
          placeholder="Ej: B12345674 o 12345678Z"
          @blur="form.tax_id = form.tax_id.toUpperCase()"
        >
        <p v-if="form.tax_id && !taxIdValid" class="field-error">
          CIF/NIF con formato inválido (revisa dígitos y letra de control).
        </p>

        <label>Cuenta bancaria (IBAN) para cobros *</label>
        <input
          v-model.trim="form.iban"
          type="text"
          placeholder="Ej: ES91 2100 0418 4502 0005 1332"
          @blur="form.iban = form.iban.toUpperCase()"
        >
        <p v-if="form.iban && !ibanValid" class="field-error">
          IBAN con formato inválido (revisa el dígito de control).
        </p>
        <p v-if="existingIbanMasked" class="hint">
          IBAN ya guardado: {{ existingIbanMasked }}. Déjalo en blanco para mantenerlo, o introduce uno nuevo para sustituirlo.
        </p>
      </section>

      <section v-if="step === 3" class="section">
        <ul>
          <li><strong>Empleados:</strong> {{ form.employees_count }}</li>
          <li><strong>Plantilla inicial:</strong> {{ employeeSummary || '—' }}</li>
          <li><strong>TPV:</strong> {{ form.uses_tpv ? 'Sí' : 'No' }}</li>
          <li><strong>Horario:</strong> {{ form.business_hours || '—' }}</li>
          <li><strong>Redes:</strong> {{ form.social_channels.join(', ') || '—' }}</li>
          <li><strong>Enlaces redes:</strong> {{ socialLinksSummary || '—' }}</li>
          <li><strong>WhatsApp:</strong> {{ form.whatsapp_number || '—' }}</li>
          <li><strong>Gestor fiscal:</strong> {{ form.email_gestor_fiscal || '—' }}</li>
          <li><strong>Razón social:</strong> {{ form.legal_name || '—' }}</li>
          <li><strong>CIF/NIF:</strong> {{ form.tax_id || '—' }}</li>
          <li><strong>IBAN:</strong> {{ form.iban ? maskIban(form.iban) : (existingIbanMasked || '—') }}</li>
        </ul>
      </section>

      <div class="actions">
        <button v-if="step > 1" type="button" class="ghost" @click="step -= 1">Atrás</button>
        <button v-if="step < 3" type="button" @click="nextStep">Siguiente</button>
        <button v-else type="button" :disabled="saving" @click="finishSetup">
          {{ saving ? 'Guardando...' : 'Finalizar configuración' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { markOnboardingSetupDone } from '@/utils/postAuthRedirect'
import { validarNifCif, validarIban, maskIban } from '@/utils/validatorsEs'

const router = useRouter()
const authStore = useAuthStore()
const step = ref(1)
const saving = ref(false)
const error = ref('')
const success = ref('')
type EmployeeRow = { full_name: string; phone: string; role_title: string }
const employeeRoles = ['camarero', 'cocina', 'encargado', 'caja', 'limpieza', 'reparto', 'administración']

const availableChannels = ['instagram', 'facebook', 'tiktok', 'google', 'youtube', 'linkedin']
const form = reactive({
  employees_count: 1,
  uses_tpv: true,
  business_hours: '',
  social_channels: [] as string[],
  social_links: {
    instagram: '',
    facebook: '',
    tiktok: '',
    google: '',
    youtube: '',
    linkedin: '',
  } as Record<string, string>,
  whatsapp_number: '',
  email_gestor_fiscal: '',
  autoriza_envio_documentos_a_asesores: true,
  control_horario_policy: '',
  employees: [{ full_name: '', phone: '', role_title: 'camarero' }] as EmployeeRow[],
  tax_id: '',
  legal_name: '',
  iban: '',
})

const existingIbanMasked = ref('')

const taxIdValid = computed(() => !!form.tax_id && validarNifCif(form.tax_id))
const ibanValid = computed(() => !!form.iban && validarIban(form.iban))

const socialLinksSummary = computed(() => {
  const entries = form.social_channels
    .map((c) => `${c}: ${String(form.social_links[c] || '').trim()}`)
    .filter((row) => !row.endsWith(': '))
  return entries.join(' · ')
})

const employeeSummary = computed(() =>
  form.employees
    .map((e) => {
      const name = String(e.full_name || '').trim()
      const role = String(e.role_title || '').trim()
      const phone = String(e.phone || '').trim()
      return `${name}${role ? ` - ${role}` : ''}${phone ? ` (${phone})` : ''}`
    })
    .filter((x) => !!x)
    .join(' · ')
)

watch(
  () => form.employees_count,
  (countRaw) => {
    const count = Math.max(0, Number(countRaw) || 0)
    if (count === 0) {
      form.employees = []
      return
    }
    while (form.employees.length < count) {
      form.employees.push({ full_name: '', phone: '', role_title: 'camarero' })
    }
    if (form.employees.length > count) {
      form.employees = form.employees.slice(0, count)
    }
  },
  { immediate: true }
)

onMounted(async () => {
  try {
    if (authStore.initialize) {
      await authStore.initialize()
    }
  } catch (_) {}
  const token = authStore.getToken ? authStore.getToken() : (authStore as any).token
  if (!token) {
    window.location.href = '/auth/login?redirect=/onboarding-setup'
    return
  }
  try {
    const status = await api.get('/api/v1/auth/onboarding/status', token)
    if (status?.setup_completed) {
      markOnboardingSetupDone()
      router.replace('/dashboard')
      return
    }
    if (status?.email_gestor_fiscal) {
      form.email_gestor_fiscal = String(status.email_gestor_fiscal)
    }
    if (status?.autoriza_envio_documentos_a_asesores != null) {
      form.autoriza_envio_documentos_a_asesores = !!status.autoriza_envio_documentos_a_asesores
    }
    if (typeof status?.tax_id === 'string' && status.tax_id.trim()) {
      form.tax_id = status.tax_id.trim()
    }
    if (typeof status?.legal_name === 'string' && status.legal_name.trim()) {
      form.legal_name = status.legal_name.trim()
    }
    if (typeof status?.iban_masked === 'string' && status.iban_masked.trim()) {
      existingIbanMasked.value = status.iban_masked.trim()
    }
    const q = status?.existing_questionnaire
    if (q && typeof q === 'object') {
      if (q.employees_count != null) form.employees_count = Number(q.employees_count) || 0
      if (q.uses_tpv != null) form.uses_tpv = !!q.uses_tpv
      if (typeof q.business_hours === 'string' && q.business_hours.trim()) {
        form.business_hours = q.business_hours.trim()
      }
    }
    const op = status?.existing_operational_profile
    if (op && typeof op === 'object') {
      if (typeof op.whatsapp_number === 'string' && op.whatsapp_number.trim()) {
        form.whatsapp_number = op.whatsapp_number.trim()
      }
      if (typeof op.control_horario_policy === 'string' && op.control_horario_policy.trim()) {
        form.control_horario_policy = op.control_horario_policy.trim()
      }
      const links = op.social_links
      if (links && typeof links === 'object') {
        const channels = Object.keys(links).filter((k) => String(links[k] || '').trim())
        if (channels.length) {
          form.social_channels = channels
          for (const ch of channels) {
            form.social_links[ch] = String(links[ch] || '').trim()
          }
        }
      }
    }
  } catch {
    /* ignore */
  }
})

const nextStep = (): void => {
  error.value = ''
  if (step.value === 1) {
    if (form.employees_count < 0) {
      error.value = 'Empleados inválido'
      return
    }
    if (!String(form.business_hours || '').trim()) {
      error.value = 'Indica el horario del negocio'
      return
    }
    if (form.employees_count > 0) {
      for (let i = 0; i < form.employees.length; i += 1) {
        const e = form.employees[i]
        if (!String(e.full_name || '').trim()) {
          error.value = `Falta el nombre del empleado ${i + 1}`
          return
        }
        if (!String(e.phone || '').trim()) {
          error.value = `Falta el teléfono del empleado ${i + 1}`
          return
        }
        if (!String(e.role_title || '').trim()) {
          error.value = `Falta el rol del empleado ${i + 1}`
          return
        }
      }
    }
  }
  if (step.value === 2) {
    if (form.social_channels.length) {
      for (const c of form.social_channels) {
        const url = String(form.social_links[c] || '').trim()
        if (!url) {
          error.value = `Falta la URL de ${c}`
          return
        }
      }
    }
    if (!String(form.email_gestor_fiscal || '').trim() || !/\S+@\S+\.\S+/.test(form.email_gestor_fiscal)) {
      error.value = 'Indica el email del gestor fiscal'
      return
    }
    if (!form.autoriza_envio_documentos_a_asesores) {
      error.value = 'Debes autorizar el envío al gestor para activar RAFAEL'
      return
    }
    if (!String(form.legal_name || '').trim()) {
      error.value = 'Indica el nombre completo / razón social de la empresa'
      return
    }
    if (!String(form.tax_id || '').trim() || !taxIdValid.value) {
      error.value = 'Indica un CIF/NIF válido de la empresa'
      return
    }
    if (!existingIbanMasked.value && !String(form.iban || '').trim()) {
      error.value = 'Indica el IBAN de cobro de la empresa'
      return
    }
    if (form.iban && !ibanValid.value) {
      error.value = 'El IBAN introducido no es válido (revisa el dígito de control)'
      return
    }
  }
  step.value += 1
}

const finishSetup = async () => {
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const token = authStore.getToken ? authStore.getToken() : (authStore as any).token
    if (!token) {
      throw new Error('Sesión expirada. Vuelve a iniciar sesión.')
    }
    const gestorEmail = String(form.email_gestor_fiscal || '').trim().toLowerCase()
    const result = await api.post('/api/v1/auth/onboarding/profile', {
      social_channels: form.social_channels,
      social_links: Object.fromEntries(
        form.social_channels
          .map((c) => [c, String(form.social_links[c] || '').trim()])
          .filter(([, v]) => !!v)
      ),
      whatsapp_number: form.whatsapp_number || null,
      control_horario_policy: form.control_horario_policy || null,
      employees_count: form.employees_count,
      employees: form.employees
        .map((e) => ({
          full_name: String(e.full_name || '').trim(),
          phone: String(e.phone || '').trim(),
          role_title: String(e.role_title || '').trim() || 'employee',
        }))
        .filter((e) => !!e.full_name),
      uses_tpv: !!form.uses_tpv,
      business_hours: String(form.business_hours || '').trim(),
      email_gestor_fiscal: gestorEmail || null,
      autoriza_envio_documentos_a_asesores: !!form.autoriza_envio_documentos_a_asesores,
      legal_name: String(form.legal_name || '').trim() || null,
      tax_id: String(form.tax_id || '').trim() || null,
      iban: String(form.iban || '').trim() || null,
    }, token)
    if (result && result.success === false) {
      throw new Error(result.message || 'No se pudo guardar la configuración')
    }
    const warn = Array.isArray(result?.warnings) && result.warnings.length
      ? ` (${result.warnings.length} aviso(s) menor(es))`
      : ''
    markOnboardingSetupDone()
    success.value = (result?.message || 'Configuración guardada') + warn + '. Redirigiendo al panel ZEUS...'
    setTimeout(() => {
      router.replace('/dashboard')
    }, 500)
  } catch (e: any) {
    try {
      const token2 = authStore.getToken ? authStore.getToken() : (authStore as any).token
      if (token2) {
        const st = await api.get('/api/v1/auth/onboarding/status', token2)
        if (st?.setup_completed) {
          markOnboardingSetupDone()
          success.value = 'La configuración ya está guardada. Redirigiendo al panel...'
          setTimeout(() => router.replace('/dashboard'), 500)
          return
        }
      }
    } catch {
      /* ignore recovery probe */
    }
    const detail = e?.detail ?? e?.data?.detail ?? e?.response?.data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((x) => x?.msg || x?.message || '').filter(Boolean).join(' ')
        : String(e?.message || '')
    if (msg.toLowerCase().includes('unauthorized')) {
      error.value = 'Sesión expirada o inválida. Inicia sesión de nuevo.'
      setTimeout(() => {
        window.location.href = '/auth/login?redirect=/onboarding-setup'
      }, 700)
      return
    }
    if (msg.includes('Error interno del servidor') || msg.includes('Internal Server')) {
      error.value =
        'Error al guardar en el servidor. Los datos principales pueden haberse guardado: recarga e inicia sesión, o reintenta en unos segundos.'
    } else {
      error.value = msg || 'No se pudo guardar la configuración'
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.setup-wrap {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 20px;
  background-image: var(--zeus-bg);
  font-family: var(--zeus-font-sans, 'Inter', sans-serif);
}

.setup-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: var(--zeus-noise-svg);
  opacity: 0.03;
  mix-blend-mode: overlay;
  pointer-events: none;
}

.setup-card {
  position: relative;
  width: 100%;
  max-width: 720px;
  background: var(--zeus-surface, #fff);
  color: var(--zeus-text, #0f172a);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-lg, 14px);
  box-shadow: var(--zeus-shadow-lg);
  padding: 28px;
}

.subtitle { color: var(--zeus-text-secondary, #52607a); margin-top: 0; }

.stepper { display: flex; gap: 16px; margin: 16px 0 20px; font-size: 13px; }
.stepper span {
  position: relative;
  color: var(--zeus-text-muted, #8792a6);
  padding-bottom: 8px;
  transition: color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

/* Paso activo del stepper — solo negrita. El gradiente vibrante queda
   reservado al boton "Siguiente"/"Finalizar", la accion primaria real
   de esta vista. */
.stepper .active {
  color: var(--zeus-text, #0f172a);
  font-weight: 700;
}

.section { display: grid; gap: 10px; }

input, textarea, select {
  width: 100%;
  background: var(--zeus-surface, #fff);
  color: var(--zeus-text, #0f172a);
  border: 1px solid var(--zeus-border, #e1e5eb);
  border-radius: var(--zeus-radius-sm, 8px);
  padding: 10px;
  font-family: inherit;
  transition: border-color var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--zeus-accent, #4f46e5);
  box-shadow: var(--zeus-shadow-focus);
}

.check { display: flex; align-items: center; gap: 8px; }
.check input { width: auto; }

.hint { font-size: 0.85rem; color: var(--zeus-text-muted, #8792a6); margin: 4px 0 12px; }

.channels { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }
.employees-grid { display: grid; gap: 10px; margin: 6px 0 8px; }
.employees-grid label { display: grid; gap: 6px; }

.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }

/* Único botón con gradiente de esta vista: "Siguiente"/"Finalizar
   configuración", la acción primaria real del formulario. */
button {
  background: var(--zeus-accent-gradient, linear-gradient(135deg, #14b8a6 0%, #8b5cf6 50%, #ec4899 100%));
  color: #fff;
  border: 0;
  border-radius: var(--zeus-radius-sm, 8px);
  padding: 10px 16px;
  cursor: pointer;
  font-weight: 600;
  box-shadow: var(--zeus-accent-gradient-shadow, 0 2px 8px rgba(0, 0, 0, 0.15));
  transition: transform var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease),
    box-shadow var(--zeus-dur-hover, 180ms) var(--zeus-ease-micro, ease);
}

button:hover:not(:disabled) {
  box-shadow: var(--zeus-accent-gradient-shadow-hover, 0 4px 14px rgba(0, 0, 0, 0.22));
  transform: translateY(-1px);
}

button:active:not(:disabled) {
  transform: translateY(0) scale(0.97);
  transition-duration: var(--zeus-dur-press, 100ms);
}

button.ghost {
  background: #ffffff;
  color: var(--zeus-text, #0f172a);
  border: 1px solid #D1D5DB;
  box-shadow: none;
}

button.ghost:hover:not(:disabled) {
  border-color: #9aa2af;
  box-shadow: none;
  transform: none;
}

button:disabled { opacity: .6; cursor: not-allowed; }

.error {
  background: var(--zeus-danger-soft, #fdecec);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #b91c1c;
  padding: 10px 14px;
  border-radius: var(--zeus-radius-sm, 8px);
  margin-bottom: 10px;
}

.success {
  background: var(--zeus-success-soft, #e9faf3);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #0d9668;
  padding: 10px 14px;
  border-radius: var(--zeus-radius-sm, 8px);
  margin-bottom: 10px;
}

.section-title {
  margin: 10px 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: var(--zeus-text-secondary, #52607a);
}

.field-error {
  font-size: 0.85rem;
  color: #b91c1c;
  margin: -4px 0 8px;
}

@media (prefers-reduced-motion: reduce) {
  button:hover:not(:disabled),
  button:active:not(:disabled) {
    transform: none;
  }
}
</style>
