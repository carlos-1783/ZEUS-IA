<template>
  <div class="doc contract">
    <h2>Contrato laboral</h2>
    <div class="section">
      <p><strong>Empleado:</strong> {{ employeeName }}</p>
      <p><strong>Puesto:</strong> {{ position }}</p>
      <p v-if="salary > 0"><strong>Salario ref.:</strong> {{ salary }}€</p>
      <p v-if="contractId"><strong>ID:</strong> {{ contractId }}</p>
    </div>
    <pre v-if="preview" class="markdown-preview">{{ preview }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ZeusDocument } from '@/utils/normalizeZeusDocument'

const props = defineProps<{ data: ZeusDocument }>()

const block = computed(() => props.data.data || {})
const employeeName = computed(() => String(block.value.employee || '—'))
const position = computed(() => String(block.value.position || '—'))
const salary = computed(() => Number(block.value.salary) || 0)
const contractId = computed(() =>
  block.value.contract_id ? String(block.value.contract_id) : '',
)
const preview = computed(() =>
  block.value.content_preview ? String(block.value.content_preview) : '',
)
</script>
