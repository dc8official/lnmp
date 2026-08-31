<template>
  <div class="settings-view">
    <!-- Header Toolbar -->
    <div class="view-header">
      <div>
        <h1 class="page-title">Platform Administration & Governance</h1>
        <p class="page-sub">Configure performance engines, security policies, network discovery, and access control</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" @click="saveAllSettings" :disabled="saving">
          {{ saving ? 'Saving...' : '💾 Save Settings' }}
        </button>
      </div>
    </div>

    <!-- Alert / Toast Banner -->
    <div v-if="alertMessage" :class="['alert-banner', alertType]">
      <span>{{ alertMessage }}</span>
      <button class="btn-close" @click="alertMessage = null">✕</button>
    </div>

    <div class="settings-grid">
      <!-- Section 1: Performance & Storage Engine -->
      <div class="settings-card">
        <div class="card-header">
          <h2 class="card-title">⚡ Performance & Storage Engine</h2>
          <span class="engine-badge" :class="settings.performanceMode ? 'badge-redis' : 'badge-pg'">
            {{ settings.performanceMode ? 'REDIS ACCELERATED' : 'POSTGRESQL NATIVE' }}
          </span>
        </div>
        <p class="card-desc">
          Accelerate session lookups and real-time event broadcasting using in-memory Redis caching, with zero-downtime PostgreSQL fallback.
        </p>

        <div class="setting-row">
          <div>
            <label class="setting-label">Memory Acceleration Driver</label>
            <p class="setting-hint">When enabled, user session tokens and pub/sub events are routed through Redis.</p>
          </div>
          <div class="driver-toggle">
            <button 
              type="button" 
              class="btn-toggle-option" 
              :class="{ active: !settings.performanceMode }"
              @click="settings.performanceMode = false"
            >
              Standard (PostgreSQL)
            </button>
            <button 
              type="button" 
              class="btn-toggle-option" 
              :class="{ active: settings.performanceMode }"
              @click="settings.performanceMode = true"
            >
              Accelerated (Redis)
            </button>
          </div>
        </div>
      </div>

      <!-- Section 2: Network Discovery -->
      <div class="settings-card">
        <div class="card-header">
          <h2 class="card-title">🌐 Network Discovery & Diagnostics</h2>
        </div>
        <p class="card-desc">
          Control automated traceroute behavior and subnet traversal optimization.
        </p>

        <div class="setting-row">
          <div>
            <label class="setting-label">Layer-2 Subnet Auto-Bypass</label>
            <p class="setting-hint">Automatically bypass ICMP/UDP traceroute subprocesses for hosts on the local /24 broadcast segment.</p>
          </div>
          <label class="switch">
            <input type="checkbox" v-model="settings.l2AutoBypass" />
            <span class="slider round"></span>
          </label>
        </div>

        <div class="setting-row">
          <div>
            <label class="setting-label">Max Concurrent Traces</label>
            <p class="setting-hint">Global concurrency semaphore bound for simultaneous diagnostic traceroutes.</p>
          </div>
          <span class="font-mono tnum font-bold">3 Traces (500ms pacing)</span>
        </div>
      </div>

      <!-- Section 3: Security & Access Policies -->
      <div class="settings-card">
        <div class="card-header">
          <h2 class="card-title">🔒 Security & Access Policies</h2>
        </div>
        <p class="card-desc">
          Enforce session lifetime limits, brute-force throttling, and token revocation controls.
        </p>

        <div class="setting-row">
          <div>
            <label class="setting-label">User Session Inactivity Timeout</label>
            <p class="setting-hint">Automatic session revocation period for idle operator accounts.</p>
          </div>
          <select v-model="settings.sessionTimeout" class="form-select font-mono">
            <option value="15">15 Minutes</option>
            <option value="30">30 Minutes</option>
            <option value="60">1 Hour</option>
            <option value="120">2 Hours (Default)</option>
            <option value="240">4 Hours</option>
          </select>
        </div>

        <div class="setting-row">
          <div>
            <label class="setting-label">Brute-Force Lockout Threshold</label>
            <p class="setting-hint">Consecutive failed login attempts before IP and account cooldown is applied.</p>
          </div>
          <select v-model="settings.lockoutThreshold" class="form-select font-mono">
            <option value="3">3 Failed Attempts</option>
            <option value="5">5 Failed Attempts (Default)</option>
            <option value="10">10 Failed Attempts</option>
          </select>
        </div>
      </div>

      <!-- Section 4: User Account Governance -->
      <div class="settings-card full-width">
        <div class="card-header">
          <div>
            <h2 class="card-title">👥 User Account Governance</h2>
            <p class="card-desc">Manage platform operator credentials, system access roles, and status.</p>
          </div>
          <button class="btn-primary btn-small" @click="openAddUserModal">
            + Add User Account
          </button>
        </div>

        <div class="table-responsive" style="margin-top: 12px;">
          <table class="data-table" aria-label="User Accounts Table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Credential State</th>
                <th>Last Active Sign-in</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="font-bold">{{ u.username }}</td>
                <td>
                  <span class="role-badge" :class="u.role.toLowerCase()">
                    {{ u.role }}
                  </span>
                </td>
                <td>
                  <span class="status-pill" :class="u.is_active ? 'status-up' : 'status-down'">
                    {{ u.is_active ? 'ACTIVE' : 'DISABLED' }}
                  </span>
                </td>
                <td>
                  <span v-if="u.must_change_password" class="text-unstable font-bold">
                    ⚡ Reset Pending
                  </span>
                  <span v-else class="text-up font-bold">
                    ✓ Secure
                  </span>
                </td>
                <td class="font-mono tnum">
                  {{ u.last_login ? new Date(u.last_login).toLocaleString() : 'Never' }}
                </td>
                <td class="text-right">
                  <div class="table-actions">
                    <button class="btn-action" @click="openResetPasswordModal(u)" title="Reset Password">🔑 Reset</button>
                    <button 
                      v-if="u.username !== currentUser" 
                      class="btn-action" 
                      @click="toggleUserStatus(u)"
                    >
                      {{ u.is_active ? '🚫 Disable' : '✅ Enable' }}
                    </button>
                    <button 
                      v-if="u.username !== currentUser" 
                      class="btn-action text-down" 
                      @click="confirmDeleteUser(u)"
                    >
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Add User Modal -->
    <div class="modal-overlay" v-if="showAddModal" @click.self="showAddModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Register New Operator Account</h3>
          <button class="btn-close" @click="showAddModal = false">✕</button>
        </div>
        <form @submit.prevent="saveNewUser" class="modal-form">
          <div class="form-group">
            <label>Username *</label>
            <input v-model="userForm.username" type="text" placeholder="operator_alex" required />
          </div>
          <div class="form-group">
            <label>Temporary Password</label>
            <input v-model="userForm.password" type="password" placeholder="Leave blank to auto-generate" />
          </div>
          <div class="form-group">
            <label>Account Role *</label>
            <select v-model="userForm.role" class="form-select">
              <option value="VIEWER">VIEWER (Read-Only Operator)</option>
              <option value="ADMIN">ADMIN (Full Administrative Control)</option>
            </select>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showAddModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="userSaving">
              {{ userSaving ? 'Creating...' : 'Register User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reset Password Modal -->
    <div class="modal-overlay" v-if="showResetModal" @click.self="showResetModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Reset Password for {{ targetUser?.username }}</h3>
          <button class="btn-close" @click="showResetModal = false">✕</button>
        </div>
        <form @submit.prevent="executeResetPassword" class="modal-form">
          <div class="form-group">
            <label>New Temporary Password</label>
            <input v-model="resetPasswordVal" type="password" placeholder="Leave blank to auto-generate" />
          </div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showResetModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="userSaving">
              {{ userSaving ? 'Resetting...' : 'Confirm Reset' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getUsers, createUser, resetUserPassword, updateUser, deleteUser } from '../services/api.js'
import { currentUser, loadUserFromStorage } from '../services/auth.js'

const saving = ref(false)
const alertMessage = ref(null)
const alertType = ref('alert-success')

const settings = reactive({
  performanceMode: false,
  l2AutoBypass: true,
  sessionTimeout: '120',
  lockoutThreshold: '5'
})

const users = ref([])
const showAddModal = ref(false)
const showResetModal = ref(false)
const userSaving = ref(false)
const targetUser = ref(null)
const resetPasswordVal = ref('')

const userForm = reactive({
  username: '',
  password: '',
  role: 'VIEWER'
})

async function fetchUsersList() {
  try {
    const res = await getUsers()
    users.value = res.data?.data || []
  } catch (err) {
    console.error('Failed to load users:', err)
  }
}

function openAddUserModal() {
  userForm.username = ''
  userForm.password = ''
  userForm.role = 'VIEWER'
  showAddModal.value = true
}

async function saveNewUser() {
  userSaving.value = true
  try {
    await createUser(userForm)
    showAddModal.value = false
    alertMessage.value = `User account '${userForm.username}' created successfully.`
    alertType.value = 'alert-success'
    await fetchUsersList()
  } catch (err) {
    alertMessage.value = err.response?.data?.detail || 'Failed to create user.'
    alertType.value = 'alert-error'
  } finally {
    userSaving.value = false
  }
}

function openResetPasswordModal(user) {
  targetUser.value = user
  resetPasswordVal.value = ''
  showResetModal.value = true
}

async function executeResetPassword() {
  if (!targetUser.value) return
  userSaving.value = true
  try {
    await resetUserPassword(targetUser.value.id, {
      temporary_password: resetPasswordVal.value || undefined
    })
    showResetModal.value = false
    alertMessage.value = `Password reset for user '${targetUser.value.username}'.`
    alertType.value = 'alert-success'
    await fetchUsersList()
  } catch (err) {
    alertMessage.value = err.response?.data?.detail || 'Failed to reset password.'
    alertType.value = 'alert-error'
  } finally {
    userSaving.value = false
  }
}

async function toggleUserStatus(user) {
  try {
    await updateUser(user.id, { is_active: !user.is_active })
    await fetchUsersList()
  } catch (err) {
    alertMessage.value = 'Failed to update user status.'
    alertType.value = 'alert-error'
  }
}

async function confirmDeleteUser(user) {
  if (!confirm(`Are you sure you want to delete user account '${user.username}'?`)) return
  try {
    await deleteUser(user.id)
    alertMessage.value = `User account '${user.username}' deleted.`
    alertType.value = 'alert-success'
    await fetchUsersList()
  } catch (err) {
    alertMessage.value = 'Failed to delete user account.'
    alertType.value = 'alert-error'
  }
}

async function saveAllSettings() {
  saving.value = true
  try {
    // Save to localStorage / configuration store
    localStorage.setItem('netmon_settings', JSON.stringify(settings))
    alertMessage.value = 'Platform settings successfully saved and applied.'
    alertType.value = 'alert-success'
  } catch (err) {
    alertMessage.value = 'Failed to save settings.'
    alertType.value = 'alert-error'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loadUserFromStorage()
  const savedSettings = localStorage.getItem('netmon_settings')
  if (savedSettings) {
    try {
      Object.assign(settings, JSON.parse(savedSettings))
    } catch (e) {}
  }
  await fetchUsersList()
})
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.page-sub {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 20px;
}

@media (min-width: 1024px) {
  .settings-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.settings-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-card.full-width {
  grid-column: 1 / -1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.card-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid var(--border-color);
}

.setting-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.setting-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 2px 0 0 0;
}

.engine-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  font-family: var(--font-mono);
}

.badge-redis {
  background: rgba(239, 68, 68, 0.15);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.badge-pg {
  background: rgba(59, 130, 246, 0.15);
  color: #3B82F6;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.driver-toggle {
  display: flex;
  background: var(--bg-surface-selected);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
}

.btn-toggle-option {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-toggle-option.active {
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* Switch toggle */
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--bg-surface-selected);
  border: 1px solid var(--border-color);
  transition: 0.2s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: var(--text-muted);
  transition: 0.2s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #10B981;
  border-color: #10B981;
}

input:checked + .slider:before {
  transform: translateX(20px);
  background-color: white;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
}

.data-table th {
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  font-weight: 600;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.05em;
}

.data-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}

.role-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.role-badge.admin {
  background: rgba(59, 130, 246, 0.15);
  color: #60A5FA;
}

.role-badge.viewer {
  background: rgba(107, 114, 128, 0.15);
  color: #9CA3AF;
}

.status-pill {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}

.status-up { background: rgba(16, 185, 129, 0.15); color: #10B981; }
.status-down { background: rgba(239, 68, 68, 0.15); color: #EF4444; }

.table-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.btn-action {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-action:hover {
  background: var(--bg-surface-hover);
  color: var(--text-primary);
}

.alert-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 13px;
}

.alert-success {
  background: rgba(16, 185, 129, 0.1);
  color: #10B981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.alert-error {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.font-mono { font-family: var(--font-mono); }
.font-bold { font-weight: 600; }
.text-right { text-align: right; }
.text-up { color: #10B981; }
.text-unstable { color: #F59E0B; }
.text-down { color: #EF4444; }
.tnum { font-feature-settings: "tnum"; font-variant-numeric: tabular-nums; }
</style>
