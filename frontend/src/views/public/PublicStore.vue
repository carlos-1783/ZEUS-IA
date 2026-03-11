<template>
  <div class="min-h-screen bg-gray-50">
    <!-- No disponible -->
    <div v-if="notFound" class="max-w-md mx-auto px-4 py-16 text-center">
      <h1 class="text-xl font-semibold text-gray-800">Web no disponible</h1>
      <p class="mt-2 text-gray-600">Este negocio no tiene página pública activa.</p>
    </div>

    <!-- Contenido cuando la web está activa -->
    <template v-else>
      <header class="bg-white shadow-sm">
        <div class="max-w-3xl mx-auto px-4 py-6">
          <h1 class="text-2xl font-bold text-gray-900">{{ siteName }}</h1>
        </div>
      </header>

      <main class="max-w-3xl mx-auto px-4 py-8">
        <!-- Formulario de reserva -->
        <section v-if="reservationsEnabled" class="bg-white rounded-lg shadow p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">Reservar mesa</h2>

          <div v-if="reservationSuccess" class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-800">
            {{ reservationSuccess }}
          </div>
          <div v-if="reservationError" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            {{ reservationError }}
          </div>

          <form class="space-y-4" @submit.prevent="submitReservation">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nombre *</label>
                <input v-model="form.guest_name" type="text" required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Teléfono *</label>
                <input v-model="form.guest_phone" type="tel" required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input v-model="form.guest_email" type="email"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Fecha *</label>
                <input v-model="form.reservation_date" type="date" required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Hora *</label>
                <input v-model="form.reservation_time" type="time" required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Comensales *</label>
              <input v-model.number="form.num_guests" type="number" min="1" max="50" required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Notas</label>
              <textarea v-model="form.notes" rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"></textarea>
            </div>
            <button type="submit" :disabled="sending"
              class="w-full py-2 px-4 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50">
              {{ sending ? 'Enviando...' : 'Enviar reserva' }}
            </button>
          </form>
        </section>
      </main>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config'

const route = useRoute()
const slug = computed(() => route.params.slug || '')

const notFound = ref(false)
const siteName = ref('')
const reservationsEnabled = ref(true)
const sending = ref(false)
const reservationSuccess = ref('')
const reservationError = ref('')

const form = reactive({
  guest_name: '',
  guest_phone: '',
  guest_email: '',
  reservation_date: '',
  reservation_time: '21:00',
  num_guests: 2,
  notes: ''
})

function setDefaultDate () {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  if (!form.reservation_date) form.reservation_date = `${y}-${m}-${day}`
}

async function loadInfo () {
  if (!slug.value) {
    notFound.value = true
    return
  }
  const base = (typeof API_BASE_URL === 'string' ? API_BASE_URL : '').replace(/\/+$/, '')
  const url = `${base}/p/${encodeURIComponent(slug.value)}/info`
  try {
    const res = await fetch(url)
    if (!res.ok) {
      notFound.value = true
      return
    }
    const data = await res.json()
    siteName.value = data.name || 'Negocio'
    reservationsEnabled.value = data.reservations_enabled !== false
    setDefaultDate()
  } catch {
    notFound.value = true
  }
}

async function submitReservation () {
  reservationError.value = ''
  reservationSuccess.value = ''
  sending.value = true
  const base = (typeof API_BASE_URL === 'string' ? API_BASE_URL : '').replace(/\/+$/, '')
  const url = `${base}/p/${encodeURIComponent(slug.value)}/reservations`
  const timeStr = form.reservation_time.length === 5 ? form.reservation_time : form.reservation_time + ':00'
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guest_name: form.guest_name.trim(),
        guest_phone: form.guest_phone.trim(),
        guest_email: form.guest_email?.trim() || null,
        reservation_date: form.reservation_date,
        reservation_time: timeStr.slice(0, 5),
        num_guests: form.num_guests,
        notes: form.notes?.trim() || null
      })
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      reservationError.value = data.detail || 'No se pudo enviar la reserva. Inténtalo de nuevo.'
      return
    }
    reservationSuccess.value = data.message || 'Reserva recibida. Te confirmaremos pronto.'
    form.guest_name = ''
    form.guest_phone = ''
    form.guest_email = ''
    form.notes = ''
  } catch {
    reservationError.value = 'Error de conexión. Inténtalo de nuevo.'
  } finally {
    sending.value = false
  }
}

onMounted(loadInfo)
</script>
