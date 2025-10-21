console.log('🚀 TEST MÍNIMO - Iniciando Vue...');

import { createApp } from 'vue';

// Componente mínimo
const MinimalApp = {
  template: `
    <div id="minimal-app">
      <h1>TEST MÍNIMO FUNCIONANDO</h1>
      <p>Si ves esto, Vue está montado correctamente</p>
      <button @click="testClick">Hacer clic aquí</button>
      <p v-if="clicked">¡Vue está funcionando!</p>
    </div>
  `,
  data() {
    return {
      clicked: false
    }
  },
  methods: {
    testClick() {
      this.clicked = true;
      console.log('✅ Vue está funcionando correctamente');
    }
  }
};

// Montar aplicación mínima
try {
  console.log('🔧 Creando aplicación mínima...');
  const app = createApp(MinimalApp);
  
  console.log('⚡ Montando aplicación mínima...');
  app.mount('#app');
  
  console.log('✅ Aplicación mínima montada correctamente');
} catch (error) {
  console.error('❌ Error al montar aplicación mínima:', error);
}
