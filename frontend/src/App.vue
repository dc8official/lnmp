<template>
  <div id="app">
    <header class="app-header" v-if="showNav">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-icon">⬡</span>
          <span class="brand-name">lnmp</span>
          <span class="brand-version">v1.5(beta)</span>
        </div>
        <nav class="header-nav">
          <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
          <RouterLink to="/users" class="nav-link" v-if="isAdmin">User Management</RouterLink>
        </nav>
        <div class="header-actions">
          <button class="theme-toggle" @click="toggleTheme"
                  :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'">
            {{ isDark ? '☀' : '☾' }}
          </button>
          <span class="user-badge" v-if="currentUser">
            {{ currentUser }} <span class="role-tag" v-if="isAdmin">(Admin)</span>
          </span>
          <button class="btn-sign-out" @click="handleLogout">
            Sign Out
          </button>
        </div>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>

    <!-- Forced Password Change Modal (Initial Setup / Admin Reset) -->
    <div v-if="displayPasswordModal" class="modal-overlay">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Initial Setup — Password Reset Required</h3>
        </div>
        <form @submit.prevent="executeChangePassword" class="modal-form">
          <div class="alert-info warning-alert">
            For security reasons, you are required to change your default or temporary password before continuing.
          </div>
          
          <div v-if="changePasswordError" class="alert-error">
            {{ changePasswordError }}
          </div>

          <div v-if="!mustChangePassword" class="form-group">
            <label>Current Password *</label>
            <input 
              type="password"
              v-model="changePasswordForm.old_password" 
              placeholder="Enter current password" 
              :required="!mustChangePassword" 
              :disabled="changePasswordLoading"
            />
          </div>
          <div class="form-group">
            <label>New Password *</label>
            <input 
              type="password"
              v-model="changePasswordForm.new_password" 
              placeholder="Enter new password (min 8 chars)" 
              required 
              :disabled="changePasswordLoading"
            />
          </div>
          <div class="form-group">
            <label>Confirm New Password *</label>
            <input 
              type="password"
              v-model="changePasswordForm.confirm_password" 
              placeholder="Confirm new password" 
              required 
              :disabled="changePasswordLoading"
            />
          </div>
          <div class="modal-actions">
            <button type="submit" class="btn-primary full-width-btn" :disabled="changePasswordLoading">
              {{ changePasswordLoading ? 'Updating...' : 'Update Password & Sign In' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute, RouterLink, RouterView } from 'vue-router'
import { logout, changePassword } from './services/api.js'
import { currentUser, isAdmin, mustChangePassword, loadUserFromStorage, setUserState, clearUserState } from './services/auth.js'

const router = useRouter()
const route = useRoute()
const isDark = ref(false)

const noNavRoutes = ['/login', '/change-password']
const showNav = computed(() => !noNavRoutes.includes(route.path))

const displayPasswordModal = computed(() => {
  return !!currentUser.value && !!mustChangePassword.value && route.path !== '/login'
})

const changePasswordLoading = ref(false)
const changePasswordError = ref(null)
const changePasswordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

onMounted(() => {
  const saved = localStorage.getItem('theme') || 'dark'
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
  
  loadUserFromStorage()
})

function toggleTheme() {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

async function executeChangePassword() {
  if (changePasswordForm.value.new_password.length < 8) {
    changePasswordError.value = 'New password must be at least 8 characters long.'
    return
  }
  if (changePasswordForm.value.new_password !== changePasswordForm.value.confirm_password) {
    changePasswordError.value = 'New password and confirmation do not match.'
    return
  }

  changePasswordLoading.value = true
  changePasswordError.value = null
  try {
    await changePassword({
      old_password: changePasswordForm.value.old_password,
      new_password: changePasswordForm.value.new_password
    })
    
    const existing = loadUserFromStorage() || {}
    setUserState({
      username: existing.username || '',
      role: existing.role || '',
      must_change_password: false
    })

    changePasswordForm.value = {
      old_password: '',
      new_password: '',
      confirm_password: ''
    }

    alert('Password updated successfully! You now have full access to the platform.')
  } catch (err) {
    console.error('Failed to change password:', err)
    changePasswordError.value = err.response?.data?.detail || 'Failed to update password. Verify current password.'
  } finally {
    changePasswordLoading.value = false
  }
}

async function handleLogout() {
  try { 
    await logout() 
  } catch (err) {
    console.error('Logout error:', err)
  }
  clearUserState()
  router.push('/login')
}
</script>

<style>
/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; padding: 0; }
a { text-decoration: none; color: inherit; }
button { cursor: pointer; border: none; background: none; }

/* ── CSS Variables Design System ── */
:root {
  --bg-app: #f5f5f5;
  --bg-surface: #ffffff;
  --bg-surface-hover: #f9f9f9;
  --bg-surface-selected: #f0f0f0;
  --border-color: #d0d0d0;
  --border-color-strong: #c0c0c0;
  --text-primary: #111111;
  --text-secondary: #444444;
  --text-muted: #666666;
  --text-inverse: #ffffff;
  --accent: #111111;
  --accent-hover: #333333;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.12);
  --radius-sm: 4px;
  --radius: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  --text-xs: 0.75rem;     /* 12px */
  --text-sm: 0.8125rem;   /* 13px */
  --text-base: 0.875rem;  /* 14px */
  --text-lg: 1rem;        /* 16px */
  --text-xl: 1.15rem;     /* 18px */
  --text-2xl: 1.5rem;     /* 24px */
  
  /* Semantic Status Variables */
  --status-up-color: #16a34a;        /* High-contrast green */
  --status-warn-color: #b45309;      /* Darker amber for light mode legibility */
  --status-down-color: #dc2626;      /* High-contrast red */
  
  /* Status Colors (Identical in both themes) */
  --color-up: #16a34a;
  --color-up-bg: rgba(22, 163, 74, 0.1);
  --color-up-unstable: #d97706;
  --color-up-unstable-bg: rgba(217, 119, 6, 0.1);
  --color-down-unstable: #ea580c;
  --color-down-unstable-bg: rgba(234, 88, 12, 0.1);
  --color-down: #dc2626;
  --color-down-bg: rgba(220, 38, 38, 0.1);
  --color-unknown: #6b7280;
  --color-unknown-bg: rgba(107, 114, 128, 0.1);

  /* Backwards-compatibility Aliases */
  --canvas-bg: var(--bg-app);
  --card-bg: var(--bg-surface);
  --card-border: var(--border-color);
}

/* ── Focus Outlines for Keyboard Accessibility ── */
:focus-visible {
  outline: 2px solid #2563EB;
  outline-offset: 2px;
}
html.dark :focus-visible {
  outline: 2px solid #60A5FA;
  outline-offset: 2px;
}

html.dark {
  --bg-app: #0d0d0d;
  --bg-surface: #1a1a1a;
  --bg-surface-hover: #222222;
  --bg-surface-selected: #2a2a2a;
  --border-color: #3a3a3a;
  --border-color-strong: #404040;
  --text-primary: #f0f0f0;
  --text-secondary: #b5b5b5;
  --text-muted: #808080;
  --text-inverse: #111111;
  --accent: #f0f0f0;
  --accent-hover: #cccccc;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.6);
  
  /* Dark Mode Semantic Refinements */
  --status-up-color: #4ade80;        /* Glowing green */
  --status-warn-color: #f59e0b;      /* Bright amber */
  --status-down-color: #f87171;      /* Bright red */
  --color-unknown: #808080;
  --color-unknown-bg: rgba(128, 128, 128, 0.15);
}

/* ── Base ── */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
    Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-app);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  transition: background-color 0.2s, color 0.2s;
}

