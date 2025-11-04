<template>
  <div class="checkout-page">
    <div class="checkout-container">
      <!-- Header -->
      <div class="checkout-header">
        <h1>⚡ ZEUS-IA</h1>
        <p>Finalizar compra</p>
      </div>

      <!-- Plan Summary -->
      <div class="plan-summary">
        <h2>Plan seleccionado: {{ planDetails.name }}</h2>
        <p class="plan-desc">{{ planDetails.description }}</p>
        
        <div class="price-breakdown">
          <div class="price-row">
            <span>Setup inicial (pago único)</span>
            <span class="price-value">€{{ planDetails.setupPrice }}</span>
          </div>
          <div class="price-row">
            <span>Suscripción mensual</span>
            <span class="price-value">€{{ planDetails.monthlyPrice }}/mes</span>
          </div>
          <div class="price-row total">
            <span><strong>Total hoy</strong></span>
            <span class="price-value"><strong>€{{ totalToday }}</strong></span>
          </div>
          <p class="price-note">
            Después del setup, pagarás €{{ planDetails.monthlyPrice }}/mes
          </p>
        </div>
      </div>

      <!-- Customer Info -->
      <div class="customer-form" v-if="!paymentSuccess">
        <h3>Información de la empresa</h3>
        
        <div class="form-group">
          <label>Nombre de la empresa *</label>
          <input 
            v-model="customerData.companyName" 
            type="text" 
            placeholder="Mi Empresa S.L."
            required
          />
        </div>

        <div class="form-group">
          <label>Email corporativo *</label>
          <input 
            v-model="customerData.email" 
            type="email" 
            placeholder="contacto@miempresa.com"
            required
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Nombre completo *</label>
            <input 
              v-model="customerData.fullName" 
              type="text" 
              placeholder="Juan Pérez"
              required
            />
          </div>
          <div class="form-group">
            <label>Número de empleados *</label>
            <input 
              v-model.number="customerData.employees" 
              type="number" 
              min="1"
              placeholder="10"
              required
            />
          </div>
        </div>

        <!-- Stripe Payment -->
        <div class="payment-section">
          <h3>Método de pago</h3>
          <div id="card-element" class="card-element"></div>
          <div id="card-errors" class="card-errors" v-if="cardError">{{ cardError }}</div>
        </div>

        <button 
          class="btn-pay" 
          @click="processPayment"
          :disabled="processing"
        >
          <span v-if="!processing">💳 Pagar €{{ totalToday }}</span>
          <span v-else>⏳ Procesando...</span>
        </button>

        <p class="security-note">
          🔒 Pago 100% seguro procesado por Stripe
        </p>
      </div>

      <!-- Success Message -->
      <div class="success-message" v-if="paymentSuccess">
        <div class="success-icon">✅</div>
        <h2>¡Pago completado!</h2>
        <p>Bienvenido a ZEUS-IA, {{ customerData.companyName }}</p>
        <p class="success-details">
          Hemos enviado un email a <strong>{{ customerData.email }}</strong> con tus credenciales de acceso.
        </p>
        <button class="btn-dashboard" @click="goToDashboard">
          Ir al Dashboard ⚡
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// Plan details
const plans = {
  startup: {
    name: 'ZEUS STARTUP',
    description: '1-5 empleados - Ideal para autónomos',
    setupPrice: 500,
    monthlyPrice: 99,
    priceId: 'price_1SPfE8RkVIjZaYJnVhWpJFCy',
    setupPriceId: 'price_1SPfE8RkVIjZaYJnOsoNG7kZ'
  },
  growth: {
    name: 'ZEUS GROWTH',
    description: '6-25 empleados - Para PYMEs en crecimiento',
    setupPrice: 1500,
    monthlyPrice: 299,
    priceId: 'price_1SPfE9RkVIjZaYJnXyYjpum9',
    setupPriceId: 'price_1SPfE9RkVIjZaYJna2Pu1wsZ'
  },
  business: {
    name: 'ZEUS BUSINESS',
    description: '26-100 empleados - Empresas establecidas',
    setupPrice: 2500,
    monthlyPrice: 699,
    priceId: 'price_1SPfEARkVIjZaYJnvJYJQzzI',
    setupPriceId: 'price_1SPfEARkVIjZaYJnyblS25rr'
  },
  enterprise: {
    name: 'ZEUS ENTERPRISE',
    description: '101+ empleados - Grandes corporaciones',
    setupPrice: 5000,
    monthlyPrice: 1500,
    priceId: 'price_1SPfEBRkVIjZaYJnSGFyux8o',
    setupPriceId: 'price_1SPfEBRkVIjZaYJnjk5cB1ma'
  }
}

const selectedPlan = route.params.plan || 'growth'
const planDetails = computed(() => plans[selectedPlan])
const totalToday = computed(() => planDetails.value.setupPrice + planDetails.value.monthlyPrice)

// Customer data
const customerData = ref({
  companyName: '',
  email: '',
  fullName: '',
  employees: null
})

// Stripe
let stripe = null
let cardElement = null
const cardError = ref('')
const processing = ref(false)
const paymentSuccess = ref(false)

onMounted(async () => {
  // Cargar Stripe.js
  const script = document.createElement('script')
  script.src = 'https://js.stripe.com/v3/'
  script.onload = initializeStripe
  document.head.appendChild(script)
})

