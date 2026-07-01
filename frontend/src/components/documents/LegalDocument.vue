<template>
  <div class="doc legal">
    <h2>{{ title }}</h2>
    <pre class="markdown-preview">{{ body }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ZeusDocument } from '@/utils/normalizeZeusDocument'

const props = defineProps<{ data: ZeusDocument }>()

const title = computed(() => props.data.title || 'Documento legal')

const body = computed(() => {
  const c = props.data.content
  if (typeof c === 'string') return c
  if (c && typeof c === 'object') {
    const row = c as Record<string, unknown>
    if (typeof row.body === 'string') return row.body
  }
  if (props.data.data) {
    const d = props.data.data
    if (typeof d.content === 'string') return d.content
    if (typeof d.content_preview === 'string') return d.content_preview
  }
  return c ? JSON.stringify(c, null, 2) : 'Sin contenido'
})
</script>
