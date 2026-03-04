# ROCE ZEUS_TPV_LAYOUT_AND_VAT_FIX_001 — Cierre

## Objetivo
Optimizar el TPV: eliminar scroll innecesario en 1366x768 y corregir el cálculo duplicado del IVA sin afectar otros módulos.

---

## Paso 1 — FIX_VAT_CALCULATION

### Análisis
- **Backend** (`tpv_service.py`, `tpv.py`): Los productos tienen `price` (neto) y `price_with_iva` (bruto). El carrito del servicio usa `subtotal = price * quantity` y `subtotal_with_iva = price_with_iva * quantity`; IVA = `subtotal_with_iva - subtotal`. Una sola fuente de verdad: neto + IVA por línea.
- **Frontend (antes)**: En el carrito se guardaba `price` como `price_with_iva` y `subtotal = price * quantity` (bruto). Luego `ivaTotal` sumaba otra vez `price * quantity * ivaRate/100` → **doble IVA**.

### Cambios
- **Precio en carrito**: Se guarda `unit_price` (neto) y `unit_price_with_iva` (bruto). Si el producto solo trae `price_with_iva`, se deriva neto = `price_with_iva / (1 + iva_rate/100)`.
- **Totales**: `subtotal` = suma de base imponible por línea, `ivaTotal` = suma de IVA por línea, `total` = suma de total con IVA por línea. Se usan helpers `calcItemSubtotalNet`, `calcItemIva`, `calcItemTotal` que respetan `item.subtotal`, `item.iva`, `item.subtotal_with_iva` si vienen del backend (no se recalcula encima).

### Lógica aplicada
- **Precio sin IVA**: `subtotal_net = unit_net * quantity`; `iva = subtotal_net * (iva_rate/100)`; `total = subtotal_net + iva`.
- **Precio con IVA (solo para derivar neto)**: `unit_net = price_with_iva / (1 + iva_rate/100)`; luego igual que arriba.

---

## Paso 2 — ADD_VAT_PROTECTION_LAYER

- **Flag**: En `recalcCartItem` se asigna `item.internal_vat_calculated = true` tras recalcular neto, IVA y total por línea.
- **Backend como fuente**: Si el item tiene `subtotal`, `iva` o `subtotal_with_iva` definidos, los computed los usan y no vuelven a calcular IVA encima.
- **Warning en desarrollo**: Si el producto trae `price_with_iva` y el neto derivado no coincide con `neto * (1+iva/100)` (delta > 0.05), se muestra `console.warn` de posible desajuste (solo una vez por item con `_warned_vat_mismatch`).

---

## Paso 3 — OPTIMIZE_TPV_LAYOUT

- **Contenedor**: `.tpv-container` → `height: 100vh`, `overflow: hidden`, `display: flex`, `flex-direction: column`, `padding: 12px`.
- **Header**: Menos margen y padding (`margin: 52px 0 8px 0`, `padding: 12px 16px`) para ganar espacio.
- **Área principal**: `.tpv-main-interface` → `flex: 1`, `min-height: 0`, `grid-template-columns: 2fr 1fr`, `gap: 12px`, `overflow: hidden`.
- **Panel izquierdo (productos)**: `min-height: 0`, `overflow-y: auto` → solo esta zona hace scroll.
- **Panel derecho (carrito)**: `min-height: 0`, `overflow: hidden`, `.cart-panel` con `flex: 1`, `min-height: 0`, `overflow: hidden`; `.cart-items` con `flex: 1`, `min-height: 0`, `overflow-y: auto` para scroll interno del listado.
- **Totales, teclado, botones**: `flex-shrink: 0` y márgenes/paddings reducidos para que quepan en 1366x768.

### Responsive
- **≤1024px**: Layout en una columna, carrito arriba; contenedor `height: auto`, `min-height: 100vh`, `overflow: auto` (se permite scroll en móvil/tablet).
- **max-height ≤800px**: Teclado y botones de acción más compactos.

---

## Paso 4 — RESPONSIVE_TESTING

- **1366x768 / 1920x1080**: Sin scroll vertical en el viewport; scroll solo dentro del listado de productos y, si hace falta, dentro del listado del carrito.
- **Tablet / móvil**: Una columna, scroll de página permitido.

---

## Paso 5 — REGRESSION

- **Ventas**: `processPayment` envía `unit_price` (neto) y `iva_rate`; el backend sigue con la misma lógica (`tpv_service.process_sale`, `get_cart_total`).
- **IVA en BD**: Sin cambios de modelo; el backend ya calcula IVA a partir de neto por línea.
- **Totales**: Tras la venta se muestra el total del backend si viene en `result.ticket.totals.total` o `result.totals.total`, si no el `total` del frontend (ya coherente con neto+IVA único).
- **Ticket**: `printTicket` usa `item.total ?? item.subtotal_with_iva`, `subtotal.value`, `ivaTotal.value`, `total.value` (ya sin doble IVA).

---

## Archivos modificados

- `frontend/src/views/TPV.vue`
  - Computed: `safeNumber`, `getItemIvaRate`, `calcItemSubtotalNet`, `calcItemIva`, `calcItemTotal`; `subtotal`, `ivaTotal`, `total` basados en ellos.
  - `recalcCartItem`: normalización neto/IVA por línea, `internal_vat_calculated`, warning en dev.
  - `addProductToCart`, `increaseQuantity`, `decreaseQuantity`, `openDiscount`: usan `recalcCartItem` y precios netos.
  - `processPayment`: envía `unit_price` (neto), usa total del backend si existe.
  - Template: precio línea carrito con `item.total ?? item.subtotal_with_iva ?? item.subtotal`.
  - Estilos: layout 100vh, grid 2fr 1fr, scroll interno, responsive y compactación.

---

## Criterios de aceptancia

- No hay doble suma de IVA (una sola vez por línea).
- Total coincide con cálculo backend cuando se usa respuesta de venta.
- TPV completo visible sin scroll principal en 1366x768.
- Carrito siempre visible; scroll solo en listados.
- Ventas anteriores y flujo de venta/impresión de ticket intactos.

**Estado final:** `TPV_OPTIMIZED_AND_VAT_FIXED`
