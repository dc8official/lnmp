<template>
  <div class="login-wrapper">
    <div class="glass-container">
      <Card class="login-card">
        <template #title>
          <div class="brand-header">
            <h2>lnmp Platform</h2>
            <p class="brand-subtitle">Network Uptime Monitoring v2.0(beta)</p>
          </div>
        </template>
        <template #content>
          <form @submit.prevent="handleLogin" method="post" action="" autocomplete="on" class="login-form">
            <div v-if="error" class="error-container">
              <Message severity="error" :closable="false">{{ error }}</Message>
            </div>

            <div class="form-group">
              <label for="username">Username</label>
              <div class="input-with-icon">
                <i class="pi pi-user field-icon"></i>
                <input 
                  id="username" 
                  name="username"
                  type="text"
                  autocomplete="username"
                  v-model="username" 
                  @input="syncValues"
                  @change="syncValues"
                  @blur="syncValues"
                  placeholder="Enter your username" 
                  required 
                  class="p-inputtext p-component full-width"
                  :disabled="loading"
                />
              </div>
            </div>

            <div class="form-group">
              <label for="password">Password</label>
              <div class="input-with-icon password-wrapper">
                <i class="pi pi-lock field-icon"></i>
                <input 
                  id="password" 
                  name="password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  v-model="password" 
                  @input="syncValues"
                  @change="syncValues"
                  @blur="syncValues"
                  placeholder="Enter your password" 
                  required 
                  class="p-inputtext p-component full-width password-input"
                  :disabled="loading"
                />
                <i 
                  class="pi toggle-icon"
                  :class="showPassword ? 'pi-eye-slash' : 'pi-eye'"
                  @click="showPassword = !showPassword"
                  title="Toggle password visibility"
                ></i>
              </div>
            </div>

            <button 
              type="submit" 
              class="submit-button p-button p-component" 
              :disabled="loading"
            >
              <i v-if="loading" class="pi pi-spin pi-spinner" style="margin-right: 0.5rem;"></i>
              <i v-else class="pi pi-sign-in" style="margin-right: 0.5rem;"></i>
              <span>{{ loading ? 'Signing In...' : 'Sign In' }}</span>
            </button>
          </form>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/api.js'
import { setUserState } from '../services/auth.js'
import Card from 'primevue/card'
import Message from 'primevue/message'

const router = useRouter()
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref(null)

const syncValues = () => {
  const uEl = document.getElementById('username')
  const pEl = document.getElementById('password')
  if (uEl && uEl.value) username.value = uEl.value
  if (pEl && pEl.value) password.value = pEl.value
}

onMounted(() => {
  // Sync in case browser password manager auto-populates the fields without triggering Vue events
  syncValues()
  setTimeout(syncValues, 200)
  setTimeout(syncValues, 600)
  setTimeout(syncValues, 1200)
})

const handleLogin = async () => {
  loading.value = true
  error.value = null
  
  // Directly extract values from DOM elements as fallback if browser autofill didn't fire Vue reactive input events
  const uEl = document.getElementById('username')
  const pEl = document.getElementById('password')
  const userInput = (uEl?.value || username.value || '').trim()
  const passInput = pEl?.value || password.value || ''

  if (!userInput || !passInput) {
    error.value = 'Please enter both username and password.'
    loading.value = false
    return
  }

  try {
    const response = await login(userInput, passInput)
    const payloadData = response.data?.data || response.data
    setUserState({
      username: payloadData.username,
      role: payloadData.role,
      must_change_password: payloadData.must_change_password
    })
    router.push('/')
  } catch (err) {
    if (err.response) {
      const status = err.response.status
      const detail = err.response.data?.detail
      if (status === 403) {
        error.value = detail || 'Account temporarily locked for 15 minutes due to multiple failed login attempts from this location.'
      } else if (status === 401) {
        error.value = detail || 'Invalid username or password. Please verify your credentials.'
      } else if (status === 429) {
        error.value = 'Too many requests. Please wait a moment before trying again.'
      } else if (status >= 500) {
        error.value = 'Server connection error. Please ensure the LNMP backend service is running.'
      } else {
        error.value = detail || 'Authentication failed. Please check your credentials and try again.'
      }
    } else {
      error.value = 'Unable to connect to LNMP server. Please check your network connection.'
    }
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
  color: #D0D0D0;
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
  color: #D0D0D0;
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
  color: #D0D0D0;
  z-index: 10;
  pointer-events: none;
}
.full-width {
  width: 100%;
  padding-left: 2.25rem !important;
}
.password-input {
  padding-right: 2.5rem !important;
}
.toggle-icon {
  position: absolute;
  right: 0.75rem;
  color: #888888;
  cursor: pointer;
  z-index: 10;
  padding: 0.25rem;
  font-size: 1rem;
}
.toggle-icon:hover {
  color: #FFFFFF;
}
.p-inputtext,
:deep(.p-inputtext) {
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  color: #FFFFFF !important;
  border-radius: 4px !important;
  font-size: 0.95rem;
  padding: 0.65rem 0.75rem 0.65rem 2.25rem;
}
.p-inputtext:focus,
:deep(.p-inputtext:focus) {
  border-color: #049f6c !important;
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
  background-color: #e5e5e5 !important;
  border-color: #e5e5e5 !important;
}
 
/* Light Mode Overrides */
</style>

<style>
html:not(.dark) .login-wrapper {
  background: radial-gradient(circle at 50% 50%, #f8fafc 0%, #e2e8f0 100%);
}
html:not(.dark) .glass-container {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
}
html:not(.dark) .brand-icon {
  color: #0f172a;
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
}
html:not(.dark) h2 {
  color: #0f172a;
}
html:not(.dark) .brand-subtitle {
  color: #475569;
}
html:not(.dark) label {
  color: #334155;
}
html:not(.dark) .field-icon {
  color: #64748b;
}
html:not(.dark) .p-inputtext {
  background-color: #ffffff !important;
  border: 1px solid #cbd5e1 !important;
  color: #0f172a !important;
}
html:not(.dark) .p-inputtext:focus {
  border-color: #049f6c !important;
}
html:not(.dark) .submit-button {
  background-color: #0f172a !important;
  border-color: #0f172a !important;
  color: #ffffff !important;
}
html:not(.dark) .submit-button:hover {
  background-color: #334155 !important;
  border-color: #334155 !important;
}
</style>
