<template>
  <div style="min-height: 100vh; background: #f0f0f0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px;">
      <h1 style="text-align: center; color: #333; margin-bottom: 20px;">
        ZEUS-IA - {{ pageTitle }}
      </h1>
      
      <!-- SLOT CONTENT -->
      <div style="border: 2px dashed #007bff; padding: 20px; margin: 20px 0;">
        <h3 style="color: #007bff; margin-bottom: 10px;">CONTENIDO DEL SLOT:</h3>
        <slot></slot>
      </div>
      
      <div style="text-align: center; color: #666; font-size: 12px;">
        © 2025 ZEUS-IA. Todos los derechos reservados.
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const pageTitle = computed(() => {
  return route.meta.title || 'Bienvenido a ZEUS-IA';
});
</script>
