<template>
  <div class="tpv-container">
    <!-- Botón de vuelta al Dashboard -->
    <button @click="goToDashboard" class="back-to-dashboard-btn fixed-top-left">
      <span class="btn-icon">📊</span>
      <span class="btn-label">{{ $t('tpv.backToDashboard') }}</span>
    </button>

    <!-- Header del TPV -->
    <div class="tpv-header">
      <div class="tpv-title-section">
        <h1 class="tpv-title">💳 {{ $t('tpv.title') }}</h1>
        <p class="tpv-subtitle">{{ $t('tpv.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <button 
          v-if="tpvConfig.tables_enabled"
          @click="toggleTablesMode" 
          class="header-btn" 
          :class="{ active: tablesMode }"
        >
          🪑 {{ tablesMode ? $t('tpv.viewProducts') : $t('tpv.tablesMode') }}
        </button>
        <button 
          @click="copyComanderoLink" 
          class="header-btn"
          title="Copiar enlace del TPV para compartir con empleados (comandero digital)"
        >
          🔗 {{ $t('tpv.shareComandero') || 'Compartir comandero' }}
        </button>
        <button @click="checkStatus" class="header-btn">
          🔄 {{ $t('tpv.refresh') }}
        </button>
        <div v-if="businessProfile" class="business-profile-badge">
          🏢 {{ getBusinessProfileLabel(businessProfile) }}
        </div>
      </div>
    </div>

    <!-- Interfaz Principal del TPV -->
    <div class="tpv-main-interface" v-if="!loading && !errorMessage">
      <!-- Panel Izquierdo: Productos o Mesas -->
      <div class="tpv-left-panel">
        <!-- Con mesa seleccionada: barra "Mesa X" + volver a mesas -->
        <div v-if="tablesMode && tpvConfig.tables_enabled && selectedTable" class="tables-selected-bar">
          <button type="button" @click="backToTablesList" class="back-to-tables-btn" title="Volver a mesas">
            ← {{ $t('tpv.tablesMode') || 'Mesas' }}
          </button>
          <span class="tables-selected-label">Añadir productos a Mesa {{ selectedTable?.number }}</span>
        </div>
        <!-- Selector de categorías (productos o cuando hay mesa seleccionada para anotar) -->
        <div class="categories-bar" v-if="!tablesMode || selectedTable">
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
            {{ $t('tpv.categories.all') }}
          </button>
        </div>

        <!-- Grid de Productos (visible también con mesa seleccionada para anotar en la mesa) -->
        <div class="products-grid" v-if="!tablesMode || selectedTable">
          <!-- Botón Añadir Producto (siempre visible, validación al guardar) -->
          <button 
            v-if="!businessProfileLoading"
            @click.stop.prevent="openProducts" 
            @mousedown.stop
            @mouseup.stop
            class="add-product-card"
            title="Añadir nuevo producto"
            type="button"
          >
            <div class="add-product-content">
              <span class="add-product-icon">➕</span>
              <span class="add-product-label">{{ $t('tpv.products.add') || 'Añadir Producto' }}</span>
            </div>
          </button>
          
          <div 
            v-for="product in filteredProducts" 
            :key="product.id || product.name"
            class="product-card"
          >
            <div @click="addProductToCart(product)" class="product-clickable">
              <div class="product-image">
                <!-- Prioridad: image > icon > default -->
                <img 
                  v-if="product.image" 
                  :src="product.image" 
                  :alt="product.name"
                  class="product-image-file"
                  @error="handleImageError"
                />
                <span 
                  v-else-if="product.icon" 
                  class="product-icon"
                >{{ getIconEmoji(product.icon) }}</span>
                <span 
                  v-else 
                  class="product-icon"
                >{{ getProductIcon(product.category) }}</span>
              </div>
              <div class="product-info">
                <h3 class="product-name">{{ product.name }}</h3>
                <p class="product-category">{{ product.category }}</p>
                <div class="product-price">
                  <span class="price-label">€</span>
                  <span class="price-value">{{ formatPrice(product.price_with_iva || product.price) }}</span>
                </div>
                <div v-if="product.stock !== null" class="product-stock">
                  {{ $t('tpv.products.stock') }}: {{ product.stock }}
                </div>
              </div>
            </div>
            <!-- Botones CRUD (solo para ADMIN y SUPERUSER) -->
            <div class="product-actions" v-if="canEditProducts">
              <button 
                @click.stop="editProduct(product)" 
                class="product-action-btn edit-btn"
                title="Editar producto"
              >
                ✏️
              </button>
              <button 
                v-if="isSuperuser"
                @click.stop="deleteProduct(product)" 
                class="product-action-btn delete-btn"
                title="Eliminar producto"
              >
                🗑️
              </button>
            </div>
          </div>
          
          <!-- Mensaje si no hay productos -->
          <div v-if="filteredProducts.length === 0" class="no-products">
            <p>📦 {{ $t('tpv.products.empty') }}</p>
            <p v-if="businessProfileLoading" class="loading-message">{{ $t('tpv.products.loading') }}</p>
            <p v-else-if="!businessProfile" class="error-message">
              ⚠️ {{ $t('tpv.products.configureBusinessProfile') }}
            </p>
            <p v-else-if="!canEditProducts" class="error-message">
              ⚠️ No tienes permisos para crear productos. Contacta con un administrador.
            </p>
          </div>
        </div>

        <!-- Vista de Mesas (cuando modo mesas y no hay mesa seleccionada) -->
        <div class="tables-grid" v-if="tablesMode && tpvConfig.tables_enabled && !selectedTable">
          <div 
            v-for="table in tables" 
            :key="table.id"
            @click="selectTable(table)"
            class="table-card"
            :class="{ 
              occupied: getTableOrderTotal(table.id) > 0, 
              selected: selectedTable?.id === table.id 
            }"
          >
            <div class="table-number">Mesa {{ table.number }}</div>
            <div class="table-status" :class="getTableOrderTotal(table.id) > 0 ? 'occupied' : 'free'">
              {{ getTableOrderTotal(table.id) > 0 ? '🟢 Ocupada' : '⚪ Libre' }}
            </div>
            <div v-if="getTableOrderTotal(table.id) > 0" class="table-total">
              €{{ formatPrice(getTableOrderTotal(table.id)) }}
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
            <h2><span class="tpv-icon tpv-icon-ui">🛒</span> Carrito <span v-if="cart.length > 0" class="cart-count-badge">({{ cart.length }})</span></h2>
            <button @click="clearCart" class="clear-cart-btn" v-if="cart.length > 0">
              <span class="tpv-icon tpv-icon-ui">🗑️</span> Limpiar
            </button>
          </div>

          <!-- Feedback visual del carrito -->
          <transition name="fade-slide">
            <div v-if="cartFeedback" class="cart-feedback" :class="cartFeedback.type">
              <span class="feedback-icon">
                {{ cartFeedback.type === 'added' ? '✅' : cartFeedback.type === 'removed' ? '🗑️' : cartFeedback.type === 'cleared' ? '🧹' : '🔄' }}
              </span>
              <span class="feedback-message">{{ cartFeedback.message }}</span>
            </div>
          </transition>

          <!-- Bloque 1: Lista productos -->
          <div class="cart-block cart-block-list">
          <div class="cart-items">
            <div 
              v-for="(item, index) in cart" 
              :key="`cart-item-${item.id || item.product?.id || index}-${index}`"
              class="cart-item"
              :class="{ 'cart-item--active': index === activeCartIndex }"
              @click="setActiveCartIndex(index)"
            >
              <div class="cart-item-info">
                <span class="cart-item-name">{{ item.name || item.product?.name || 'Producto' }}</span>
                <span class="cart-item-price">€{{ formatPrice(item.total ?? item.subtotal_with_iva ?? item.subtotal ?? 0) }}</span>
                <span class="cart-item-unit-price" v-if="item.quantity > 1">
                  €{{ formatPrice(item.unit_price_with_iva || item.product?.price_with_iva || 0) }} / unidad
                </span>
              </div>
              <!-- Controles de edición (solo en estado CART) -->
              <div class="cart-item-controls" v-if="tpvState === TPV_STATES.CART">
                <button 
                  @click="decreaseQuantity(index)" 
                  class="qty-btn decrement-btn"
                  :title="$t('tpv.cart.decreaseQuantity')"
                >
                  ➖
                </button>
                <span class="cart-item-qty">{{ item.quantity }}</span>
                <button 
                  @click="increaseQuantity(index)" 
                  class="qty-btn increment-btn"
                  :title="$t('tpv.cart.increaseQuantity')"
                  :disabled="item.quantity >= 999"
                >
                  ➕
                </button>
                <button 
                  @click="removeFromCart(index)" 
                  class="remove-btn"
                  :title="$t('tpv.cart.removeItem')"
                >
                  🗑
                </button>
              </div>
              <!-- Vista de solo lectura (PRE_PAYMENT, PAYMENT, CLOSED) -->
              <div class="cart-item-readonly" v-else>
                <span class="cart-item-qty-readonly">{{ item.quantity }}x</span>
              </div>
            </div>
            
            <div v-if="cart.length === 0" class="empty-cart">
              <div class="empty-cart-icon">🛒</div>
              <p class="empty-cart-message">{{ $t('tpv.cart.emptyMessage') || 'Añade productos o servicios para comenzar' }}</p>
              <p class="empty-cart-hint">💡 Haz clic en cualquier producto para añadirlo al carrito</p>
            </div>
          </div>
          </div>

          <!-- Bloque 2: Resumen -->
          <div class="cart-block cart-block-summary">
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

          <!-- Bloque 3: Acciones -->
          <div class="cart-block cart-block-actions">
          <div class="action-buttons">
            <!-- Estado CART: Mostrar botón para revisar y pagar -->
            <template v-if="tpvState === TPV_STATES.CART">
              <button 
                @click="goToPrePayment" 
                class="action-btn pay-btn" 
                :disabled="!Array.isArray(cart) || cart.length === 0"
                :title="(!Array.isArray(cart) || cart.length === 0) ? 'Añade productos al carrito para continuar' : 'Revisar y proceder al pago'"
              >
                <span class="tpv-icon tpv-icon-primary">💳</span> REVISAR Y PAGAR €{{ formatPrice(total) }}
              </button>
              <button 
                v-if="tpvConfig.supports_tickets !== false"
                @click="printTicket" 
                class="action-btn secondary-btn" 
                :disabled="cart.length === 0"
                :title="cart.length === 0 ? 'Añade productos al carrito para generar ticket' : 'Generar e imprimir ticket'"
              >
                <span class="tpv-icon tpv-icon-ui">🖨️</span> {{ tpvConfig.supports_invoices && cart.length > 0 ? 'Generar Ticket/Factura' : 'Imprimir Ticket' }}
              </button>
              <button 
                @click="openDiscount" 
                class="action-btn secondary-btn" 
                :disabled="cart.length === 0"
                :title="cart.length === 0 ? 'Añade productos al carrito para aplicar descuento' : 'Aplicar descuento al carrito'"
              >
                <span class="tpv-icon tpv-icon-ui">🏷️</span> Descuento
              </button>
            </template>
            
            <!-- Estado PRE_PAYMENT: Mostrar botones para volver o confirmar pago -->
            <template v-else-if="tpvState === TPV_STATES.PRE_PAYMENT">
              <button 
                @click="startPayment" 
                class="action-btn pay-btn"
                :title="'Confirmar y proceder al pago de €' + formatPrice(total)"
              >
                <span class="tpv-icon tpv-icon-primary">💳</span> CONFIRMAR PAGO €{{ formatPrice(total) }}
              </button>
              <button 
                @click="backToCart" 
                class="action-btn secondary-btn"
                title="Volver al carrito para editar productos (no se pierde el estado)"
              >
                <span class="tpv-icon tpv-icon-ui">←</span> Volver al Carrito
              </button>
              <button 
                @click="openDiscount" 
                class="action-btn secondary-btn"
                title="Aplicar descuento al carrito"
              >
                <span class="tpv-icon tpv-icon-ui">🏷️</span> Descuento
              </button>
            </template>
            
            <!-- Estado PAYMENT: Mostrar botones de pago o cancelar -->
            <template v-else-if="tpvState === TPV_STATES.PAYMENT">
              <button 
                @click="processPayment" 
                class="action-btn pay-btn"
                :title="'Finalizar pago de €' + formatPrice(total) + ' - La venta se registrará automáticamente'"
              >
                <span class="tpv-icon tpv-icon-primary">✅</span> FINALIZAR PAGO €{{ formatPrice(total) }}
              </button>
              <button 
                @click="cancelPayment" 
                class="action-btn secondary-btn"
                title="Cancelar pago y volver a revisión (no se pierde el carrito)"
              >
                <span class="tpv-icon tpv-icon-ui">←</span> Cancelar
              </button>
            </template>
            
            <!-- Estado CLOSED: Mostrar botones para nueva venta -->
            <template v-else-if="tpvState === TPV_STATES.CLOSED">
              <button 
                @click="resetTPV" 
                class="action-btn pay-btn"
                title="Iniciar una nueva venta (se limpiará el carrito)"
              >
                <span class="tpv-icon tpv-icon-primary">🆕</span> NUEVA VENTA
              </button>
              <button 
                v-if="tpvConfig.supports_invoices"
                @click="generateInvoice" 
                class="action-btn secondary-btn"
                :title="lastSaleTicketId ? 'Generar factura para el ticket #' + lastSaleTicketId : 'Generar factura para el último ticket'"
              >
                <span class="tpv-icon tpv-icon-ui">🧾</span> Generar Factura
              </button>
            </template>
          </div>
          </div>
          
          <!-- Nota de pago (visible en PRE_PAYMENT) -->
          <div v-if="tpvState === TPV_STATES.PRE_PAYMENT" class="payment-note-section">
            <label for="payment-note">Nota adicional (opcional):</label>
            <textarea 
              id="payment-note"
              v-model="paymentNote" 
              class="payment-note-input"
              placeholder="Añade una nota para esta venta..."
              rows="2"
            ></textarea>
          </div>
        </div>
      </div>
    </div>

    <!-- Mensajes de estado -->
    <div v-if="loading" class="loading-overlay">
      <p>Cargando TPV...</p>
    </div>
    <div v-if="errorMessage" class="error-overlay">
      <p>❌ {{ errorMessage }}</p>
      <button @click="checkStatus" class="retry-btn">Reintentar</button>
    </div>
    
    <!-- Modal de Producto (Crear/Editar) -->
    <div v-if="showProductModal" class="modal-overlay" @click.self="showProductModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ editingProduct ? '✏️ Editar Producto' : '➕ Crear Producto' }}</h2>
          <button @click="showProductModal = false" class="modal-close">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Nombre del producto *</label>
            <input 
              v-model="productForm.name" 
              type="text" 
              placeholder="Ej: Café con leche"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Precio (sin IVA) *</label>
            <input 
              v-model.number="productForm.price" 
              type="number" 
              step="0.01"
              min="0"
              placeholder="0.00"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Categoría</label>
            <input 
              v-model="productForm.category" 
              type="text" 
              placeholder="General"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>IVA (%)</label>
            <input 
              v-model.number="productForm.iva_rate" 
              type="number" 
              step="0.1"
              min="0"
              max="100"
              placeholder="21.0"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label>Stock (opcional)</label>
            <input 
              v-model.number="productForm.stock" 
              type="number" 
              min="0"
              placeholder="Dejar vacío si no aplica"
              class="form-input"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showProductModal = false" class="btn-cancel">Cancelar</button>
          <button @click="saveProduct" class="btn-save">{{ editingProduct ? 'Guardar Cambios' : 'Crear Producto' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import { useNotifications } from '@/composables/useNotifications'
import { jwtDecode } from 'jwt-decode'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const { success, error, warning, info } = useNotifications()

// Estados del TPV
const TPV_STATES = {
  CART: 'CART',           // Estado editable de venta
  PRE_PAYMENT: 'PRE_PAYMENT', // Revisión antes del pago
  PAYMENT: 'PAYMENT',     // Proceso de cobro
  CLOSED: 'CLOSED'        // Venta finalizada
}

// Estado
const loading = ref(false)
const errorMessage = ref(null)
const products = ref([])
const cart = ref([])
const activeCartIndex = ref(-1) // Índice del ítem activo en el carrito (para teclado numérico)
const quantityInputBuffer = ref('') // Buffer de entrada numérica (para cantidades 1-999)
const selectedCategory = ref('all')
const tablesMode = ref(false)
const selectedTable = ref(null)
const tables = ref([])
/** Carrito por mesa: cada mesa es independiente (id de mesa -> array de ítems) */
const tableCarts = ref({})
const tpvState = ref(TPV_STATES.CART) // Estado actual del TPV
const paymentNote = ref('') // Nota adicional para el pago
const cartFeedback = ref(null) // Feedback visual del carrito
const cartFeedbackTimeout = ref(null) // Timeout para ocultar feedback
const lastSaleTicketId = ref(null) // ID del último ticket vendido

// TPV Configuration from backend
const businessProfile = ref(null)
const tpvConfig = ref({})
const businessProfileLoading = ref(true)

// Permisos de usuario
const userRole = ref(null)
const isSuperuser = ref(false)
const canEditProducts = computed(() => {
  return isSuperuser.value || userRole.value === 'ADMIN'
})

// Estado del modal de producto
const showProductModal = ref(false)
const editingProduct = ref(null)
const productForm = ref({
  name: '',
  price: 0,
  category: 'General',
  iva_rate: 21.0,
  stock: null,
  image: null,
  icon: null
})

// Refs para manejo de imágenes
const imageFile = ref(null)
const imagePreview = ref(null)
const iconOptions = ['coffee', 'food', 'service', 'house', 'default']

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

const safeNumber = (value) => {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : 0
}

const getItemIvaRate = (item) => {
  const fallback = tpvConfig.value?.default_iva_rate ?? 21
  return safeNumber(item?.product?.iva_rate ?? item?.iva_rate ?? fallback)
}

const calcItemSubtotalNet = (item) => {
  if (item?.subtotal !== undefined && item?.subtotal !== null) return safeNumber(item.subtotal)
  const unitNet = item?.unit_price ?? item?.price ?? item?.product?.price ?? 0
  return safeNumber(unitNet) * safeNumber(item?.quantity ?? 1)
}

const calcItemIva = (item) => {
  if (item?.iva !== undefined && item?.iva !== null) return safeNumber(item.iva)
  if (item?.subtotal_with_iva !== undefined && item?.subtotal_with_iva !== null && item?.subtotal !== undefined && item?.subtotal !== null) {
    return safeNumber(item.subtotal_with_iva) - safeNumber(item.subtotal)
  }
  const net = calcItemSubtotalNet(item)
  return net * (getItemIvaRate(item) / 100)
}

const calcItemTotal = (item) => {
  if (item?.total !== undefined && item?.total !== null) return safeNumber(item.total)
  if (item?.subtotal_with_iva !== undefined && item?.subtotal_with_iva !== null) return safeNumber(item.subtotal_with_iva)
  return calcItemSubtotalNet(item) + calcItemIva(item)
}

// Totales del carrito (fuente de verdad: neto + IVA; si backend ya entrega totales por línea, se respetan)
const subtotal = computed(() => {
  if (!Array.isArray(cart.value) || cart.value.length === 0) return 0
  return cart.value.reduce((sum, item) => sum + calcItemSubtotalNet(item), 0)
})

const ivaTotal = computed(() => {
  if (!Array.isArray(cart.value) || cart.value.length === 0) return 0
  return cart.value.reduce((sum, item) => sum + calcItemIva(item), 0)
})

const total = computed(() => {
  if (!Array.isArray(cart.value) || cart.value.length === 0) return 0
  return cart.value.reduce((sum, item) => sum + calcItemTotal(item), 0)
})

/** Total del carrito de una mesa (para mostrar en la tarjeta de la mesa). */
const getTableOrderTotal = (tableId) => {
  const items = tableCarts.value[tableId]
  if (!Array.isArray(items) || items.length === 0) return 0
  return items.reduce((sum, item) => sum + calcItemTotal(item), 0)
}

// Métodos
const goToDashboard = () => {
  router.push('/dashboard')
}

const formatPrice = (price) => {
  return Number(price).toFixed(2).replace('.', ',')
}

// Sistema de feedback visual para acciones del carrito
const showCartFeedback = (message, type = 'added') => {
  cartFeedback.value = { message, type }
  
  // Limpiar timeout anterior si existe
  if (cartFeedbackTimeout.value) {
    clearTimeout(cartFeedbackTimeout.value)
  }
  
  // Ocultar después de 2 segundos
  cartFeedbackTimeout.value = setTimeout(() => {
    cartFeedback.value = null
  }, 2000)
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

// Obtener emoji según icono predefinido
const getIconEmoji = (icon) => {
  const iconMap = {
    'coffee': '☕',
    'food': '🍽️',
    'service': '💼',
    'house': '🏠',
    'default': '📦'
  }
  return iconMap[icon] || '📦'
}

// Manejar error al cargar imagen
const handleImageError = (event) => {
  console.warn('⚠️ Error cargando imagen, usando icono por defecto')
  event.target.style.display = 'none'
}

// Función auxiliar para obtener token de forma robusta
const getAuthToken = async () => {
  // Intentar múltiples formas de obtener el token
  if (authStore.getToken) {
    const token = authStore.getToken()
    if (token) return token
  }
  
  if (authStore.token) {
    return authStore.token
  }
  
  // Intentar desde localStorage directamente (con verificación de disponibilidad)
  try {
    if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
      const storedToken = localStorage.getItem('auth_token')
      if (storedToken) {
        // Actualizar el store con el token encontrado
        if (authStore.setAuthTokens) {
          const refreshToken = localStorage.getItem('refresh_token') || ''
          authStore.setAuthTokens({
            access_token: storedToken,
            refresh_token: refreshToken,
            expires_in: 3600,
            token_type: 'Bearer'
          })
        }
        return storedToken
      }
    }
  } catch (e) {
    console.warn('⚠️ Error accediendo a localStorage:', e)
  }
  
  // Si no hay token, intentar inicializar el store
  if (!authStore.isAuthenticated) {
    try {
      await authStore.initialize()
      if (authStore.getToken) {
        const token = authStore.getToken()
        if (token) return token
      }
    } catch (err) {
      console.warn('⚠️ Error inicializando authStore:', err)
    }
  }
  
  return null
}

const checkStatus = async () => {
  loading.value = true
  errorMessage.value = null
  
  try {
    // Obtener token de forma robusta (ahora es async)
    let token = await getAuthToken()
    
    // Si aún no hay token, redirigir al login
    if (!token) {
      console.error('❌ No hay token de autenticación disponible')
      errorMessage.value = 'Sesión expirada. Por favor, inicia sesión nuevamente.'
      // Redirigir al login después de 2 segundos
      setTimeout(() => {
        router.push('/login?redirect=/tpv')
      }, 2000)
      return
    }
    
    // Verificar que el token no esté expirado
    try {
      const decoded = jwtDecode(token)
      const now = Math.floor(Date.now() / 1000)
      if (decoded.exp && decoded.exp < now) {
        console.warn('⚠️ Token expirado, intentando refresh...')
        const refreshed = await authStore.refreshAccessToken()
        if (refreshed) {
          token = await getAuthToken()
        } else {
          throw new Error('Token expirado y no se pudo refrescar')
        }
      }
    } catch (tokenError) {
      console.warn('⚠️ Error verificando token:', tokenError)
      // Continuar de todas formas, el backend validará
    }

    // Cargar información del usuario para permisos
    try {
      const userInfo = authStore.user || {}
      console.log('🔍 User info completo:', userInfo)
      
      // Intentar múltiples formas de obtener is_superuser
      isSuperuser.value = userInfo.is_superuser || 
                         userInfo.isSuperuser || 
                         authStore.isAdmin || 
                         false
      
      // Intentar múltiples formas de obtener role
      userRole.value = userInfo.role || 
                      userInfo.user_role ||
                      (isSuperuser.value ? 'SUPERUSER' : null) ||
                      'EMPLOYEE'
      
      console.log('👤 Permisos usuario:', { 
        isSuperuser: isSuperuser.value, 
        role: userRole.value,
        canEditProducts: canEditProducts.value,
        authStoreUser: authStore.user,
        authStoreIsAdmin: authStore.isAdmin
      })
      
      // Si no tenemos permisos claros, intentar obtenerlos del backend
      if (!isSuperuser.value && userRole.value !== 'ADMIN') {
        console.log('⚠️ Permisos no claros, verificando con backend...')
        try {
          const api = (await import('@/services/api')).default
          const userData = await api.get('/api/v1/user/me', token)
          console.log('👤 Datos del usuario desde backend:', userData)
          
          if (userData.is_superuser || userData.isSuperuser) {
            isSuperuser.value = true
            userRole.value = 'SUPERUSER'
          } else if (userData.role) {
            userRole.value = userData.role
          }
          
          console.log('✅ Permisos actualizados:', { 
            isSuperuser: isSuperuser.value, 
            role: userRole.value,
            canEditProducts: canEditProducts.value
          })
        } catch (err) {
          console.warn('⚠️ No se pudieron obtener permisos del backend:', err)
        }
      }
    } catch (err) {
      console.warn('⚠️ No se pudieron cargar permisos:', err)
    }
    
    // Cargar productos usando servicio API centralizado
    try {
      const api = (await import('@/services/api')).default
      const productsData = await api.get('/api/v1/tpv/products', token)
      
      if (productsData && productsData.success && productsData.products) {
        const loadedProducts = productsData.products || []
        products.value = loadedProducts
        console.log('✅ Productos cargados:', loadedProducts.length)
        console.log('📦 Lista de productos:', loadedProducts.map(p => p.name))
        
        // BLOCKING RULE: Validar que hay al menos 1 producto
        if (loadedProducts.length === 0) {
          console.warn('⚠️ No hay productos configurados. El TPV requiere al menos 1 producto activo.')
        }
      } else {
        console.error('❌ Error en respuesta de productos:', productsData)
        products.value = []
      }
    } catch (err) {
      // Manejar errores de API
      if (err.status === 401) {
        console.error('❌ Token expirado o inválido (401)')
        errorMessage.value = 'Sesión expirada. Por favor, inicia sesión nuevamente.'
        authStore.resetAuthState()
        setTimeout(() => {
          router.push('/login?redirect=/tpv')
        }, 2000)
        return
      }
      
      console.error('Error cargando productos:', err)
      errorMessage.value = err.message || 'Error al cargar productos. Verifica la conexión con el servidor.'
      products.value = []
    }
    
    // Cargar configuración del TPV
    await loadTPVConfig()
  } catch (err) {
    console.error('Error:', err)
    errorMessage.value = err.message || 'Error al cargar el TPV'
  } finally {
    loading.value = false
    businessProfileLoading.value = false
  }
}

const loadTPVConfig = async () => {
  try {
    const token = await getAuthToken()
    if (!token) {
      console.warn('⚠️ No hay token para cargar configuración TPV')
      // Intentar inicializar y obtener token nuevamente
      await authStore.initialize()
      const retryToken = await getAuthToken()
      if (!retryToken) {
        errorMessage.value = 'Sesión expirada. Redirigiendo al login...'
        setTimeout(() => {
          router.push('/login?redirect=/tpv')
        }, 2000)
        return
      }
      return
    }
    
    // Usar servicio API centralizado
    const api = (await import('@/services/api')).default
    const data = await api.get('/api/v1/tpv', token)
    
    businessProfile.value = data.business_profile
    tpvConfig.value = data.config || {}
    console.log('✅ Configuración TPV cargada:', businessProfile.value, tpvConfig.value)
    
    // Si no hay business_profile, mostrar configuración inicial
    if (!businessProfile.value) {
      errorMessage.value = 'Por favor, configura el tipo de negocio antes de usar el TPV'
    }
  } catch (err) {
    console.error('Error cargando configuración TPV:', err)
  }
}

const getBusinessProfileLabel = (profile) => {
  return t(`tpv.businessProfiles.${profile}`, profile)
}

// Validar cantidad según reglas (min: 1, max: 999)
const validateQuantity = (quantity) => {
  return Math.max(1, Math.min(999, quantity))
}

// Protección anti-doble IVA: normaliza cálculos por línea (neto + IVA) y evita sumar IVA dos veces.
const recalcCartItem = (item) => {
  if (!item) return

  const quantity = validateQuantity(item.quantity || 1)
  const ivaRate = getItemIvaRate(item)
  const discountPercent = safeNumber(item.discount_percent ?? 0)
  const discountMultiplier = 1 - Math.min(100, Math.max(0, discountPercent)) / 100

  // Unit price NETO (sin IVA). Fuente: item.unit_price -> product.price -> item.price (compat)
  let unitNet = safeNumber(item.unit_price ?? item.product?.price ?? item.price ?? 0)

  // Si solo tenemos precio con IVA, derivar neto (evita doble cálculo).
  const unitGrossFromProduct = safeNumber(item.product?.price_with_iva ?? item.price_with_iva ?? 0)
  if (!unitNet && unitGrossFromProduct && ivaRate >= 0) {
    unitNet = unitGrossFromProduct / (1 + ivaRate / 100)
  }

  const subtotalNet = unitNet * quantity * discountMultiplier
  const ivaAmount = subtotalNet * (ivaRate / 100)
  const totalGross = subtotalNet + ivaAmount
  const unitGross = quantity > 0 ? (totalGross / quantity) : 0

  // Guardar campos normalizados
  item.quantity = quantity
  item.unit_price = unitNet
  item.unit_price_with_iva = unitGross
  item.subtotal = subtotalNet
  item.iva_rate = ivaRate
  item.iva = ivaAmount
  item.subtotal_with_iva = totalGross
  item.total = totalGross
  item.internal_vat_calculated = true

  // Warning si detectamos una posible doble imposición (típico cuando unit_price ya venía con IVA)
  if (import.meta.env.DEV && unitGrossFromProduct && unitNet) {
    const expectedUnitGross = unitNet * (1 + ivaRate / 100)
    const delta = Math.abs(expectedUnitGross - unitGrossFromProduct)
    if (delta > 0.05 && !item._warned_vat_mismatch) {
      item._warned_vat_mismatch = true
      console.warn('[TPV] Posible desajuste IVA: el producto trae price_with_iva que no coincide con neto+IVA. Se usa neto+IVA como fuente de verdad.', {
        product_id: item.id || item.product?.id,
        unitNet,
        ivaRate,
        expectedUnitGross,
        productUnitGross: unitGrossFromProduct
      })
    }
  }
}

// REQUIRED FUNCTION: addProduct - push product into cart array
const addProductToCart = (product) => {
  // Validar producto
  if (!product || !product.id) {
    console.error('❌ Producto inválido:', product)
    return
  }
  
  // Asegurar que estamos en estado CART
  if (tpvState.value !== TPV_STATES.CART) {
    tpvState.value = TPV_STATES.CART
  }
  
  // Asegurar que cart es un array
  if (!Array.isArray(cart.value)) {
    cart.value = []
  }
  
  // Buscar si el producto ya existe en el carrito
  const existingItem = cart.value.find(item => {
    const itemProductId = item.product?.id || item.id
    return itemProductId === product.id
  })
  
  if (existingItem) {
    // Si existe, incrementar cantidad
    existingItem.quantity = validateQuantity(existingItem.quantity + 1)
    recalcCartItem(existingItem)
  } else {
    // Si no existe, crear nueva entrada en el array
    const ivaRate = safeNumber(product.iva_rate ?? tpvConfig.value?.default_iva_rate ?? 21)
    const unitNet = safeNumber(product.price ?? 0) || (safeNumber(product.price_with_iva ?? 0) / (1 + ivaRate / 100)) || 0
    const newItem = {
      id: product.id,
      name: product.name,
      unit_price: unitNet, // NETO (sin IVA)
      unit_price_with_iva: safeNumber(product.price_with_iva ?? (unitNet * (1 + ivaRate / 100))),
      iva_rate: ivaRate,
      discount_percent: 0,
      quantity: 1,
      subtotal: unitNet,
      subtotal_with_iva: safeNumber(product.price_with_iva ?? (unitNet * (1 + ivaRate / 100))),
      iva: 0,
      total: 0,
      product: product // Mantener referencia completa del producto
    }
    recalcCartItem(newItem)
    cart.value.push(newItem)
  }
  
  console.log('✅ Producto añadido. Carrito tiene', cart.value.length, 'items')
  showCartFeedback(product.name || 'Producto', 'added')
  saveCartToCurrentTable()
}

// REQUIRED FUNCTION: removeProduct - remove product by index or id
const removeFromCart = (index) => {
  // Asegurar que cart es un array
  if (!Array.isArray(cart.value)) {
    cart.value = []
    return
  }
  
  // Asegurar que estamos en estado CART
  if (tpvState.value !== TPV_STATES.CART) {
    tpvState.value = TPV_STATES.CART
  }
  
  if (index < 0 || index >= cart.value.length) {
    console.error('❌ Índice inválido:', index)
    return
  }
  
  const item = cart.value[index]
  if (!item) {
    console.error('❌ Item no encontrado en índice:', index)
    return
  }
  
  const itemName = item.name || item.product?.name || 'Producto'
  cart.value.splice(index, 1)
  
  console.log('✅ Producto eliminado. Carrito tiene', cart.value.length, 'items')
  showCartFeedback(`${itemName} eliminado`, 'removed')
  saveCartToCurrentTable()
}

// REQUIRED FUNCTION: updateQuantity - recalculate subtotal
const increaseQuantity = (index) => {
  // Asegurar que cart es un array
  if (!Array.isArray(cart.value)) {
    cart.value = []
    return
  }
  
  // Asegurar que estamos en estado CART
  if (tpvState.value !== TPV_STATES.CART) {
    tpvState.value = TPV_STATES.CART
  }
  
  if (index < 0 || index >= cart.value.length) {
    console.error('❌ Índice inválido:', index)
    return
  }
  
  const item = cart.value[index]
  if (!item) {
    console.error('❌ Item no encontrado en índice:', index)
    return
  }
  
  item.quantity = validateQuantity(item.quantity + 1)
  recalcCartItem(item)
  
  const itemName = item.name || item.product?.name || 'Producto'
  console.log('➕ Cantidad incrementada:', itemName, '→', item.quantity)
  showCartFeedback(`${itemName}: ${item.quantity} unidades`, 'updated')
  saveCartToCurrentTable()
}

// REQUIRED FUNCTION: updateQuantity - recalculate subtotal (decrease)
const decreaseQuantity = (index) => {
  // Asegurar que cart es un array
  if (!Array.isArray(cart.value)) {
    cart.value = []
    return
  }
  
  // Asegurar que estamos en estado CART
  if (tpvState.value !== TPV_STATES.CART) {
    tpvState.value = TPV_STATES.CART
  }
  
  if (index < 0 || index >= cart.value.length) {
    console.error('❌ Índice inválido:', index)
    return
  }
  
  const item = cart.value[index]
  if (!item) {
    console.error('❌ Item no encontrado en índice:', index)
    return
  }
  
  if (item.quantity > 1) {
    item.quantity--
    recalcCartItem(item)
    
    const itemName = item.name || item.product?.name || 'Producto'
    console.log('➖ Cantidad decrementada:', itemName, '→', item.quantity)
    showCartFeedback(`${itemName}: ${item.quantity} unidades`, 'updated')
    saveCartToCurrentTable()
  } else {
    // Si la cantidad llega a 1, eliminar del carrito
    removeFromCart(index)
  }
}

const clearCart = () => {
  // Solo permitir limpiar si estamos en estado CART
  if (tpvState.value !== TPV_STATES.CART) {
    return
  }
  
  if (cart.value.length === 0) {
    return
  }
  
  // Usar confirm nativo solo para confirmaciones críticas (limpiar carrito de esta mesa)
  if (window.confirm(`¿Estás seguro de limpiar el carrito de esta mesa? Se eliminarán ${cart.value.length} producto(s).`)) {
    cart.value = []
    if (selectedTable.value?.id != null) {
      tableCarts.value[selectedTable.value.id] = []
    }
    showCartFeedback('Carrito vaciado', 'cleared')
    success('Carrito vaciado correctamente')
  }
}

// Funciones para manejar estados del TPV
// BLOCKING RULE: No permitir pago si cart.length === 0
const goToPrePayment = () => {
  // Asegurar que cart es un array
  if (!Array.isArray(cart.value)) {
    cart.value = []
  }
  
  // BLOQUEAR si el carrito está vacío
  if (cart.value.length === 0) {
    warning('El carrito está vacío. Añade productos antes de proceder al pago.')
    return
  }
  
  if (tpvState.value === TPV_STATES.CART) {
    tpvState.value = TPV_STATES.PRE_PAYMENT
  }
}

const backToCart = () => {
  if (tpvState.value === TPV_STATES.PRE_PAYMENT) {
    tpvState.value = TPV_STATES.CART
  }
}

const startPayment = () => {
  if (tpvState.value === TPV_STATES.PRE_PAYMENT) {
    tpvState.value = TPV_STATES.PAYMENT
  }
}

const cancelPayment = () => {
  if (tpvState.value === TPV_STATES.PAYMENT) {
    tpvState.value = TPV_STATES.PRE_PAYMENT
  }
}

const resetTPV = () => {
  cart.value = []
  tpvState.value = TPV_STATES.CART
  paymentNote.value = ''
  selectedTable.value = null
  lastSaleTicketId.value = null
  cartFeedback.value = null
  activeCartIndex.value = -1
  quantityInputBuffer.value = ''
}

const setActiveCartIndex = (index) => {
  if (!Array.isArray(cart.value) || index < 0 || index >= cart.value.length) {
    activeCartIndex.value = -1
    quantityInputBuffer.value = ''
    return
  }
  activeCartIndex.value = index
  quantityInputBuffer.value = ''
}

const applyQuantityBufferToActiveItem = () => {
  if (!Array.isArray(cart.value) || cart.value.length === 0) return

  if (activeCartIndex.value < 0 || activeCartIndex.value >= cart.value.length) {
    activeCartIndex.value = cart.value.length - 1
  }

  const item = cart.value[activeCartIndex.value]
  if (!item) return

  const itemName = item.name || item.product?.name || 'Producto'
  const raw = quantityInputBuffer.value || '1'
  const parsed = parseInt(raw, 10)
  const quantity = validateQuantity(isNaN(parsed) ? 1 : parsed)

  item.quantity = quantity
  recalcCartItem(item)
  showCartFeedback(`${itemName}: ${item.quantity} unidades`, 'updated')
}

const handleKeyPress = (key) => {
  if (key === 'C') {
    // Limpiar solo el buffer numérico y restaurar cantidad a 1 en el ítem activo
    if (quantityInputBuffer.value) {
      quantityInputBuffer.value = ''
      applyQuantityBufferToActiveItem()
    }
  } else if (key === '⌫') {
    // Borrar último dígito del buffer; si queda vacío, volver a cantidad 1
    if (quantityInputBuffer.value) {
      quantityInputBuffer.value = quantityInputBuffer.value.slice(0, -1)
      applyQuantityBufferToActiveItem()
    } else if (cart.value.length > 0 && tpvState.value === TPV_STATES.CART) {
      // Si no hay buffer, mantener atajo para eliminar último producto
      const lastIndex = cart.value.length - 1
      removeFromCart(lastIndex)
    }
  } else if (key === '✓' || key === 'Enter') {
    // Procesar pago si estamos en estado adecuado
    if (tpvState.value === TPV_STATES.PAYMENT) {
      processPayment()
    } else if (tpvState.value === TPV_STATES.PRE_PAYMENT) {
      startPayment()
    } else if (tpvState.value === TPV_STATES.CART && cart.value.length > 0) {
      goToPrePayment()
    }
  } else if (!isNaN(parseInt(key))) {
    // Tecla numérica: edición profesional de cantidad sobre ítem activo
    if (!Array.isArray(cart.value) || cart.value.length === 0) {
      warning('Añade productos al carrito antes de usar el teclado numérico')
      return
    }

    // Si no hay ítem activo, usar el último del carrito
    if (activeCartIndex.value < 0 || activeCartIndex.value >= cart.value.length) {
      activeCartIndex.value = cart.value.length - 1
    }

    // Limitar cantidad a 3 dígitos (1-999)
    if (quantityInputBuffer.value.length >= 3) {
      return
    }

    quantityInputBuffer.value = `${quantityInputBuffer.value}${key}`
    applyQuantityBufferToActiveItem()
  }
}

const toggleTablesMode = () => {
  if (!tpvConfig.value.tables_enabled) {
    warning(t('tpv.messages.tablesNotAvailable') || 'Las mesas no están disponibles para este tipo de negocio')
    return
  }
  tablesMode.value = !tablesMode.value
}

/** Guarda el carrito actual en la mesa seleccionada (cada mesa es independiente). */
const saveCartToCurrentTable = () => {
  if (selectedTable.value?.id != null && Array.isArray(cart.value)) {
    tableCarts.value[selectedTable.value.id] = cart.value.map(item => ({ ...item }))
  }
}

const selectTable = (table) => {
  // Guardar carrito de la mesa actual antes de cambiar
  if (selectedTable.value?.id != null) {
    tableCarts.value[selectedTable.value.id] = [...(cart.value || [])]
  }
  selectedTable.value = table
  // Cargar el carrito de esta mesa (cada mesa es independiente)
  cart.value = [...(tableCarts.value[table.id] || [])]
  info(`Mesa ${table.number} – carrito independiente`)
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

const backToTablesList = () => {
  saveCartToCurrentTable()
  selectedTable.value = null
}

const copyComanderoLink = async () => {
  const url = `${window.location.origin}${import.meta.env.BASE_URL}tpv`.replace(/([^/])\/+$/g, '$1')
  try {
    await navigator.clipboard.writeText(url)
    success(t('tpv.comanderoLinkCopied') || 'Enlace del comandero copiado. Compártelo con tus empleados para que abran el TPV.')
  } catch {
    warning(t('tpv.comanderoLinkCopyFailed') || 'No se pudo copiar. Comparte manualmente: ' + url)
  }
}

const processPayment = async () => {
  // Solo procesar si estamos en estado PAYMENT
  if (tpvState.value !== TPV_STATES.PAYMENT) {
    return
  }
  
  if (cart.value.length === 0) {
    warning('El carrito está vacío')
    return
  }
  
  try {
    const token = await getAuthToken()
    if (!token) {
      console.error('❌ No hay token de autenticación')
      warning('Sesión expirada. Por favor, inicia sesión nuevamente.')
      router.push('/login?redirect=/tpv')
      return
    }
    
    // Validar según configuración
    let employeeId = null
    if (tpvConfig.value.requires_employee) {
      // En una implementación completa, esto pediría seleccionar empleado
      employeeId = prompt('ID del empleado (requerido para este tipo de negocio):')
      if (!employeeId) {
        warning('Debe especificar un empleado para procesar esta venta')
        return
      }
    }
    
    let customerData = null
    if (tpvConfig.value.requires_customer_data) {
      const customerName = prompt('Nombre del cliente (requerido):')
      if (!customerName) {
        warning('Debe especificar un cliente para procesar esta venta')
        return
      }
      customerData = { name: customerName }
    }
    
    // Preparar datos de la venta - Asegurar que cart es array
    if (!Array.isArray(cart.value) || cart.value.length === 0) {
      warning('El carrito está vacío')
      return
    }
    
    const saleData = {
      payment_method: 'efectivo', // Por defecto, se puede cambiar después
      employee_id: employeeId,
      customer_data: customerData,
      terminal_id: null,
      note: paymentNote.value || null, // Añadir nota si existe
      cart_items: cart.value.map(item => ({
        product_id: item.id || item.product?.id || 'UNKNOWN',
        quantity: item.quantity || 1,
        // Enviar SIEMPRE precio NETO (sin IVA). El backend calcula price_with_iva y totales.
        unit_price: item.unit_price ?? item.product?.price ?? item.price ?? 0,
        iva_rate: item.iva_rate ?? item.product?.iva_rate ?? 21.0
      }))
    }
    
    // Procesar pago en backend usando servicio API centralizado
    const api = (await import('@/services/api')).default
    const result = await api.post('/api/v1/tpv/sale', saleData, token)
    
    // Guardar ticket_id para facturación posterior
    const ticketId = result.ticket_id || result.ticket?.id || null
    lastSaleTicketId.value = ticketId
    
    // Cambiar estado a CLOSED después del pago exitoso
    tpvState.value = TPV_STATES.CLOSED
    // Vaciar carrito de esta mesa (cada mesa es independiente; la venta ya se cobró)
    if (selectedTable.value?.id != null) {
      tableCarts.value[selectedTable.value.id] = []
      cart.value = []
    }
    
    // Mostrar confirmación usando ticket_id del resultado
    const backendTotal = result?.ticket?.totals?.total ?? result?.totals?.total ?? null
    const totalToShow = backendTotal !== null ? backendTotal : total.value
    success(`Pago procesado exitosamente. Ticket #${ticketId || 'N/A'}. Total: EUR ${formatPrice(totalToShow)}. Esta venta se ha registrado automáticamente con RAFAEL.`)
    
    console.log('✅ Venta procesada exitosamente:', result)
  } catch (err) {
    console.error('Error procesando pago:', err)
    error('Error al procesar el pago: ' + err.message)
    // Volver al estado PRE_PAYMENT en caso de error
    tpvState.value = TPV_STATES.PRE_PAYMENT
  }
}

const generateInvoice = async () => {
  // En una implementación completa, esto generaría la factura
  info('Generando factura... (Funcionalidad en desarrollo)')
}

const printTicket = async () => {
  if (cart.value.length === 0) {
    warning('El carrito está vacío')
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
  `${item.name || item.product?.name || 'Producto'} x${item.quantity || 1} - €${formatPrice(item.total || item.subtotal_with_iva || 0)}`
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
    error('Error al generar el ticket: ' + err.message)
  }
}

const openDiscount = () => {
  if (cart.value.length === 0) {
    warning('El carrito está vacío')
    return
  }
  
  const discountPercent = prompt('Ingresa el descuento (%):', '0')
  if (!discountPercent || isNaN(discountPercent)) return
  
  const discount = parseFloat(discountPercent)
  if (discount < 0 || discount > 100) {
    warning('El descuento debe estar entre 0% y 100%')
    return
  }
  
  // Aplicar descuento al carrito
  cart.value.forEach(item => {
    item.discount_percent = discount
    recalcCartItem(item)
  })
  
  console.log(`✅ Descuento del ${discount}% aplicado`)
}

// REQUIRED FUNCTION: createProduct - push into products array
const openProducts = async () => {
  console.log('🔍 ===== openProducts INICIADO =====')
  console.log('🔍 Estado actual:', {
    canEditProducts: canEditProducts.value,
    isSuperuser: isSuperuser.value,
    userRole: userRole.value,
    authStoreUser: authStore.user,
    authStoreIsAdmin: authStore.isAdmin,
    businessProfileLoading: businessProfileLoading.value,
    showProductModal: showProductModal.value
  })
  
  try {
    // SIEMPRE permitir abrir el modal, la validación de permisos se hace al guardar
    console.log('✅ Abriendo modal (validación de permisos al guardar)')
    
    // Resetear estado
    editingProduct.value = null
    productForm.value = {
      name: '',
      price: 0,
      category: tpvConfig.value.default_categories?.[0] || 'General',
      iva_rate: tpvConfig.value.default_iva_rate || 21.0,
      stock: null,
      image: null,
      icon: null
    }
    imageFile.value = null
    imagePreview.value = null
    
    // Cerrar modal primero si está abierto (para forzar re-render)
    if (showProductModal.value) {
      showProductModal.value = false
      await nextTick()
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    
    // Abrir modal
    showProductModal.value = true
    
    // Forzar actualización del DOM
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))
    
    console.log('✅ Modal abierto, showProductModal:', showProductModal.value)
    console.log('✅ productForm:', productForm.value)
    
    // Verificar si el modal está realmente visible
    setTimeout(() => {
      const modal = document.querySelector('.modal-overlay')
      const modalContent = document.querySelector('.modal-content')
      
      if (modal) {
        const styles = window.getComputedStyle(modal)
        console.log('✅ Modal encontrado en DOM')
        console.log('✅ Modal display:', styles.display)
        console.log('✅ Modal visibility:', styles.visibility)
        console.log('✅ Modal opacity:', styles.opacity)
        console.log('✅ Modal z-index:', styles.zIndex)
        
        if (styles.display === 'none' || styles.visibility === 'hidden') {
          console.error('❌ Modal está oculto en CSS')
          // Forzar visibilidad
          modal.style.display = 'flex'
          modal.style.visibility = 'visible'
          modal.style.opacity = '1'
        }
      } else {
        console.error('❌ Modal NO encontrado en DOM')
        console.error('❌ showProductModal.value:', showProductModal.value)
      }
      
      if (modalContent) {
        console.log('✅ Modal content encontrado')
      } else {
        console.error('❌ Modal content NO encontrado')
      }
    }, 200)
    
    // Mostrar alerta de debug (temporal)
    console.log('🔔 Si no ves el modal, revisa la consola para más detalles')
    
  } catch (error) {
    console.error('❌ Error en openProducts:', error)
    error('Error al abrir el formulario: ' + error.message)
  }
}

// Manejar selección de imagen
const handleImageSelect = (event) => {
  const file = event.target.files[0]
  if (!file) return
  
  // Validar tamaño (max 2MB)
  if (file.size > 2 * 1024 * 1024) {
    warning('La imagen supera el límite de 2MB')
    return
  }
  
  // Validar tipo
  const allowedTypes = ['image/png', 'image/jpeg', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    warning('Formato no soportado. Usa PNG, JPEG o WEBP')
    return
  }
  
  imageFile.value = file
  
  // Crear preview
  const reader = new FileReader()
  reader.onload = (e) => {
    imagePreview.value = e.target.result
  }
  reader.readAsDataURL(file)
}

// Limpiar imagen
const clearImage = () => {
  imageFile.value = null
  imagePreview.value = null
  productForm.value.image = null
}

// REQUIRED FUNCTION: updateProduct - replace by id
const editProduct = (product) => {
  if (!canEditProducts.value) {
    warning('No tienes permisos para editar productos')
    return
  }
  
  editingProduct.value = product
  productForm.value = {
    name: product.name || '',
    price: product.price || 0,
    category: product.category || 'General',
    iva_rate: product.iva_rate || 21.0,
    stock: product.stock || null,
    image: product.image || null,
    icon: product.icon || null
  }
  imageFile.value = null
  imagePreview.value = product.image || null
  showProductModal.value = true
}

// REQUIRED FUNCTION: deleteProduct - filter by id
const deleteProduct = async (product) => {
  if (!isSuperuser.value) {
    warning('Solo los superusuarios pueden eliminar productos')
    return
  }
  
  if (!confirm(`¿Estás seguro de eliminar el producto "${product.name}"?\n\nEsta acción no se puede deshacer.`)) {
    return
  }
  
  try {
    const token = await getAuthToken()
    if (!token) {
      console.error('❌ No hay token de autenticación')
      warning('Sesión expirada. Por favor, inicia sesión nuevamente.')
      router.push('/login?redirect=/tpv')
      return
    }
    
    // Usar servicio API centralizado
    const api = (await import('@/services/api')).default
    const result = await api.delete(`/api/v1/tpv/products/${product.id}`, token)
    
    console.log('✅ Producto eliminado:', result)
    
    // STATE MANAGEMENT: filter by id (sin refresh)
    products.value = products.value.filter(p => p.id !== product.id)
    
    success(`Producto "${product.name}" eliminado correctamente`)
  } catch (err) {
    console.error('❌ Error eliminando producto:', err)
    error('Error al eliminar producto: ' + err.message)
  }
}

// Guardar producto (crear o actualizar)
const saveProduct = async () => {
  console.log('🔍 ===== saveProduct INICIADO =====')
  console.log('🔍 Estado:', {
    canEditProducts: canEditProducts.value,
    isSuperuser: isSuperuser.value,
    userRole: userRole.value,
    productForm: productForm.value
  })
  
  // Verificar permisos ANTES de validar el formulario
  if (!canEditProducts.value) {
    console.log('⚠️ Verificando permisos antes de guardar...')
    
    // Intentar verificar permisos una vez más
    try {
      const token = await getAuthToken()
      if (token) {
        const api = (await import('@/services/api')).default
        const userData = await api.get('/api/v1/user/me', token)
        console.log('👤 Verificación de permisos desde backend:', userData)
        
        if (userData.is_superuser || userData.isSuperuser) {
          isSuperuser.value = true
          userRole.value = 'SUPERUSER'
          console.log('✅ Permisos actualizados: SUPERUSER')
        } else if (userData.role === 'ADMIN') {
          userRole.value = 'ADMIN'
          console.log('✅ Permisos actualizados: ADMIN')
        }
      }
    } catch (err) {
      console.error('❌ Error verificando permisos:', err)
    }
    
    // Si aún no tiene permisos, mostrar mensaje
    if (!canEditProducts.value) {
      warning('No tienes permisos para crear productos. Se requiere rol ADMIN o SUPERUSER. Contacta con un administrador para obtener permisos.')
      console.error('❌ Permisos insuficientes:', {
        isSuperuser: isSuperuser.value,
        userRole: userRole.value,
        canEditProducts: canEditProducts.value
      })
      return
    }
  }
  
  if (!productForm.value.name || !productForm.value.name.trim()) {
    warning('El nombre del producto es requerido')
    return
  }
  
  if (!productForm.value.price || productForm.value.price <= 0) {
    warning('El precio debe ser mayor a 0')
    return
  }
  
  try {
    const token = await getAuthToken()
    if (!token) {
      console.error('❌ No hay token de autenticación')
      warning('Sesión expirada. Por favor, inicia sesión nuevamente.')
      router.push('/login?redirect=/tpv')
      return
    }
    
    // Subir imagen si hay un archivo seleccionado
    let imageUrl = productForm.value.image || null
    if (imageFile.value) {
      try {
        const formData = new FormData()
        formData.append('image', imageFile.value)
        
        const api = (await import('@/services/api')).default
        const uploadResult = await api.postFormData('/api/v1/tpv/products/upload-image', formData, token)
        imageUrl = uploadResult.url || uploadResult.image_url || uploadResult.public_url
        console.log('✅ Imagen subida:', imageUrl)
      } catch (uploadError) {
        // Si es 401, manejar autenticación
        if (uploadError?.status === 401) {
          console.error('❌ Token expirado (401) al subir imagen')
          authStore.resetAuthState()
          warning('Sesión expirada. Por favor, inicia sesión nuevamente.')
          router.push('/login?redirect=/tpv')
          return
        }
        console.warn('⚠️ Error al subir imagen:', uploadError)
        // Continuar sin imagen si falla la subida
      }
    }
    
    const isEditing = editingProduct.value !== null
    // Usar servicio API centralizado
    const api = (await import('@/services/api')).default
    const endpoint = isEditing 
      ? `/api/v1/tpv/products/${editingProduct.value.id}`
      : '/api/v1/tpv/products'
    
    const productData = {
      name: productForm.value.name.trim(),
      price: parseFloat(productForm.value.price),
      category: productForm.value.category || 'General',
      iva_rate: parseFloat(productForm.value.iva_rate) || 21.0,
      stock: productForm.value.stock ? parseInt(productForm.value.stock) : null,
      image: imageUrl,
      icon: productForm.value.icon || null
    }
    
    try {
      const result = isEditing
        ? await api.put(endpoint, productData, token)
        : await api.post(endpoint, productData, token)
      console.log('✅ Producto guardado:', result)
      
      const savedProduct = result.product || result
      
      if (isEditing) {
        // STATE MANAGEMENT: replace by id (sin refresh)
        const index = products.value.findIndex(p => p.id === savedProduct.id)
        if (index !== -1) {
          products.value[index] = savedProduct
        }
        success(`Producto "${savedProduct.name}" actualizado correctamente`)
      } else {
        // STATE MANAGEMENT: push into products (sin refresh)
        products.value.push(savedProduct)
        success(`Producto "${savedProduct.name}" creado correctamente`)
      }
      
      showProductModal.value = false
      editingProduct.value = null
      imageFile.value = null
      imagePreview.value = null
    } catch (err) {
      // Manejar errores de API
      if (err.status === 401) {
        console.error('❌ Token expirado (401) al guardar producto')
        authStore.resetAuthState()
        warning('Sesión expirada. Por favor, inicia sesión nuevamente.')
        router.push('/login?redirect=/tpv')
        return
      }
      
      console.error('❌ Error guardando producto:', err)
      const errorMsg = err.message || 'Error al guardar producto'
      error(errorMsg)
    }
  } catch (err) {
    console.error('❌ Error general guardando producto:', err)
    error('Error al guardar producto: ' + (err.message || 'Error desconocido'))
  }
}

// Cargar al montar
onMounted(async () => {
  // Asegurar que el estado inicial sea CART
  tpvState.value = TPV_STATES.CART
  console.log('🔄 TPV montado. Estado inicial:', tpvState.value)
  
  // Inicializar authStore para asegurar que el token esté disponible
  try {
    await authStore.initialize()
    console.log('✅ AuthStore inicializado')
    
    // Verificar autenticación
    if (!authStore.isAuthenticated) {
      console.warn('⚠️ Usuario no autenticado, redirigiendo al login')
      router.push('/login?redirect=/tpv')
      return
    }
  } catch (err) {
    console.error('❌ Error inicializando authStore:', err)
    router.push('/login?redirect=/tpv')
    return
  }
  
  // Cargar configuración primero
  await loadTPVConfig()
  // Luego cargar productos
  await checkStatus()
  
  // Log del estado final
  console.log('✅ TPV cargado:', {
    estado: tpvState.value,
    productos: products.value.length,
    carrito: cart.value.length,
    config: tpvConfig.value,
    autenticado: authStore.isAuthenticated
  })
})
</script>

<style scoped>
/* Pantalla completa real: fija al viewport, sin espacio blanco alrededor */
.tpv-container {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0f1419 0%, #1a1f2e 100%);
  color: #fff;
  padding: 12px;
  box-sizing: border-box;
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
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  margin: 52px 0 8px 0;
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

/* ZEUS_TPV_CART_ULTRA_MINIMAL_003: 4fr 1fr, terminal bancaria */
.tpv-main-interface {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 4fr minmax(0, 300px);
  gap: 6px;
  margin: 0;
  overflow: hidden;
}

/* Solo la zona de productos tiene scroll; carrito sin cambios */
.tpv-left-panel {
  min-height: 0;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 16px;
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
  border-radius: 8px;
  padding: 15px;
  transition: all 0.3s;
  text-align: center;
  user-select: none;
  position: relative;
  display: flex;
  flex-direction: column;
}

.product-clickable {
  cursor: pointer;
  flex: 1;
}

.product-card:hover {
  transform: translateY(-5px);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 8px 25px rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
}

.product-actions {
  display: flex;
  gap: 5px;
  justify-content: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.product-action-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.product-action-btn.edit-btn:hover {
  background: rgba(59, 130, 246, 0.4);
  transform: scale(1.1);
}

.product-action-btn.delete-btn:hover {
  background: rgba(239, 68, 68, 0.4);
  transform: scale(1.1);
}

.product-icon {
  font-size: 2rem; /* tamaño lógico similar a iconos del carrito */
  display: block;
  margin-bottom: 8px;
}

.product-image-file {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  margin-bottom: 8px;
}

.image-preview {
  margin-top: 10px;
  text-align: center;
}

.image-preview img {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  margin-bottom: 10px;
}

.btn-remove-image {
  background: rgba(239, 68, 68, 0.3);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #fca5a5;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-remove-image:hover {
  background: rgba(239, 68, 68, 0.5);
  transform: scale(1.05);
}

.product-image-file {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: 8px;
  margin-bottom: 10px;
}

.image-preview {
  margin-top: 10px;
  text-align: center;
}

.image-preview img {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  border: 2px solid rgba(59, 130, 246, 0.5);
  margin-bottom: 10px;
}

.btn-remove-image {
  padding: 6px 12px;
  background: rgba(239, 68, 68, 0.3);
  border: 1px solid rgba(239, 68, 68, 0.5);
  border-radius: 6px;
  color: #fca5a5;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-remove-image:hover {
  background: rgba(239, 68, 68, 0.5);
  transform: scale(1.05);
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

/* ZEUS_TPV_CART_ULTRA_MINIMAL_003: carrito máx 300px, gap 6px */
.tpv-right-panel {
  min-height: 0;
  min-width: 0;
  width: 100%;
  max-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
}

/* ZEUS_TPV_CART_ULTRA_MINIMAL_003: padding 10px, gap 6px, radius 8px */
.cart-panel {
  flex: 1;
  min-height: 0;
  max-height: 100%;
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 6px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

/* ZEUS_TPV_CART_ULTRA_MINIMAL_003: iconos máx 16px */
.tpv-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  line-height: 1;
}
.tpv-icon-ui,
.tpv-icon-primary {
  font-size: 16px;
}
.secondary-btn .tpv-icon {
  opacity: 0.9;
}
.action-btn .tpv-icon {
  font-size: 14px;
}

/* Bloques del carrito: ultra compactos, márgenes ≤8px */
.cart-block {
  flex-shrink: 0;
}
.cart-block + .cart-block {
  margin-top: 6px;
}
.cart-block-list {
  /* Listado siempre visible: prioridad de espacio y scroll solo aquí */
  flex: 1 1 0;
  min-height: 120px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.cart-block-summary,
.cart-block-actions {
  flex: 0 0 auto;
}
/* Teclado no crece: altura fija para que no robe espacio a la lista */
.cart-panel .numeric-keyboard {
  flex: 0 0 auto;
}

.cart-header {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.cart-header h2 {
  margin: 0;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.cart-count-badge {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 400;
}

.clear-cart-btn {
  padding: 4px 8px;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #fca5a5;
  cursor: pointer;
  font-size: 12px;
}

.cart-items {
  /* Listado visible de productos: scroll solo aquí si hay muchos ítems */
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  margin-bottom: 0;
  -webkit-overflow-scrolling: touch;
}

.cart-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  margin-bottom: 6px;
  flex-shrink: 0;
  min-height: 44px;
}

.cart-item--active {
  outline: 1px solid rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.25), rgba(16, 185, 129, 0.12));
}

.cart-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cart-item-name {
  display: block;
  font-weight: 600;
  margin-bottom: 2px;
  font-size: 13px;
  color: #fff;
  word-break: break-word;
  min-height: 1.2em;
}

.cart-item-price {
  color: #10b981;
  font-weight: 700;
}

.cart-item-unit-price {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 2px;
}

.cart-item.read-only {
  opacity: 0.8;
  background: rgba(255, 255, 255, 0.03);
}

.cart-item-readonly {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cart-item-qty-readonly {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.cart-item-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  white-space: nowrap;
}

.qty-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  background: rgba(59, 130, 246, 0.3);
  color: #fff;
  cursor: pointer;
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.qty-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.5);
  transform: scale(1.1);
}

.qty-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.increment-btn {
  background: rgba(16, 185, 129, 0.3);
}

.increment-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.5);
}

.decrement-btn {
  background: rgba(245, 158, 11, 0.3);
}

.decrement-btn:hover:not(:disabled) {
  background: rgba(245, 158, 11, 0.5);
}

.cart-item-qty {
  min-width: 30px;
  text-align: center;
  font-weight: 600;
}

.remove-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  background: rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  cursor: pointer;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.remove-btn:hover {
  background: rgba(239, 68, 68, 0.5);
  transform: scale(1.1);
}

.empty-cart {
  text-align: center;
  padding: 12px 8px;
  color: rgba(255, 255, 255, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.empty-cart-icon {
  font-size: 1.75rem;
  margin-bottom: 6px;
  opacity: 0.6;
}

.empty-cart-message {
  font-size: 0.9rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
}

.empty-cart-hint {
  font-size: 0.8rem;
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.4);
}

.cart-totals {
  flex: 0 0 auto;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 6px;
  margin-bottom: 0;
}

.total-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
  color: rgba(255, 255, 255, 0.75);
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
}

.total-final {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  border-top: 2px solid rgba(255, 255, 255, 0.2);
  padding-top: 4px;
  margin-top: 4px;
  margin-bottom: 0;
}

/* Botonera/teclado numérico: altura fija para que no se rompa el layout */
.numeric-keyboard {
  flex: 0 0 auto;
  display: grid;
  grid-template-rows: repeat(4, 32px);
  gap: 4px;
  margin-bottom: 0;
  height: calc(4 * 32px + 3 * 4px); /* 4 filas + 3 gaps */
  min-height: 140px;
  max-height: 140px;
}

.keyboard-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  min-height: 32px;
}

.keyboard-key {
  min-height: 28px;
  height: 100%;
  min-width: 0;
  padding: 2px 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.keyboard-key:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
}

.keyboard-key:active {
  background: rgba(59, 130, 246, 0.4);
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2);
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
  gap: 4px;
}

.action-btn {
  width: 100%;
  padding: 4px 8px;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ZEUS_TPV_CART_ULTRA_MINIMAL_003: principal 38px, 14px */
.pay-btn {
  height: 38px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35);
}

.pay-btn:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.5);
  filter: brightness(1.05);
}

