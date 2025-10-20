// Debug version of main.js - simplified
console.log('🚀 Starting main-debug.js...');

(async () => {
  try {
    console.log('📦 Importing Vue...');
    const { createApp } = await import('vue');
    console.log('✅ Vue imported successfully');
    
    console.log('📦 Importing App...');
    const App = (await import('./App.vue')).default;
    console.log('✅ App imported successfully');
    
    console.log('📦 Creating app...');
    const app = createApp(App);
    console.log('✅ App created successfully');
    
    console.log('📦 Mounting app...');
    app.mount('#app');
    console.log('✅ App mounted successfully');
    
  } catch (error) {
    console.error('❌ Error in main-debug.js:', error);
    console.error('Stack:', error.stack);
  }
})();
