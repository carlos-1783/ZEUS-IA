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
  social_channels: ['instagram', 'facebook'] as string[],
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
})

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
    if (status?.email_gestor_fiscal) {
      form.email_gestor_fiscal = String(status.email_gestor_fiscal)
    }
    if (status?.autoriza_envio_documentos_a_asesores != null) {
      form.autoriza_envio_documentos_a_asesores = !!status.autoriza_envio_documentos_a_asesores
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
      email_gestor_fiscal: String(form.email_gestor_fiscal || '').trim().toLowerCase(),
      autoriza_envio_documentos_a_asesores: !!form.autoriza_envio_documentos_a_asesores,
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
.setup-wrap { min-height: 100vh; display: grid; place-items: center; padding: 20px; background: #0b1020; }
.setup-card { width: 100%; max-width: 720px; background: #121a33; color: #fff; border: 1px solid #243056; border-radius: 14px; padding: 22px; }
.subtitle { color: #b9c3e4; margin-top: 0; }
.stepper { display: flex; gap: 10px; margin: 10px 0 16px; font-size: 13px; }
.stepper span { opacity: .6; }
.stepper .active { opacity: 1; font-weight: 700; }
.section { display: grid; gap: 8px; }
input, textarea, select { width: 100%; background: #0a1228; color: #fff; border: 1px solid #2b3a66; border-radius: 8px; padding: 10px; }
.check { display: flex; align-items: center; gap: 8px; }
.check input { width: auto; }
.hint { font-size: 0.85rem; color: #9ca8cf; margin: 4px 0 12px; }
.channels { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }
.employees-grid { display: grid; gap: 10px; margin: 6px 0 8px; }
.employees-grid label { display: grid; gap: 6px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
button { background: #4f46e5; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; }
button.ghost { background: #243056; }
button:disabled { opacity: .6; cursor: not-allowed; }
.error { background: #3a1218; border: 1px solid #7b1d2e; color: #fecdd3; padding: 8px 10px; border-radius: 8px; margin-bottom: 10px; }
.success { background: #0e2d20; border: 1px solid #1d6a4f; color: #bbf7d0; padding: 8px 10px; border-radius: 8px; margin-bottom: 10px; }
</style>
