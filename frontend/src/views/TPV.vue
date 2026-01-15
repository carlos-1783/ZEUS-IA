<template>
  <div class="tpv-container">
    <!-- Botón de vuelta al Dashboard -->
    <button @click="goToDashboard" class="back-to-dashboard-btn fixed-top-left">
      <span class="btn-icon">📊</span>
      <span class="btn-label">Volver al Dashboard</span>
    </button>

    <!-- Header del TPV -->
    <div class="tpv-header">
      <div class="tpv-title-section">
        <h1 class="tpv-title">💳 TPV Universal Enterprise</h1>
        <p class="tpv-subtitle">Sistema de Punto de Venta</p>
      </div>
      <div class="header-actions">
        <button 
          v-if="tpvConfig.tables_enabled"
          @click="toggleTablesMode" 
          class="header-btn" 
          :class="{ active: tablesMode }"
        >
          🪑 {{ tablesMode ? 'Ver Productos' : 'Modo Mesas' }}
        </button>
        <button @click="checkStatus" class="header-btn">
          🔄 Actualizar
        </button>
        <div v-if="businessProfile" class="business-profile-badge">
          🏢 {{ getBusinessProfileLabel(businessProfile) }}
        </div>
      </div>
    </div>

    <!-- Interfaz Principal del TPV -->
    <div class="tpv-main-interface" v-if="!loading && !error">
      <!-- Panel Izquierdo: Productos o Mesas -->
      <div class="tpv-left-panel">
        <!-- Selector de categorías -->
        <div class="categories-bar" v-if="!tablesMode">
          <button 
            v-for="category in categories" 
            :key="category"
            @click="selectedCategory = category"
            class="category-btn"
            :class="{ active: selectedCategory === category }"
          >
            {{ category }}
          </button>
          <button @click="selectedCategory = 'all'" class="category-btn" :class="{ active: selectedCategory === 'all' }">
            Todos
          </button>
        </div>

        <!-- Grid de Productos -->
        <div class="products-grid" v-if="!tablesMode">
          <div 
            v-for="product in filteredProducts" 
            :key="product.id"
            @click="addProductToCart(product)"
            class="product-card"
          >
            <div class="product-image">
              <span class="product-icon">{{ getProductIcon(product.category) }}</span>
            </div>
            <div class="product-info">
              <h3 class="product-name">{{ product.name }}</h3>
              <p class="product-category">{{ product.category }}</p>
              <div class="product-price">
                <span class="price-label">€</span>
                <span class="price-value">{{ formatPrice(product.price_with_iva || product.price) }}</span>
              </div>
              <div v-if="product.stock !== null" class="product-stock">
                Stock: {{ product.stock }}
              </div>
            </div>
          </div>
          
          <!-- Mensaje si no hay productos -->
          <div v-if="filteredProducts.length === 0" class="no-products">
            <p>📦 No hay productos configurados</p>
            <button @click="openProducts" class="add-product-btn" v-if="!businessProfileLoading">
              ➕ Añadir Producto
            </button>
            <p v-if="businessProfileLoading" class="loading-message">Cargando configuración...</p>
            <p v-else-if="!businessProfile" class="error-message">
              ⚠️ Por favor, configura el tipo de negocio antes de usar el TPV
            </p>
          </div>
        </div>

        <!-- Vista de Mesas (Solo si está habilitado en config) -->
        <div class="tables-grid" v-if="tablesMode && tpvConfig.tables_enabled">
          <div 
            v-for="table in tables" 
            :key="table.id"
            @click="selectTable(table)"
            class="table-card"
            :class="{ 
              occupied: table.status === 'occupied', 
              selected: selectedTable?.id === table.id 
            }"
          >
            <div class="table-number">Mesa {{ table.number }}</div>
            <div class="table-status" :class="table.status">
              {{ table.status === 'occupied' ? '🟢 Ocupada' : '⚪ Libre' }}
            </div>
            <div v-if="table.order_total" class="table-total">
              €{{ formatPrice(table.order_total) }}
            </div>
          </div>
          
          <button @click="addTable" class="add-table-btn">
            ➕ Añadir Mesa
          </button>
        </div>
      </div>

      <!-- Panel Derecho: Carrito y Teclado -->
      <div class="tpv-right-panel">
        <!-- Resumen del Carrito -->
        <div class="cart-panel">
          <div class="cart-header">
            <h2>🛒 Carrito</h2>
            <button @click="clearCart" class="clear-cart-btn" v-if="cart.length > 0">
              🗑️ Limpiar
            </button>
          </div>

          <!-- Lista de productos en el carrito -->
          <div class="cart-items">
            <div 
              v-for="(item, index) in cart" 
              :key="index"
              class="cart-item"
            >
              <div class="cart-item-info">
                <span class="cart-item-name">{{ item.product.name }}</span>
                <span class="cart-item-price">€{{ formatPrice(item.total) }}</span>
              </div>
              <div class="cart-item-controls">
                <button @click="decreaseQuantity(index)" class="qty-btn">-</button>
                <span class="cart-item-qty">{{ item.quantity }}</span>
                <button @click="increaseQuantity(index)" class="qty-btn">+</button>
                <button @click="removeFromCart(index)" class="remove-btn">✕</button>
              </div>
            </div>
            
            <div v-if="cart.length === 0" class="empty-cart">
              <p>El carrito está vacío</p>
              <p class="empty-cart-hint">Selecciona productos para comenzar</p>
            </div>
          </div>

          <!-- Totales -->
          <div class="cart-totals" v-if="cart.length > 0">
            <div class="total-line">
              <span>Subtotal:</span>
              <span>€{{ formatPrice(subtotal) }}</span>
            </div>
            <div class="total-line">
              <span>IVA:</span>
              <span>€{{ formatPrice(ivaTotal) }}</span>
            </div>
            <div class="total-line total-final">
              <span>TOTAL:</span>
              <span>€{{ formatPrice(total) }}</span>
            </div>
          </div>

          <!-- Teclado Numérico -->
          <div class="numeric-keyboard">
            <div class="keyboard-row" v-for="(row, rowIndex) in keyboardLayout" :key="rowIndex">
              <button 
                v-for="key in row" 
                :key="key"
                @click="handleKeyPress(key)"
                class="keyboard-key"
                :class="{ 
                  'key-action': ['C', '⌫'].includes(key),
                  'key-zero': key === '0',
                  'key-enter': key === '✓'
                }"
              >
                {{ key }}
              </button>
            </div>
          </div>

          <!-- Botones de acción -->
          <div class="action-buttons">
            <button @click="processPayment" class="action-btn pay-btn" :disabled="cart.length === 0">
              💳 PAGAR €{{ formatPrice(total) }}
            </button>
            <button 
              v-if="tpvConfig.supports_tickets !== false"
              @click="printTicket" 
              class="action-btn secondary-btn" 
              :disabled="cart.length === 0"
            >
              🖨️ {{ tpvConfig.supports_invoices && cart.length > 0 ? 'Generar Ticket/Factura' : 'Imprimir Ticket' }}
            </button>
            <button @click="openDiscount" class="action-btn secondary-btn" :disabled="cart.length === 0">
              🏷️ Descuento
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Mensajes de estado -->
    <div v-if="loading" class="loading-overlay">
      <p>Cargando TPV...</p>
    </div>
    <div v-if="error" class="error-overlay">
      <p>❌ {{ error }}</p>
      <button @click="checkStatus" class="retry-btn">Reintentar</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// Estado
