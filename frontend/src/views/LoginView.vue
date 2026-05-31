<template>
  <div class="login-wrapper">
    <div class="glass-container">
      <Card class="login-card">
        <template #title>
          <div class="brand-header">
            <i class="pi pi-shield brand-icon"></i>
            <h2>lnmp Platform</h2>
            <p class="brand-subtitle">Network Uptime Monitoring</p>
          </div>
        </template>
        <template #content>
          <form @submit.prevent="handleLogin" class="login-form">
            <div v-if="error" class="error-container">
              <Message severity="error" :closable="false">{{ error }}</Message>
            </div>

            <div class="form-group">
              <label for="username">Username</label>
              <div class="input-with-icon">
                <i class="pi pi-user field-icon"></i>
                <InputText 
                  id="username" 
                  v-model="username" 
                  placeholder="Enter your username" 
                  required 
                  class="full-width"
                  :disabled="loading"
                />
              </div>
            </div>

            <div class="form-group">
              <label for="password">Password</label>
              <div class="input-with-icon">
                <i class="pi pi-lock field-icon"></i>
                <Password 
                  id="password" 
                  v-model="password" 
                  placeholder="Enter your password" 
                  required 
                  :feedback="false"
                  toggleMask
                  class="full-width-password"
                  inputClass="full-width"
                  :disabled="loading"
                />
              </div>
            </div>

            <Button 
              type="submit" 
              label="Sign In" 
              icon="pi pi-sign-in" 
              :loading="loading" 
              class="submit-button"
            />
          </form>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/api.js'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref(null)

const handleLogin = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await login(username.value, password.value)
    // Save user info (username and role) locally
    localStorage.setItem('user', JSON.stringify({
      username: response.data.username,
      role: response.data.role
    }))
    router.push('/')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Invalid username or password. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 10% 20%, rgb(4, 159, 108) 0%, rgb(194, 254, 113) 90.1%);
  padding: 1rem;
}
.glass-container {
  width: 100%;
  max-width: 440px;
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  background-color: rgba(255, 255, 255, 0.75);
  border-radius: 16px;
  border: 1px solid rgba(209, 213, 219, 0.3);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
}
.login-card {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 1.5rem 1rem;
}
.brand-header {
  text-align: center;
  margin-bottom: 2rem;
}
.brand-icon {
  font-size: 2.5rem;
  color: #049f6c;
  background-color: rgba(4, 159, 108, 0.1);
  padding: 1rem;
  border-radius: 50%;
  margin-bottom: 1rem;
}
h2 {
  font-size: 1.6rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.25rem;
}
.brand-subtitle {
  color: #64748b;
  font-size: 0.9rem;
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.error-container {
  margin-bottom: 0.5rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #334155;
}
.input-with-icon {
  position: relative;
  display: flex;
  align-items: center;
}
.field-icon {
  position: absolute;
  left: 0.75rem;
  color: #94a3b8;
  z-index: 10;
  pointer-events: none;
}
.full-width {
  width: 100%;
  padding-left: 2.25rem !important;
}
.full-width-password {
  width: 100%;
}
:deep(.full-width-password input) {
  width: 100%;
  padding-left: 2.25rem !important;
}
.submit-button {
  background-color: #049f6c !important;
  border-color: #049f6c !important;
  padding: 0.75rem !important;
  font-size: 1rem !important;
  font-weight: 600 !important;
  margin-top: 1rem;
  width: 100%;
}
.submit-button:hover {
  background-color: #038459 !important;
  border-color: #038459 !important;
}
</style>
