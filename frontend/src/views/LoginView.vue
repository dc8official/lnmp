<template>
  <div class="login-wrapper">
    <div class="glass-container">
      <Card class="login-card">
        <template #title>
          <div class="brand-header">
            <h2>lnmp v3.0.0</h2>
            <p class="brand-subtitle">Network Uptime Monitoring Platform</p>
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
import { ref } from 'vue'
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

const handleLogin = async () => {
  const u = (username.value || '').trim()
  const p = password.value || ''

  if (!u || !p) {
    error.value = 'Please enter both username and password.'
    return
  }

  loading.value = true
  error.value = null

  try {
    const response = await login(u, p)
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
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--bg-primary, #09090b);
  background-image: 
    radial-gradient(at 0% 0%, rgba(255, 255, 255, 0.03) 0px, transparent 50%),
    radial-gradient(at 100% 100%, rgba(255, 255, 255, 0.02) 0px, transparent 50%);
  padding: 1.5rem;
}

.glass-container {
  width: 100%;
  max-width: 420px;
}

:deep(.p-card.login-card) {
  background: var(--bg-surface, #121215);
  border: 1px solid var(--border-color, #27272a);
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  padding: 1.5rem;
}

.brand-header {
  text-align: center;
  margin-bottom: 2rem;
}

.brand-header h2 {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--text-primary, #fafafa);
  letter-spacing: -0.04em;
  margin: 0;
  text-transform: lowercase;
}

.brand-subtitle {
  font-size: 0.8125rem;
  color: var(--text-secondary, #a1a1aa);
  margin-top: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
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

.form-group label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary, #a1a1aa);
  letter-spacing: -0.01em;
}

.input-with-icon {
  position: relative;
  display: flex;
  align-items: center;
}

.field-icon {
  position: absolute;
  left: 0.875rem;
  color: var(--text-tertiary, #71717a);
  pointer-events: none;
  font-size: 0.9375rem;
  z-index: 1;
}

.input-with-icon input {
  padding-left: 2.5rem;
  height: 2.625rem;
  background: var(--bg-surface-hover);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: var(--radius-sm, 6px);
  font-size: 0.875rem;
  transition: all 0.15s ease;
  width: 100%;
}

.input-with-icon input:focus {
  outline: none;
  border-color: var(--text-primary);
  box-shadow: 0 0 0 1px var(--text-primary);
  background: var(--bg-surface);
}

.password-wrapper input {
  padding-right: 2.5rem;
}

.toggle-icon {
  position: absolute;
  right: 0.875rem;
  color: var(--text-tertiary, #71717a);
  cursor: pointer;
  font-size: 0.9375rem;
  padding: 0.25rem;
  transition: color 0.15s ease;
}

.toggle-icon:hover {
  color: var(--text-primary, #fafafa);
}

.submit-button {
  height: 2.625rem;
  margin-top: 0.5rem;
  background: var(--btn-primary-bg, #fafafa);
  color: var(--btn-primary-text, #09090b);
  border: none;
  font-weight: 600;
  font-size: 0.875rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.15s ease;
}

.submit-button:hover:not(:disabled) {
  background: #e4e4e7;
  transform: translateY(-1px);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 480px) {
  .glass-container {
    max-width: 100%;
  }
}
</style>
