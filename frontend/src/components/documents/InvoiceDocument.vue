<template>
  <div class="doc invoice">
    <h2>Factura</h2>
    <p><strong>Cliente:</strong> {{ client }}</p>
    <ul v-if="items.length">
      <li v-for="(item, idx) in items" :key="idx">
        {{ item.description }} — {{ formatPrice(item.price) }}
      </li>
    </ul>
    <p v-else class="section">Sin líneas detalladas.</p>
    <h3>Total: {{ formatPrice(total) }}</h3>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ZeusDocument } from '@/utils/normalizeZeusDocument'

const props = defineProps<{ data: ZeusDocument }>()

const client = computed(() => props.data.client || 'Cliente')
const items = computed(() => props.data.items || [])
const total = computed(() => {
  if (props.data.total != null && props.data.total > 0) return props.data.total
  return items.value.reduce((s, i) => s + (Number(i.price) || 0), 0)
})

const formatPrice = (v: number) => `${Number(v || 0).toFixed(2)}€`
</script>