.secondary-btn {
  height: 30px;
  background: rgba(59, 130, 246, 0.25);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: rgba(255, 255, 255, 0.95);
  font-size: 12px;
}

.secondary-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.4);
  border-color: rgba(59, 130, 246, 0.6);
}

.payment-note-section {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.payment-note-section label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.payment-note-input {
  width: 100%;
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #fff;
  font-family: inherit;
  font-size: 0.9rem;
  resize: vertical;
  min-height: 60px;
}

.payment-note-input:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.payment-note-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* Barra "Mesa X" cuando hay mesa seleccionada para anotar */
.tables-selected-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
}
.back-to-tables-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 0.9rem;
}
.back-to-tables-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}
.tables-selected-label {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
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

/* Tarjeta para añadir producto (visible siempre si tiene permisos) */
.add-product-card {
  min-height: 200px;
  border: 2px dashed rgba(59, 130, 246, 0.5);
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.1);
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  margin-bottom: 20px;
}

.add-product-card:hover:not(.disabled) {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.8);
  transform: scale(1.02);
}

.add-product-card.disabled,
.add-product-card:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  pointer-events: none;
}

.add-product-card:disabled:hover {
  transform: none;
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
}

.add-product-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.add-product-icon {
  font-size: 2.2rem;
  opacity: 0.85;
}

