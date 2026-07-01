<template>
  <component v-if="Component" :is="Component" :data="normalized" />
  <div v-else class="doc-error">Tipo de documento no soportado para vista previa.</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ContractDocument from './ContractDocument.vue'
import InvoiceDocument from './InvoiceDocument.vue'
import LegalDocument from './LegalDocument.vue'
import { normalizeZeusDocument } from '@/utils/normalizeZeusDocument'

const props = defineProps<{ doc: unknown }>()

const normalized = computed(() => normalizeZeusDocument(props.doc))

const Component = computed(() => {
  const src = normalized.value?.agent_source?.toUpperCase()
  if (src === 'AFRODITA') return ContractDocument
  if (src === 'RAFAEL') return InvoiceDocument
  if (src === 'JUSTICIA') return LegalDocument
  return null
})
</script>