const loading = ref(false)
const error = ref(null)
const products = ref([])
const cart = ref([])
const selectedCategory = ref('all')
const tablesMode = ref(false)
const selectedTable = ref(null)
const tables = ref([])

// TPV Configuration from backend
const businessProfile = ref(null)
const tpvConfig = ref({})
const businessProfileLoading = ref(true)

// Teclado numérico
const keyboardLayout = [
  ['7', '8', '9'],
  ['4', '5', '6'],
  ['1', '2', '3'],
  ['C', '0', '⌫']
]

// Computed
const categories = computed(() => {
  const cats = new Set(products.value.map(p => p.category))
  return Array.from(cats).sort()
})

const filteredProducts = computed(() => {
  if (selectedCategory.value === 'all') {
    return products.value
  }
  return products.value.filter(p => p.category === selectedCategory.value)
})

const subtotal = computed(() => {
  return cart.value.reduce((sum, item) => sum + (item.product.price * item.quantity), 0)
})

const ivaTotal = computed(() => {
  return cart.value.reduce((sum, item) => {
    const ivaRate = item.product.iva_rate || 21
    return sum + (item.product.price * item.quantity * ivaRate / 100)
  }, 0)
})

const total = computed(() => {
  return subtotal.value + ivaTotal.value
})

// Métodos
const goToDashboard = () => {
  router.push('/dashboard')
}

