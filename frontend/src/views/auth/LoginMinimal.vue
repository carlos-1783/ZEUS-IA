<template>
  <div style="padding: 20px; max-width: 400px; margin: 0 auto;">
    <h1>ZEUS-IA Login</h1>
    
    <form @submit.prevent="handleLogin">
      <div style="margin-bottom: 15px;">
        <label>Email:</label><br>
        <input 
          v-model="email" 
          type="email" 
          required 
          style="width: 100%; padding: 8px; margin-top: 5px;"
        >
      </div>
      
      <div style="margin-bottom: 15px;">
        <label>Password:</label><br>
        <input 
          v-model="password" 
          type="password" 
          required 
          style="width: 100%; padding: 8px; margin-top: 5px;"
        >
      </div>
      
      <button 
        type="submit" 
        style="width: 100%; padding: 10px; background: #007bff; color: white; border: none; cursor: pointer;"
      >
        Login
      </button>
    </form>
    
    <div v-if="message" style="margin-top: 15px; padding: 10px; background: #f0f0f0;">
      {{ message }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoginMinimal',
  data() {
    return {
      email: '',
      password: '',
      message: ''
    }
  },
  methods: {
    handleLogin() {
      this.message = `Login attempt: ${this.email} / ${this.password}`;
      console.log('Login attempt:', this.email, this.password);
      alert('Login funcionando! Email: ' + this.email);
    }
  }
}
</script>