#app { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header ── */
.app-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 16px;
  color: var(--text-primary);
}

.brand-icon { font-size: 20px; }

.brand-version {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-muted);
  background: var(--bg-surface-selected);
  padding: 2px 6px;
  border-radius: 4px;
}

.header-nav {
  display: flex;
  gap: 4px;
  flex: 1;
}

.nav-link {
  padding: 6px 12px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover,
.nav-link.router-link-active {
  background: var(--bg-surface-selected);
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.theme-toggle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--text-secondary);
  background: var(--bg-surface-selected);
  transition: background 0.15s;
}

.theme-toggle:hover { background: var(--border-color); }

.user-badge {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 12px;
  background: var(--bg-surface-selected);
  border-radius: 20px;
  border: 1px solid var(--border-color);
  font-weight: 500;
}

.role-tag {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 400;
  margin-left: 2px;
}

.btn-sign-out {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  padding: 6px 14px;
  border: 1px solid var(--border-color-strong);
  border-radius: var(--radius);
  background: transparent;
  transition: background 0.15s;
}

.btn-sign-out:hover { background: var(--bg-surface-selected); }

/* ── Main Layout ── */
.app-main {
  flex: 1;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px;
}

/* ── Shared Badges & Indicators ── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.badge-up {
  color: var(--color-up);
  background: var(--color-up-bg);
}
.badge-up-unstable {
  color: var(--color-up-unstable);
  background: var(--color-up-unstable-bg);
}
.badge-down-unstable {
  color: var(--color-down-unstable);
  background: var(--color-down-unstable-bg);
}
.badge-down {
  color: var(--color-down);
  background: var(--color-down-bg);
}
.badge-unknown {
  color: var(--color-unknown);
  background: var(--color-unknown-bg);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.dot-up { background: var(--color-up); }
.dot-up-unstable { background: var(--color-up-unstable); }
.dot-down-unstable { background: var(--color-down-unstable); }
.dot-down { background: var(--color-down); }
.dot-unknown { background: var(--color-unknown); }

/* ── Global High Contrast Button System ── */
button {
  font-family: inherit;
  cursor: pointer;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.btn-primary {
  background-color: #2563EB;
  color: #FFFFFF;
  border: 1px solid #1D4ED8;
  padding: 8px 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background-color: #1D4ED8;
  border-color: #1E40AF;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: var(--bg-surface-selected);
  color: var(--text-primary);
  border: 1px solid var(--border-color-strong);
  padding: 8px 16px;
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--border-color);
  color: var(--text-primary);
}