const formatPrice = (price) => {
  return Number(price).toFixed(2).replace('.', ',')
}

const getProductIcon = (category) => {
  // Iconos más genéricos que funcionan para cualquier tipo de negocio
  const icons = {
    'Bebidas': '🥤',
    'Bebidas Alcohólicas': '🍷',
    'Comida': '🍽️',
    'Postres': '🍰',
    'Entrantes': '🥗',
    'Platos': '🍛',
    'Pizzas': '🍕',
    'Hamburguesas': '🍔',
    'Café': '☕',
    'Servicios': '💼',
    'Productos': '📦',
    'Consultas': '🏥',
    'Tratamientos': '✨',
    'Cortes': '✂️',
    'Repuestos': '🔧',
    'Envíos': '📦',
    'Entradas': '🎫',
    'Medicamentos': '💊',
    'General': '📦',
    'Otros': '📦'
  }
  return icons[category] || '📦'
}

const checkStatus = async () => {
  loading.value = true
  error.value = null
  
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }

    // Cargar productos
    const productsResponse = await fetch('/api/v1/tpv/products', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (productsResponse.ok) {
      const productsData = await productsResponse.json()
      if (productsData.success) {
        products.value = productsData.products || []
        console.log('✅ Productos cargados:', products.value.length)
      }
    }
    
    // Cargar configuración del TPV
    await loadTPVConfig()
  } catch (err) {
    console.error('Error:', err)
    error.value = err.message || 'Error al cargar el TPV'
  } finally {
    loading.value = false
    businessProfileLoading.value = false
  }
}

const loadTPVConfig = async () => {
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) return
    
    const response = await fetch('/api/v1/tpv', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      businessProfile.value = data.business_profile
      tpvConfig.value = data.config || {}
      console.log('✅ Configuración TPV cargada:', businessProfile.value, tpvConfig.value)
      
      // Si no hay business_profile, mostrar configuración inicial
      if (!businessProfile.value) {
        error.value = 'Por favor, configura el tipo de negocio antes de usar el TPV'
      }
    }
  } catch (err) {
    console.error('Error cargando configuración TPV:', err)
  }
}

const getBusinessProfileLabel = (profile) => {
  const labels = {
    'restaurante': 'Restaurante',
    'bar': 'Bar',
    'cafetería': 'Cafetería',
    'tienda_minorista': 'Tienda',
    'peluquería': 'Peluquería',
    'centro_estético': 'Centro Estético',
    'taller': 'Taller',
    'clínica': 'Clínica',
    'discoteca': 'Discoteca',
    'farmacia': 'Farmacia',
    'logística': 'Logística',
    'otros': 'Otros'
  }
  return labels[profile] || profile
}

const addProductToCart = (product) => {
  const existingItem = cart.value.find(item => item.product.id === product.id)
  
  if (existingItem) {
    existingItem.quantity++
    existingItem.total = existingItem.product.price_with_iva * existingItem.quantity
  } else {
    cart.value.push({
      product: product,
      quantity: 1,
      total: product.price_with_iva || product.price
    })
  }
}

const removeFromCart = (index) => {
  cart.value.splice(index, 1)
}

const increaseQuantity = (index) => {
  const item = cart.value[index]
  item.quantity++
  item.total = item.product.price_with_iva * item.quantity
}

const decreaseQuantity = (index) => {
  const item = cart.value[index]
  if (item.quantity > 1) {
    item.quantity--
    item.total = item.product.price_with_iva * item.quantity
  } else {
    removeFromCart(index)
  }
}

