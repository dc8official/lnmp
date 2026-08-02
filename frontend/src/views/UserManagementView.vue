<template>
  <div class="user-management-view">
    <!-- Header Toolbar -->
    <div class="view-header">
      <div>
        <h1 class="page-title">User Account & Credential Governance</h1>
        <p class="page-sub">Manage platform operator accounts, security credentials, and access control roles</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="fetchUsers" :disabled="loading">
          {{ loading ? 'Refreshing...' : '↻ Refresh Accounts' }}
        </button>
        <button class="btn-primary" @click="openAddDialog">
          + Add User Account
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert-error">
      <span>⚠️ {{ error }}</span>
      <button class="btn-retry" @click="fetchUsers">Retry</button>
    </div>

    <!-- Users Table Card -->
    <div class="table-card">
      <div v-if="loading && users.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Synchronizing platform user accounts...</p>
      </div>

      <div v-else-if="users.length === 0" class="empty-state">
        <p>No registered user accounts found.</p>
      </div>

      <div v-else class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Account Status</th>
              <th>Credential State</th>
              <th>Last Active Sign-in</th>
              <th>Created At</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" :class="{ 'self-row': u.username === currentUser }">
              <td>
                <div class="user-info">
                  <span class="user-name">{{ u.username }}</span>
                  <span v-if="u.username === currentUser" class="you-tag">(You)</span>
                </div>
              </td>
              <td>
                <span class="role-badge" :class="u.role.toLowerCase()">
                  {{ u.role }}
                </span>
              </td>
              <td>
                <span class="status-badge" :class="u.is_active ? 'active' : 'disabled'">
                  <span class="status-dot" :class="u.is_active ? 'dot-active' : 'dot-disabled'"></span>
                  {{ u.is_active ? 'Active' : 'Disabled' }}
                </span>
              </td>
              <td>
                <span v-if="u.must_change_password" class="cred-badge pending">
                  ⚡ Reset Pending
                </span>
                <span v-else class="cred-badge secure">
                  ✓ Secure
                </span>
              </td>
              <td>
                <span class="date-sub">{{ formatDate(u.last_login) }}</span>
              </td>
              <td>
                <span class="date-sub">{{ formatDate(u.created_at) }}</span>
              </td>
              <td class="text-right">
                <div class="action-buttons">
                  <button 
                    class="btn-icon warning" 
                    @click="openResetPasswordDialog(u)" 
                    title="Reset Password"
                  >
                    🔑 Reset Pass
                  </button>
                  <button 
                    v-if="u.username !== currentUser"
                    class="btn-icon" 
                    :class="u.is_active ? 'toggle-disable' : 'toggle-enable'"
                    @click="toggleUserActive(u)" 
                    :title="u.is_active ? 'Disable Account' : 'Enable Account'"
                  >
                    {{ u.is_active ? '🚫 Disable' : '✅ Enable' }}
                  </button>
                  <button 
                    v-if="u.username !== currentUser"
                    class="btn-icon danger" 
                    @click="confirmDelete(u)" 
                    title="Delete User"
                  >
                    🗑 Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add User Modal -->
    <div class="modal-overlay" v-if="showAddModal" @click.self="showAddModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Register New User Account</h3>
          <button class="btn-close" @click="showAddModal = false">✕</button>
        </div>

        <form @submit.prevent="saveUser" class="modal-form">
          <div class="form-group">
            <label>Username *</label>
            <input v-model="form.username" type="text" placeholder="operator_alex" required />
          </div>

          <div class="form-group">
            <label>Temporary Password</label>
            <input v-model="form.password" type="password" placeholder="Leave blank to auto-generate (e.g. Falcon-482)" />
            <small class="form-help">User will be prompted to change temporary password on initial sign-in.</small>
          </div>

          <div class="form-group">
            <label>Account Role *</label>
            <select v-model="form.role" class="form-select">
              <option value="VIEWER">VIEWER (Read-Only Operator)</option>
              <option value="ADMIN">ADMIN (Full Administrative Control)</option>
            </select>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showAddModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Creating...' : 'Register User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reset Password Modal -->
    <div class="modal-overlay" v-if="showResetModal" @click.self="showResetModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Reset Password — {{ targetUsername }}</h3>
          <button class="btn-close" @click="showResetModal = false">✕</button>
        </div>

        <form @submit.prevent="saveResetPassword" class="modal-form">
          <div class="alert-info warning-alert">
            This will immediately invalidate the current password for <strong>{{ targetUsername }}</strong>. They will be required to set a new password on their next login.
          </div>

          <div class="form-group">
            <label>New Temporary Password</label>
            <input v-model="resetForm.password" type="password" placeholder="Leave blank to auto-generate (e.g. Falcon-482)" />
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showResetModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Resetting...' : 'Reset Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Temporary Password Display Modal -->
    <div class="modal-overlay" v-if="showPasswordModal" @click.self="showPasswordModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>🔑 Temporary Password Generated</h3>
          <button class="btn-close" @click="showPasswordModal = false">✕</button>
        </div>

        <div class="modal-form">
          <div class="alert-info warning-alert">
            Temporary password generated for <strong>{{ generatedPassUser }}</strong>. Please copy it now. The user will be required to change it on their next login.
          </div>

          <div class="password-box-container">
            <span class="password-display">{{ generatedPasswordValue }}</span>
            <button class="btn-primary btn-copy" type="button" @click="copyGeneratedPassword">
              {{ copyBtnText }}
            </button>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showPasswordModal = false">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Custom Confirmation Modal -->
    <div class="modal-overlay" v-if="confirmModal.show" @click.self="confirmModal.show = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>{{ confirmModal.title }}</h3>
          <button class="btn-close" @click="confirmModal.show = false">✕</button>
        </div>
        <div class="modal-form">
          <p class="modal-alert-text">{{ confirmModal.message }}</p>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="confirmModal.show = false">Cancel</button>
            <button type="button" class="btn-danger" @click="confirmModal.onConfirm">Confirm</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getUsers, createUser, updateUser, resetUserPassword, deleteUser } from '../services/api.js'