.add-product-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(59, 130, 246, 0.9);
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

/* Responsive: 1366x768 y 1920x1080 sin scroll (layout base). Tablet/móvil: columna única */
@media (max-width: 1024px) {
  .tpv-container {
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .tpv-main-interface {
    grid-template-columns: 1fr;
    flex: none;
    height: auto;
    min-height: 400px;
  }

  .tpv-right-panel {
    order: -1;
    min-height: 0;
  }
}

/* Pantalla baja: teclado mantiene altura fija, botones de pago más compactos */
@media (max-height: 800px) {
  .numeric-keyboard {
    grid-template-rows: repeat(4, 28px);
    height: calc(4 * 28px + 3 * 4px);
    min-height: 124px;
    max-height: 124px;
  }

  .keyboard-row {
    min-height: 28px;
  }

  .keyboard-key {
    font-size: 13px;
  }

  .pay-btn {
    height: 48px;
    font-size: 16px;
  }

  .secondary-btn {
    height: 40px;
  }
}

@media (max-width: 768px) {
  .tpv-container {
    padding: 10px;
  }

  .back-to-dashboard-btn.fixed-top-left {
    top: 10px;
    left: 10px;
    padding: 10px 16px;
    font-size: 14px;
  }

  .back-to-dashboard-btn .btn-label {
    display: none;
  }

  .tpv-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
    padding: 15px 20px;
    margin: 60px 10px 15px 10px;
  }

  .tpv-title {
    font-size: 1.5rem;
  }

  .tpv-subtitle {
    font-size: 0.9rem;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
    gap: 8px;
  }

  .header-btn {
    padding: 8px 16px;
    font-size: 14px;
    flex: 1;
    min-width: calc(50% - 4px);
  }

  .business-profile-badge {
    width: 100%;
    text-align: center;
    padding: 8px;
    font-size: 0.85rem;
  }

  .tpv-main-interface {
    margin: 10px;
    gap: 15px;
  }

  .tpv-left-panel,
  .tpv-right-panel {
    padding: 15px;
  }

  .products-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
  }

  .categories-bar {
    gap: 8px;
    margin-bottom: 15px;
  }

  .category-btn {
    padding: 8px 16px;
    font-size: 14px;
  }

  .product-card {
    padding: 12px;
  }

  .product-name {
    font-size: 1rem;
  }

  .product-price {
    font-size: 1.1rem;
  }

  .cart-item {
    padding: 12px;
  }

  .cart-summary {
    padding: 15px;
  }

  .cart-total {
    font-size: 1.3rem;
  }
}