const clearCart = () => {
  if (confirm('¿Estás seguro de limpiar el carrito?')) {
    cart.value = []
  }
}

const handleKeyPress = (key) => {
  if (key === 'C') {
    clearCart()
  } else if (key === '⌫') {
    // Borrar último carácter (para futuras mejoras)
    console.log('Backspace')
  } else if (key === '✓') {
    processPayment()
  } else {
    // Tecla numérica (para futuras mejoras como búsqueda rápida)
    console.log('Número:', key)
  }
}

const toggleTablesMode = () => {
  if (!tpvConfig.value.tables_enabled) {
    alert('⚠️ El modo mesas no está disponible para este tipo de negocio')
    return
  }
  tablesMode.value = !tablesMode.value
}

const selectTable = (table) => {
  selectedTable.value = table
  if (table.status === 'occupied') {
    // Cargar pedido existente de la mesa
    alert(`Cargando pedido de Mesa ${table.number}`)
  } else {
    // Nueva venta para esta mesa
    cart.value = []
  }
}

const addTable = () => {
  const newNumber = tables.value.length + 1
  tables.value.push({
    id: newNumber,
    number: newNumber,
    status: 'free',
    order_total: 0
  })
}

const processPayment = async () => {
  if (cart.value.length === 0) return
  
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }
    
    // Validar según configuración
    let employeeId = null
    if (tpvConfig.value.requires_employee) {
      // En una implementación completa, esto pediría seleccionar empleado
      employeeId = prompt('ID del empleado (requerido para este tipo de negocio):')
      if (!employeeId) {
        alert('⚠️ Debe especificar un empleado para procesar esta venta')
        return
      }
    }
    
    let customerData = null
    if (tpvConfig.value.requires_customer_data) {
      const customerName = prompt('Nombre del cliente (requerido):')
      if (!customerName) {
        alert('⚠️ Debe especificar un cliente para procesar esta venta')
        return
      }
      customerData = { name: customerName }
    }
    
    // Preparar datos de la venta
    const saleData = {
      payment_method: 'efectivo', // Por defecto, se puede cambiar después
      employee_id: employeeId,
      customer_data: customerData,
      terminal_id: null,
      cart_items: cart.value.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity,
        unit_price: item.product.price,
        iva_rate: item.product.iva_rate || 21.0
      }))
    }
    
    // Procesar pago en backend
    const response = await fetch('/api/v1/tpv/sale', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(saleData)
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(errorData.detail || `Error ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    
    // Limpiar carrito después del pago exitoso
    cart.value = []
    selectedTable.value = null
    
    // Mostrar confirmación
    alert(`✅ Pago procesado exitosamente\n\nVenta #${result.sale_id || 'N/A'}\nTotal: €${formatPrice(total.value)}\n\nEsta venta se ha registrado automáticamente con RAFAEL.`)
    
    console.log('✅ Venta procesada exitosamente:', result)
  } catch (err) {
    console.error('Error procesando pago:', err)
    alert('❌ Error al procesar el pago: ' + err.message)
  }
}

