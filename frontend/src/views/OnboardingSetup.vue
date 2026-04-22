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

        <label>WhatsApp del negocio</label>
        <input v-model.trim="form.whatsapp_number" type="text" placeholder="+34600111222" />

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
          <li><strong>TPV:</strong> {{ form.uses_tpv ? 'Sí' : 'No' }}</li>
          <li><strong>Horario:</strong> {{ form.business_hours || '—' }}</li>
          <li><strong>Redes:</strong> {{ form.social_channels.join(', ') || '—' }}</li>
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
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const step = ref(1)
const saving = ref(false)
const error = ref('')
const success = ref('')

const availableChannels = ['instagram', 'facebook', 'tiktok', 'google', 'youtube', 'linkedin']
const form = reactive({
  employees_count: 1,
  uses_tpv: true,
  business_hours: '',
  social_channels: ['instagram', 'facebook'] as string[],
  whatsapp_number: '',
  control_horario_policy: '',
})

onMounted(async () => {
  try {
    if (!authStore.isAuthenticated && authStore.initialize) {
      await authStore.initialize()
    }
  } catch (_) {}
  const token = authStore.getToken ? authStore.getToken() : (authStore as any).token
  if (!token) {
    window.location.href = '/auth/login?redirect=/onboarding-setup'
  }
})

const nextStep = () => {
  error.value = ''
  if (step.value === 1) {
    if (form.employees_count < 0) return (error.value = 'Empleados inválido')
    if (!String(form.business_hours || '').trim()) return (error.value = 'Indica el horario del negocio')
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
    await api.post('/api/v1/auth/onboarding/profile', {
      social_channels: form.social_channels,
      whatsapp_number: form.whatsapp_number || null,
      control_horario_policy: form.control_horario_policy || null,
      employees_count: form.employees_count,
      uses_tpv: !!form.uses_tpv,
      business_hours: String(form.business_hours || '').trim(),
    }, token)
    success.value = 'Configuración guardada. Redirigiendo al dashboard...'
    setTimeout(() => {
      window.location.href = '/dashboard'
    }, 700)
  } catch (e: any) {
    error.value = e?.message || 'No se pudo guardar la configuración'
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
input, textarea { width: 100%; background: #0a1228; color: #fff; border: 1px solid #2b3a66; border-radius: 8px; padding: 10px; }
.check { display: flex; align-items: center; gap: 8px; }
.check input { width: auto; }
.channels { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
button { background: #4f46e5; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; }
button.ghost { background: #243056; }
button:disabled { opacity: .6; cursor: not-allowed; }
.error { background: #3a1218; border: 1px solid #7b1d2e; color: #fecdd3; padding: 8px 10px; border-radius: 8px; margin-bottom: 10px; }
.success { background: #0e2d20; border: 1px solid #1d6a4f; color: #bbf7d0; padding: 8px 10px; border-radius: 8px; margin-bottom: 10px; }
</style>