.btn-danger {
  background-color: #DC2626;
  color: #FFFFFF;
  border: 1px solid #B91C1C;
  padding: 8px 16px;
}

.btn-danger:hover:not(:disabled) {
  background-color: #B91C1C;
}

/* ── Modal Overlay & Card System ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(6px);
  padding: 16px;
}

.modal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
  border-radius: 12px;
  width: 460px;
  max-width: 95vw;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-card.wide {
  width: 600px;
}

.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-surface-selected);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1.25rem;
  padding: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease;
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.modal-form {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.alert-info {
  background: rgba(37, 99, 235, 0.15);
  border: 1px solid rgba(37, 99, 235, 0.3);
  color: #60A5FA;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  line-height: 1.4;
}

:global(html:not(.dark)) .alert-info {
  background: #EFF6FF;
  border-color: #93C5FD;
  color: #1D4ED8;
}

.alert-error {
  background: rgba(220, 38, 38, 0.15);
  border: 1px solid rgba(220, 38, 38, 0.3);
  color: #F87171;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  line-height: 1.4;
}

:global(html:not(.dark)) .alert-error {
  background: #FEF2F2;
  border-color: #FCA5A5;
  color: #DC2626;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 0.82rem;
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-group label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.form-group input, .form-select, .form-textarea {
  background: var(--bg-app);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 10px 12px;
  color: var(--text-primary);
  font-size: var(--text-base);
  width: 100%;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-group input:focus, .form-select:focus, .form-textarea:focus {
  border-color: #049f6c;
  box-shadow: 0 0 0 3px rgba(4, 159, 108, 0.15);
}

/* ── Global Spinner System ── */
.spinner-sm {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s infinite linear;
}
html:not(.dark) .spinner-sm {
  border: 2px solid rgba(0, 0, 0, 0.12);
  border-top-color: #3b82f6;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.full-width-btn {
  width: 100%;
  padding: 12px;
  font-size: 0.95rem;
}
</style>