const users = ref([])
const loading = ref(true)
const error = ref(null)
const saving = ref(false)
const currentUser = ref('')

const showAddModal = ref(false)
const showResetModal = ref(false)
const showPasswordModal = ref(false)
const generatedPasswordValue = ref('')
const generatedPassUser = ref('')
const copyBtnText = ref('📋 Copy Password')
const targetUserId = ref(null)
const targetUsername = ref('')

const confirmModal = ref({
  show: false,
  title: '',
  message: '',
  onConfirm: () => {}
})

const form = ref({
  username: '',
  password: '',
  role: 'VIEWER'
})

const resetForm = ref({
  password: ''
})

function copyGeneratedPassword() {
  if (navigator.clipboard && generatedPasswordValue.value) {
    navigator.clipboard.writeText(generatedPasswordValue.value)
    copyBtnText.value = '✅ Copied!'
    setTimeout(() => {
      copyBtnText.value = '📋 Copy Password'
    }, 2000)
  }
}

function formatDate(isoStr) {
  if (!isoStr) return 'Never'
  return new Date(isoStr).toLocaleString()
}

async function fetchUsers() {
  loading.value = true
  error.value = null
  try {
    const res = await getUsers()
    users.value = res.data?.data || res.data || []
  } catch (err) {
    console.error('Failed to fetch users:', err)
    error.value = err.response?.data?.detail || err.response?.data?.error?.message || 'Failed to load user accounts. Administrative access required.'
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  form.value = { username: '', password: '', role: 'VIEWER' }
  showAddModal.value = true
}

async function saveUser() {
  if (form.value.username.trim().length < 3) {
    alert('Username must be at least 3 characters long.')
    return
  }
  saving.value = true
  try {
    const res = await createUser({
      username: form.value.username,
      password: form.value.password || null,
      role: form.value.role
    })
    showAddModal.value = false
    await fetchUsers()
    
    const genPass = res.data?.data?.generated_password || res.data?.generated_password
    if (genPass) {
      generatedPassUser.value = form.value.username
      generatedPasswordValue.value = genPass
      copyBtnText.value = '📋 Copy Password'
      showPasswordModal.value = true
    } else {
      alert(`User account '${form.value.username}' created successfully.`)
    }
  } catch (err) {
    console.error('Failed to create user:', err)
    alert(err.response?.data?.detail || 'Failed to create user.')
  } finally {
    saving.value = false
  }
}

function openResetPasswordDialog(u) {
  targetUserId.value = u.id
  targetUsername.value = u.username
  resetForm.value = { password: '' }
  showResetModal.value = true
}

async function saveResetPassword() {
  saving.value = true
  try {
    const res = await resetUserPassword(targetUserId.value, { password: resetForm.value.password || null })
    showResetModal.value = false
    await fetchUsers()
    
    const genPass = res.data?.data?.generated_password || res.data?.generated_password
    if (genPass) {
      generatedPassUser.value = targetUsername.value
      generatedPasswordValue.value = genPass
      copyBtnText.value = '📋 Copy Password'
      showPasswordModal.value = true
    } else {
      alert(`Password reset successfully for ${targetUsername.value}.`)
    }
  } catch (err) {
    console.error('Failed to reset password:', err)
    alert(err.response?.data?.detail || 'Failed to reset password.')
  } finally {
    saving.value = false
  }
}

async function toggleUserActive(u) {
  const newStatus = !u.is_active
  const actionName = newStatus ? 'enable' : 'disable'
  confirmModal.value = {
    show: true,
    title: `${newStatus ? 'Enable' : 'Disable'} User Account`,
    message: `Are you sure you want to ${actionName} account '${u.username}'?`,
    onConfirm: async () => {
      confirmModal.value.show = false
      try {
        await updateUser(u.id, { is_active: newStatus })
        await fetchUsers()
      } catch (err) {
        console.error('Failed to toggle user status:', err)
        alert(err.response?.data?.detail || 'Failed to update account status.')
      }
    }
  }
}

async function confirmDelete(u) {
  confirmModal.value = {
    show: true,
    title: 'Delete User Account',
    message: `Are you sure you want to delete user account '${u.username}'?`,
    onConfirm: async () => {
      confirmModal.value.show = false
      try {
        await deleteUser(u.id)
        await fetchUsers()
      } catch (err) {
        console.error('Failed to delete user:', err)
        alert(err.response?.data?.detail || 'Failed to delete user account.')
      }
    }
  }
}

onMounted(() => {
  const stored = localStorage.getItem('user')
  if (stored) {
    try {
      currentUser.value = JSON.parse(stored).username || ''
    } catch (e) {}
  }
  fetchUsers()
})
</script>

<style scoped>
.user-management-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  font-size: 1.5rem;
  color: var(--text-primary);
  margin: 0;
}

