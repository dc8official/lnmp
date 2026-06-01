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
      role: response.data.role,
      must_change_password: response.data.must_change_password
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
  background-color: #0A0A0A;
  padding: 1rem;
}
.glass-container {
  width: 100%;
  max-width: 440px;
  background-color: #000000;
  border-radius: 8px;
  border: 1px solid #262626;
  box-shadow: none;
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
  font-size: 2rem;
  color: #FFFFFF;
  background-color: #0A0A0A;
  border: 1px solid #262626;
  padding: 0.85rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}
h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: #FFFFFF;
  margin-bottom: 0.25rem;
  letter-spacing: -0.02em;
}
.brand-subtitle {
  color: #A3A3A3;
  font-size: 0.85rem;
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
  font-size: 0.8rem;
  font-weight: 600;
  color: #A3A3A3;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.input-with-icon {
  position: relative;
  display: flex;
  align-items: center;
}
.field-icon {
  position: absolute;
  left: 0.75rem;
  color: #A3A3A3;
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
:deep(.p-inputtext) {
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  color: #FFFFFF !important;
  border-radius: 4px !important;
}
:deep(.p-inputtext:focus) {
  border-color: #A3A3A3 !important;
}
.submit-button {
  background-color: #FFFFFF !important;
  border-color: #FFFFFF !important;
  color: #000000 !important;
  padding: 0.75rem !important;
  font-size: 0.9rem !important;
  font-weight: 700 !important;
  margin-top: 1rem;
  width: 100%;
  border-radius: 4px !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}
.submit-button:hover {
  background-color: #A3A3A3 !important;
  border-color: #A3A3A3 !important;
}

/* Light Mode Overrides */
:global(html:not(.dark)) .login-wrapper {
  background-color: #f1f5f9;
}
:global(html:not(.dark)) .glass-container {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
}
:global(html:not(.dark)) .brand-icon {
  color: #0f172a;
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
}
:global(html:not(.dark)) h2 {
  color: #0f172a;
}
:global(html:not(.dark)) .brand-subtitle {
  color: #475569;
}
:global(html:not(.dark)) label {
  color: #475569;
}
:global(html:not(.dark)) .field-icon {
  color: #64748b;
}
:global(html:not(.dark)) :deep(.p-inputtext) {
  background-color: #ffffff !important;
  border: 1px solid #cbd5e1 !important;
  color: #0f172a !important;
}
:global(html:not(.dark)) :deep(.p-inputtext:focus) {
  border-color: #049f6c !important;
}
:global(html:not(.dark)) .submit-button {
  background-color: #0f172a !important;
  border-color: #0f172a !important;
  color: #ffffff !important;
}
:global(html:not(.dark)) .submit-button:hover {
  background-color: #334155 !important;
  border-color: #334155 !important;
}
</style>