const printTicket = async () => {
  if (cart.value.length === 0) {
    alert('⚠️ El carrito está vacío')
    return
  }
  
  try {
    // En una implementación completa, esto generaría y descargaría/imprimiría el ticket
    // Por ahora, mostramos un mensaje informativo
    const ticketData = {
      items: cart.value,
      subtotal: subtotal.value,
      iva: ivaTotal.value,
      total: total.value,
      date: new Date().toISOString()
    }
    
    // Crear contenido del ticket
    const ticketText = `
TICKET DE VENTA
${new Date().toLocaleString('es-ES')}

${cart.value.map(item => 
  `${item.product.name} x${item.quantity} - €${formatPrice(item.total)}`
).join('\n')}

---
Subtotal: €${formatPrice(subtotal.value)}
IVA: €${formatPrice(ivaTotal.value)}
TOTAL: €${formatPrice(total.value)}

Gracias por su compra
    `.trim()
    
    // Descargar como archivo de texto
    const blob = new Blob([ticketText], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ticket-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    console.log('✅ Ticket generado')
  } catch (err) {
    console.error('Error generando ticket:', err)
    alert('❌ Error al generar el ticket: ' + err.message)
  }
}

const openDiscount = () => {
  if (cart.value.length === 0) {
    alert('⚠️ El carrito está vacío')
    return
  }
  
  const discountPercent = prompt('Ingresa el descuento (%):', '0')
  if (!discountPercent || isNaN(discountPercent)) return
  
  const discount = parseFloat(discountPercent)
  if (discount < 0 || discount > 100) {
    alert('⚠️ El descuento debe estar entre 0% y 100%')
    return
  }
  
  // Aplicar descuento al carrito
  const discountMultiplier = 1 - (discount / 100)
  cart.value.forEach(item => {
    item.total = (item.product.price_with_iva * item.quantity * discountMultiplier)
  })
  
  console.log(`✅ Descuento del ${discount}% aplicado`)
}

const openProducts = async () => {
  // En una implementación completa, esto abriría un modal o navegaría a gestión de productos
  // Por ahora, redirigimos al endpoint de creación (se puede mejorar con un modal)
  const name = prompt('Nombre del producto:')
  if (!name) return
  
  const price = parseFloat(prompt('Precio (sin IVA):', '0'))
  if (isNaN(price) || price < 0) {
    alert('⚠️ Precio inválido')
    return
  }
  
  const category = prompt('Categoría:', tpvConfig.value.default_categories?.[0] || 'General')
  if (!category) return
  
  try {
    const token = authStore.getToken ? authStore.getToken() : authStore.token
    if (!token) {
      throw new Error('No hay token de autenticación')
    }
    
    const response = await fetch('/api/v1/tpv/products', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name,
        price,
        category,
        iva_rate: tpvConfig.value.default_iva_rate || 21.0
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      alert(`✅ Producto "${name}" creado correctamente`)
      // Recargar productos
      await checkStatus()
    } else {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(errorData.detail || 'Error al crear producto')
    }
  } catch (err) {
    console.error('Error creando producto:', err)
    alert('❌ Error al crear producto: ' + err.message)
  }
}

// Cargar al montar
onMounted(async () => {
  // Cargar configuración primero
  await loadTPVConfig()
  // Luego cargar productos
  await checkStatus()
})
</script>

<style scoped>
.tpv-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
  color: #fff;
  padding: 20px;
  position: relative;
}

.back-to-dashboard-btn.fixed-top-left {
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
}

.back-to-dashboard-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
}

.tpv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  margin: 80px 20px 20px 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.tpv-title {
  font-size: 2rem;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.tpv-subtitle {
  color: rgba(255, 255, 255, 0.6);
  margin: 5px 0 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.header-btn {
  padding: 10px 20px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

.header-btn:hover,
.header-btn.active {
  background: rgba(59, 130, 246, 0.4);
  border-color: rgba(59, 130, 246, 0.6);
}

.tpv-main-interface {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  margin: 20px;
  height: calc(100vh - 200px);
}

.tpv-left-panel {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  padding: 20px;
  overflow-y: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.categories-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.category-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}

.category-btn:hover,
.category-btn.active {
  background: rgba(59, 130, 246, 0.3);
  border-color: rgba(59, 130, 246, 0.5);
  color: #fff;
}

.products-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 15px;
}

.product-card {
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
}

.product-card:hover {
  transform: translateY(-5px);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 8px 25px rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
}

.product-icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 10px;
}

.product-name {
  font-size: 1rem;
  font-weight: 600;
  margin: 10px 0 5px;
  color: #fff;
}

.product-category {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 10px;
}

.product-price {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  margin: 10px 0;
}

.price-label {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.7);
}

.price-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #10b981;
}

.product-stock {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 5px;
}

.tpv-right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cart-panel {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.cart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.cart-header h2 {
  margin: 0;
  font-size: 1.5rem;
}

.clear-cart-btn {
  padding: 6px 12px;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #fca5a5;
  cursor: pointer;
  font-size: 0.85rem;
}

.cart-items {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
}

.cart-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  margin-bottom: 10px;
}

.cart-item-info {
  flex: 1;
}

.cart-item-name {
  display: block;
  font-weight: 600;
  margin-bottom: 5px;
}