.page-sub {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 4px 0 0 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}



.alert-error {
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid var(--status-down-color);
  color: var(--status-down-color);
  padding: 12px 16px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-retry {
  background: #EF4444;
  color: #FFFFFF;
  border: none;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
}

.table-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}

.table-responsive {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.data-table th, .data-table td {
  padding: 14px 18px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.data-table th {
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  font-weight: 600;
}

.data-table tr.self-row {
  background: rgba(59, 130, 246, 0.05);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-weight: 600;
  color: var(--text-primary);
}

.you-tag {
  font-size: 0.75rem;
  color: #60A5FA;
  font-weight: 600;
}

.role-badge {
  font-size: 0.78rem;
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 700;
}

.role-badge.admin {
  background: rgba(220, 38, 38, 0.15);
  color: var(--status-down-color);
  border: 1px solid rgba(220, 38, 38, 0.3);
}

.role-badge.viewer {
  background: rgba(59, 130, 246, 0.15);
  color: #60A5FA;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
}

.status-badge.active {
  background: rgba(22, 163, 74, 0.15);
  color: var(--status-up-color);
}

.status-badge.disabled {
  background: rgba(220, 38, 38, 0.15);
  color: var(--status-down-color);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.dot-active { background: var(--status-up-color); }
.dot-disabled { background: var(--status-down-color); }

.cred-badge {
  font-size: 0.78rem;
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 600;
}

.cred-badge.pending {
  background: rgba(245, 158, 11, 0.15);
  color: var(--status-warn-color);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.cred-badge.secure {
  background: rgba(22, 163, 74, 0.15);
  color: var(--status-up-color);
  border: 1px solid rgba(22, 163, 74, 0.3);
}

.date-sub {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.action-buttons {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.btn-icon {
  padding: 5px 10px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-surface-selected);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-icon:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.btn-icon.warning:hover {
  color: var(--status-warn-color);
  border-color: var(--status-warn-color);
}

.btn-icon.danger:hover {
  color: var(--status-down-color);
  border-color: var(--status-down-color);
}

.btn-icon.toggle-disable:hover {
  color: var(--status-down-color);
  border-color: var(--status-down-color);
}

.btn-icon.toggle-enable:hover {
  color: var(--status-up-color);
  border-color: var(--status-up-color);
}

/* Modal Overlay & Card */
.form-help {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.loading-state, .empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: #2563EB;
  border-radius: 50%;
  animation: spin 1s infinite linear;
  margin: 0 auto 12px auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.password-box-container {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-app);
  border: 1px solid var(--border-color);
  padding: 12px 16px;
  border-radius: 8px;
  margin: 8px 0;
}

.password-display {
  font-family: monospace;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 1px;
  color: #2563eb;
  flex: 1;
}

.btn-copy {
  white-space: nowrap;
}

/* Light mode contrast overrides */
</style>

<style>
html:not(.dark) .you-tag {
  color: #1d4ed8;
}
html:not(.dark) .role-badge.viewer {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.25);
}
</style>