const initializeStripe = () => {
  // Usar la publishable key
  stripe = window.Stripe('pk_test_51SPKKlRkVIjZaYJnqT8QAWqcZsEoTuKGTU0vgF7ZOHj98wAYwCwxBQy3YpC4bc6kCBtNhy1QfBfGVcnxbynioHzX00rJEovHQc')
  
  const elements = stripe.elements()
  cardElement = elements.create('card', {
    style: {
      base: {
        fontSize: '16px',
        color: '#fff',
        '::placeholder': {
          color: 'rgba(255, 255, 255, 0.5)'
        }
      }
    }
  })
  
  cardElement.mount('#card-element')
  
  cardElement.on('change', (event) => {
    cardError.value = event.error ? event.error.message : ''
  })
}

const processPayment = async () => {
  if (!customerData.value.companyName || !customerData.value.email || !customerData.value.fullName) {
    cardError.value = 'Por favor completa todos los campos'
    return
  }

  processing.value = true
  cardError.value = ''

  try {
    // 1. Crear Payment Intent en el backend
    const response = await fetch(`${import.meta.env.VITE_API_URL}/integrations/stripe/payment-intent`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        amount: totalToday.value,
        customer_email: customerData.value.email,
        description: `${planDetails.value.name} - Setup + Primera mensualidad`,
        metadata: {
          plan: selectedPlan,
          company_name: customerData.value.companyName,
          full_name: customerData.value.fullName,
          employees: customerData.value.employees
        }
      })
    })

    const paymentIntent = await response.json()

    if (!paymentIntent.success) {
      throw new Error(paymentIntent.error || 'Error al crear payment intent')
    }

    // 2. Confirmar pago con Stripe
    const { error, paymentIntent: confirmedPayment } = await stripe.confirmCardPayment(
      paymentIntent.client_secret,
      {
        payment_method: {
          card: cardElement,
          billing_details: {
            name: customerData.value.fullName,
            email: customerData.value.email
          }
        }
      }
    )

    if (error) {
      cardError.value = error.message
      processing.value = false
      return
    }

    // 3. Pago exitoso
    if (confirmedPayment.status === 'succeeded') {
      // Aquí crear la cuenta del usuario y la suscripción
      await createUserAccount()
      
      paymentSuccess.value = true
      processing.value = false
    }

  } catch (error) {
    cardError.value = error.message || 'Error al procesar el pago'
    processing.value = false
  }
}

const createUserAccount = async () => {
  // TODO: Llamar al backend para crear cuenta y suscripción
  console.log('Creando cuenta para:', customerData.value)
}

const goToDashboard = () => {
  router.push('/auth/login')
}
</script>

<style scoped>
.checkout-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0a0e1a 0%, #1a1f2e 100%);
  padding: 40px 20px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.checkout-container {
  max-width: 600px;
  width: 100%;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.checkout-header {
  text-align: center;
  margin-bottom: 40px;
}

.checkout-header h1 {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 8px;
}

.checkout-header p {
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

.plan-summary {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 32px;
}

.plan-summary h2 {
  font-size: 24px;
  margin: 0 0 8px;
  color: #3b82f6;
}

.plan-desc {
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 20px;
}

.price-breakdown {
  margin-top: 20px;
}

.price-row {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.price-row.total {
  border-bottom: none;
  padding-top: 16px;
  margin-top: 8px;
  border-top: 2px solid rgba(59, 130, 246, 0.5);
  font-size: 18px;
}

.price-value {
  color: #3b82f6;
  font-weight: 600;
}

.price-note {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 12px;
  text-align: center;
}

.customer-form h3 {
  font-size: 20px;
  margin: 0 0 24px;
  color: #fff;
}

.form-group {
  margin-bottom: 20px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-group label {
  display: block;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 16px;
  transition: all 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(255, 255, 255, 0.08);
}

.payment-section {
  margin: 32px 0;
}

.payment-section h3 {
  font-size: 20px;
  margin: 0 0 16px;
}

.card-element {
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  transition: all 0.3s;
}

.card-element:focus-within {
  border-color: #3b82f6;
  background: rgba(255, 255, 255, 0.08);
}

.card-errors {
  color: #ef4444;
  font-size: 14px;
  margin-top: 8px;
}

.btn-pay {
  width: 100%;
  padding: 18px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 24px;
}

.btn-pay:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 40px rgba(59, 130, 246, 0.5);
}

.btn-pay:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.security-note {
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  margin-top: 16px;
}

/* Success Message */
.success-message {
  text-align: center;
  padding: 40px 20px;
}

.success-icon {
  font-size: 80px;
  margin-bottom: 20px;
  animation: scaleIn 0.5s ease-out;
}

@keyframes scaleIn {
  from {
    transform: scale(0);
  }
  to {
    transform: scale(1);
  }
}

.success-message h2 {
  font-size: 32px;
  margin: 0 0 16px;
  color: #10b981;
}

.success-message p {
  color: rgba(255, 255, 255, 0.8);
  margin: 12px 0;
  font-size: 16px;
}

.success-details {
  margin-top: 24px;
  padding: 20px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 12px;
}

.btn-dashboard {
  margin-top: 32px;
  padding: 16px 48px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-dashboard:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 40px rgba(59, 130, 246, 0.5);
}

/* Responsive */
@media (max-width: 768px) {
  .checkout-container {
    padding: 24px;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .checkout-header h1 {
    font-size: 24px;
  }

  .plan-summary h2 {
    font-size: 20px;
  }
}
</style>

