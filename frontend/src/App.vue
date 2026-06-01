<template>
  <div id="app">
    <header class="app-header" v-if="showNav">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-icon">⬡</span>
          <span class="brand-name">lnmp</span>
          <span class="brand-version">v1(beta)</span>
        </div>
        <nav class="header-nav">
          <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute, RouterLink, RouterView } from 'vue-router'
import { logout } from './services/api.js'

const router = useRouter()
const route = useRoute()
const isDark = ref(false)
const currentUser = ref(null)
const isAdmin = ref(false)

const noNavRoutes = ['/login', '/change-password']
const showNav = computed(() => !noNavRoutes.includes(route.path))

onMounted(() => {
  const saved = localStorage.getItem('theme') || 'dark'
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
  
  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    try {
      const parsed = JSON.parse(storedUser)
      currentUser.value = parsed.username
      if (parsed.role === 'ADMIN') {
        isAdmin.value = true
      }
    } catch (e) {
      console.error('Failed to parse user state:', e)
    }
  }
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

async function handleLogout() {
  try { 
    await logout() 
  } catch (err) {
    console.error('Logout error:', err)
  }
  localStorage.removeItem('user')
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
  --border-color: #e0e0e0;
  --border-color-strong: #c0c0c0;
  --text-primary: #111111;
  --text-secondary: #555555;
  --text-muted: #888888;
  --text-inverse: #ffffff;
  --accent: #111111;
  --accent-hover: #333333;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.12);
  --radius: 8px;
  
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

html.dark {
  --bg-app: #0d0d0d;
  --bg-surface: #1a1a1a;
  --bg-surface-hover: #222222;
  --bg-surface-selected: #2a2a2a;
  --border-color: #2a2a2a;
  --border-color-strong: #404040;
  --text-primary: #f0f0f0;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --text-inverse: #111111;
  --accent: #f0f0f0;
  --accent-hover: #cccccc;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.6);
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
  color: var(--text-muted);
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
</style>