.cart-item-price {
  color: #10b981;
  font-weight: 700;
}

.cart-item-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.qty-btn {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: rgba(59, 130, 246, 0.3);
  color: #fff;
  cursor: pointer;
  font-weight: 700;
  font-size: 1.2rem;
}

.qty-btn:hover {
  background: rgba(59, 130, 246, 0.5);
}

.cart-item-qty {
  min-width: 30px;
  text-align: center;
  font-weight: 600;
}

.remove-btn {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  cursor: pointer;
  font-weight: 700;
}

.empty-cart {
  text-align: center;
  padding: 40px 20px;
  color: rgba(255, 255, 255, 0.5);
}

.empty-cart-hint {
  font-size: 0.85rem;
  margin-top: 10px;
}

.cart-totals {
  border-top: 2px solid rgba(255, 255, 255, 0.1);
  padding-top: 15px;
  margin-bottom: 20px;
}

.total-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: rgba(255, 255, 255, 0.7);
}

.total-final {
  font-size: 1.3rem;
  font-weight: 700;
  color: #fff;
  border-top: 2px solid rgba(255, 255, 255, 0.2);
  padding-top: 10px;
  margin-top: 10px;
}

.numeric-keyboard {
  display: grid;
  grid-template-rows: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.keyboard-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.keyboard-key {
  padding: 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 1.5rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}

.keyboard-key:hover {
  background: rgba(59, 130, 246, 0.3);
  border-color: rgba(59, 130, 246, 0.5);
  transform: scale(1.05);
}

.keyboard-key:active {
  transform: scale(0.95);
}

.key-action {
  background: rgba(139, 92, 246, 0.3);
  border-color: rgba(139, 92, 246, 0.5);
}

.key-enter {
  background: rgba(16, 185, 129, 0.3);
  border-color: rgba(16, 185, 129, 0.5);
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-btn {
  padding: 15px;
  border: none;
  border-radius: 10px;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pay-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #fff;
  font-size: 1.2rem;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
}

.pay-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6);
}

.secondary-btn {
  background: rgba(59, 130, 246, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.5);
  color: #fff;
}

.secondary-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.5);
}

/* Mesas */
.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 15px;
}

.table-card {
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  text-align: center;
  transition: all 0.3s;
}

.table-card:hover {
  transform: translateY(-5px);
  border-color: rgba(59, 130, 246, 0.5);
}

.table-card.occupied {
  border-color: rgba(16, 185, 129, 0.5);
  background: rgba(16, 185, 129, 0.1);
}

.table-card.selected {
  border-color: rgba(59, 130, 246, 1);
  background: rgba(59, 130, 246, 0.2);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
}

.table-number {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 10px;
}

.table-status {
  font-size: 0.85rem;
  margin-bottom: 5px;
}

.table-total {
  font-size: 1.1rem;
  font-weight: 700;
  color: #10b981;
  margin-top: 10px;
}

.add-table-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 2px dashed rgba(255, 255, 255, 0.3);
  border-radius: 12px;
  padding: 40px 20px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.5);
  font-size: 1.2rem;
  font-weight: 600;
}

.add-table-btn:hover {
  border-color: rgba(59, 130, 246, 0.5);
  color: #fff;
  background: rgba(59, 130, 246, 0.1);
}

.no-products {
  text-align: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.5);
}

.add-product-btn {
  margin-top: 20px;
  padding: 12px 24px;
  background: rgba(59, 130, 246, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

.loading-overlay,
.error-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.error-overlay {
  gap: 20px;
}

.retry-btn {
  padding: 12px 24px;
  background: rgba(59, 130, 246, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

/* Responsive */
@media (max-width: 1024px) {
  .tpv-main-interface {
    grid-template-columns: 1fr;
    height: auto;
  }
  
  .tpv-right-panel {
    order: -1;
  }
}

@media (max-width: 768px) {
  .products-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }
  
  .back-to-dashboard-btn .btn-label {
    display: none;
  }
}

.business-profile-badge {
  padding: 8px 16px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-radius: 8px;
  color: #fff;
  font-size: 0.9rem;
  font-weight: 600;
  margin-left: 10px;
}
</style>