@media (max-width: 480px) {
  .tpv-container {
    padding: 8px;
  }

  .back-to-dashboard-btn.fixed-top-left {
    top: 8px;
    left: 8px;
    padding: 8px 12px;
  }

  .tpv-header {
    margin: 50px 8px 12px 8px;
    padding: 12px 15px;
  }

  .tpv-title {
    font-size: 1.3rem;
  }

  .header-btn {
    padding: 8px 12px;
    font-size: 13px;
    min-width: 100%;
  }

  .tpv-main-interface {
    margin: 8px;
    gap: 12px;
  }

  .products-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 10px;
  }

  .product-card {
    padding: 10px;
  }

  .product-image {
    height: 80px;
  }

  .product-name {
    font-size: 0.9rem;
  }

  .category-btn {
    padding: 6px 12px;
    font-size: 13px;
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

/* Modal de Producto */
.modal-overlay {
  position: fixed !important;
  inset: 0 !important;
  background: rgba(0, 0, 0, 0.8) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 99999 !important;
  animation: fadeIn 0.2s;
  visibility: visible !important;
  opacity: 1 !important;
}

.modal-content {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 15px;
  padding: 0;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  animation: slideUp 0.3s;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #fff;
}

.modal-close {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  color: #fff;
  cursor: pointer;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.modal-close:hover {
  background: rgba(239, 68, 68, 0.4);
  transform: scale(1.1);
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
  font-size: 0.9rem;
}

.form-input {
  width: 100%;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 1rem;
  transition: all 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.modal-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-cancel {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-cancel:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn-save {
  padding: 12px 24px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
}

.btn-save:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Feedback visual del carrito */
.cart-feedback {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 15px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #10b981;
  font-weight: 600;
  animation: slideIn 0.3s ease-out;
}

.cart-feedback.removed {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

.cart-feedback.cleared {
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(245, 158, 11, 0.4);
  color: #f59e0b;
}

.cart-feedback.updated {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.4);
  color: #3b82f6;
}

.feedback-icon {
  font-size: 18px;
  vertical-align: middle;
}

.feedback-message {
  flex: 1;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
