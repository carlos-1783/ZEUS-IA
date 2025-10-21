<template>
  <div style="background: red; color: white; padding: 20px; border: 5px solid yellow;">
    <h1>🚨 TEST COMPONENTE FUNCIONANDO 🚨</h1>
    <p>Si ves esto, el componente se está renderizando</p>
    <button @click="testClick" style="background: blue; color: white; padding: 10px;">
      HACER CLIC AQUÍ
    </button>
    <p v-if="clicked" style="color: green; font-weight: bold;">
      ✅ VUE ESTÁ FUNCIONANDO CORRECTAMENTE
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const clicked = ref(false);

const testClick = () => {
  clicked.value = true;
  console.log('✅ Test component clicked - Vue is working!');
};
</script>
