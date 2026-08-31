<template>
  <div id="app">
    <header class="app-header" v-if="showNav">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-name">lnmp</span>
          <span class="brand-version">{{ appVersion || 'v3.0.0' }}</span>
        </div>
        <nav class="header-nav" aria-label="Main Navigation">
          <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
          <RouterLink to="/topology" class="nav-link">Topology Map</RouterLink>
          <RouterLink to="/settings" class="nav-link" v-if="isAdmin">Admin Settings</RouterLink>
        </nav>
        <div class="header-actions">
          <button 
            class="theme-toggle" 
            @click="toggleTheme"
            :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          >
            {{ isDark ? '☀' : '☾' }}
          </button>
          <span class="user-badge" v-if="currentUser">
            {{ currentUser }} <span class="role-tag" v-if="isAdmin">(ADMIN)</span>
          </span>
          <button class="btn-sign-out" @click="handleLogout">
            Sign Out
          </button>
        </div>
      </div>
    </header>

    <!-- Accessible live region for real-time announcements -->
    <div class="sr-only" aria-live="polite" aria-atomic="true">
      {{ liveAnnouncement }}
    </div>

    <main class="app-main">
      <RouterView />
    </main>

    <!-- Forced Password Change Modal -->
    <div v-if="displayPasswordModal" class="modal-overlay">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Initial Setup — Password Reset Required</h3>
        </div>
        <form @submit.prevent="executeChangePassword" class="modal-form">
          <div class="alert-info warning-alert">
            For security reasons, you are required to change your default or temporary password before continuing.
          </div>
          
          <div v-if="changePasswordError" class="alert-error" role="alert">
            {{ changePasswordError }}
          </div>

          <div class="form-group">
            <label for="current-password">Current Password *</label>
            <input 
              id="current-password"
              name="current-password"
              type="password"
              autocomplete="current-password"
              v-model="changePasswordForm.old_password" 
              placeholder="Enter current password" 
              required 
              :disabled="changePasswordLoading"
            />
          </div>
          <div class="form-group">
            <label for="new-password">New Password *</label>
            <input 
              id="new-password"
              name="new-password"
              type="password"
              autocomplete="new-password"
              v-model="changePasswordForm.new_password" 
              placeholder="Enter new password (min 8 chars)" 
              required 
              :disabled="changePasswordLoading"
            />
          </div>
          <div class="form-group">
            <label for="confirm-password">Confirm New Password *</label>
            <input 
              id="confirm-password"
              name="confirm-password"
              type="password"
              autocomplete="new-password"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute, RouterLink, RouterView } from 'vue-router'
import { logout, changePassword, getVersion } from './services/api.js'
import { currentUser, isAdmin, mustChangePassword, loadUserFromStorage, setUserState, clearUserState } from './services/auth.js'

const router = useRouter()
const route = useRoute()
const isDark = ref(true)
const appVersion = ref('v3.0.0')
const liveAnnouncement = ref('')
let globalSse = null

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

onMounted(async () => {
  const saved = localStorage.getItem('theme') || 'dark'
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
  
  loadUserFromStorage()

  try {
    const res = await getVersion()
    if (res.data?.data?.version) {
      appVersion.value = `v${res.data.data.version.replace(/^v/, '')}`
    }
  } catch (err) {
    appVersion.value = 'v3.0.0'
  }

  // Global SSE listener for accessibility screen reader announcements
  try {
    globalSse = new EventSource('/api/v1/events/stream')
    globalSse.onmessage = (e) => {
      if (!e.data) return
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'STATE_TRANSITION') {
          liveAnnouncement.value = `Network update: Endpoint state transitioned to ${payload.detailed_state}`
        } else if (payload.type === 'NODE_STATE_CHANGE') {
          liveAnnouncement.value = `Topology update: Node status is now ${payload.new_state}`
        }
      } catch (err) {}
    }
  } catch (err) {}
})

onUnmounted(() => {
  if (globalSse) globalSse.close()
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

/* ── Screen Reader Live Announcement ── */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* ── CSS Variables Design System ── */
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;

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
  --status-up-color: #16a34a;
  --status-warn-color: #b45309;
  --status-down-color: #dc2626;
  
  /* Status Colors */
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

  --canvas-bg: var(--bg-app);
  --card-bg: var(--bg-surface);
  --card-border: var(--border-color);
}

/* ── Focus Outlines for Keyboard Accessibility (WCAG 2.1 AA) ── */
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
  --bg-surface: #161616;
  --bg-surface-hover: #1f1f1f;
  --bg-surface-selected: #262626;
  --border-color: #333333;
  --border-color-strong: #444444;
  --text-primary: #f0f0f0;
  --text-secondary: #b5b5b5;
  --text-muted: #808080;
  --text-inverse: #111111;
  --accent: #f0f0f0;
  --accent-hover: #cccccc;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.6);
  
  --status-up-color: #4ade80;
  --status-warn-color: #f59e0b;
  --status-down-color: #f87171;
  --color-unknown: #808080;
  --color-unknown-bg: rgba(128, 128, 128, 0.15);
}

/* ── Base ── */
body {
  font-family: var(--font-sans);
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

.brand-name {
  letter-spacing: 0.05em;
}

.brand-version {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--bg-surface-selected);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
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
  transition: color 0.15s, background-color 0.15s;
}

.nav-link:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.nav-link.router-link-active {
  color: var(--text-primary);
  font-weight: 600;
  background: var(--bg-surface-selected);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.theme-toggle {
  font-size: 16px;
  padding: 6px 10px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  transition: all 0.15s ease;
}

.theme-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.user-badge {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.role-tag {
  font-size: 11px;
  color: #3B82F6;
  font-weight: 700;
}

.btn-sign-out {
  padding: 6px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.btn-sign-out:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

/* ── Main Layout ── */
.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
  width: 100%;
  flex: 1;
  box-sizing: border-box;
}

/* ── Generic Buttons ── */
.btn-primary {
  background: var(--accent);
  color: var(--text-inverse);
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-surface-hover);
}

.btn-danger {
  background: #DC2626;
  color: white;
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
}

.btn-danger:hover:not(:disabled) {
  background: #B91C1C;
}

/* ── Modals ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}

.modal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  width: 100%;
  max-width: 500px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-surface-selected);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.btn-close {
  font-size: 16px;
  color: var(--text-muted);
}

.btn-close:hover {
  color: var(--text-primary);
}

.modal-form {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-input, .form-select, input[type="text"], input[type="password"] {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-family: inherit;
}

.form-input:focus, .form-select:focus, input:focus {
  border-color: var(--accent);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

.full-width-btn {
  width: 100%;
}

.tnum {
  font-feature-settings: "tnum";
  font-variant-numeric: tabular-nums;
}
</style>
