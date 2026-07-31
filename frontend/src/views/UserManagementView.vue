<template>
  <div class="user-management-view">
    <div class="view-header">
      <div>
        <h1 class="page-title">User Account Management</h1>
        <p class="page-sub">Manage platform operator & administrator accounts and permissions</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="fetchUsers" :disabled="loading">
          {{ loading ? 'Refreshing...' : '↻ Refresh List' }}
        </button>
        <button class="btn-primary" @click="openAddDialog">
          + Add User Account
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert-error">
      {{ error }}
    </div>

    <!-- Users Table -->
    <div class="table-card">
      <div v-if="loading && users.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Loading user accounts...</p>
      </div>

      <div v-else-if="users.length === 0" class="empty-state">
        <p>No user accounts found.</p>
      </div>

      <table v-else class="data-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Role</th>
            <th>Created At</th>
            <th class="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
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
              <span class="date-sub">{{ formatDate(u.created_at) }}</span>
            </td>
            <td class="text-right">
              <button class="btn-icon" @click="openResetPasswordDialog(u)" title="Reset Password">🔑 Reset Password</button>
              <button class="btn-icon danger" @click="confirmDelete(u)" :disabled="u.username === currentUser" title="Delete User">🗑 Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add User Modal -->
    <div class="modal-overlay" v-if="showAddModal" @click.self="showAddModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Create New User Account</h3>
          <button class="btn-close" @click="showAddModal = false">✕</button>
        </div>

        <form @submit.prevent="saveUser" class="modal-form">
          <div class="form-group">
            <label>Username *</label>
            <input v-model="form.username" type="text" placeholder="operator_alex" required />
          </div>

          <div class="form-group">
            <label>Password *</label>
            <input v-model="form.password" type="password" placeholder="••••••••" required />
          </div>

          <div class="form-group">
            <label>Account Role *</label>
            <select v-model="form.role" class="form-select">
              <option value="VIEWER">VIEWER (Read-Only Operator)</option>
              <option value="ADMIN">ADMIN (Full Control)</option>
            </select>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showAddModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Creating...' : 'Create User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reset Password Modal -->
    <div class="modal-overlay" v-if="showResetModal" @click.self="showResetModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Reset Password for {{ targetUsername }}</h3>
          <button class="btn-close" @click="showResetModal = false">✕</button>
        </div>

        <form @submit.prevent="saveResetPassword" class="modal-form">
          <div class="form-group">
            <label>New Password *</label>
            <input v-model="resetForm.password" type="password" placeholder="••••••••" required />
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="showResetModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Saving...' : 'Reset Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getUsers, createUser, resetUserPassword, deleteUser } from '../services/api.js'

const users = ref([])
const loading = ref(true)
const error = ref(null)
const saving = ref(false)
const currentUser = ref('')

const showAddModal = ref(false)
const showResetModal = ref(false)
const targetUserId = ref(null)
const targetUsername = ref('')

const form = ref({
  username: '',
  password: '',
  role: 'VIEWER'
})

const resetForm = ref({
  password: ''
})

function formatDate(isoStr) {
  if (!isoStr) return '-'
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
    error.value = 'Failed to load user accounts.'
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  form.value = { username: '', password: '', role: 'VIEWER' }
  showAddModal.value = true
}

async function saveUser() {
  saving.value = true
  try {
    await createUser(form.value)
    showAddModal.value = false
    await fetchUsers()
    alert('User account created successfully.')
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
    await resetUserPassword(targetUserId.value, { password: resetForm.value.password })
    showResetModal.value = false
    alert(`Password reset successfully for ${targetUsername.value}.`)
  } catch (err) {
    console.error('Failed to reset password:', err)
    alert(err.response?.data?.detail || 'Failed to reset password.')
  } finally {
    saving.value = false
  }
}

async function confirmDelete(u) {
  if (confirm(`Are you sure you want to delete user account ${u.username}?`)) {
    try {
      await deleteUser(u.id)
      await fetchUsers()
    } catch (err) {
      console.error('Failed to delete user:', err)
      alert('Failed to delete user account.')
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

.table-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
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
  color: var(--text-muted);
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

.date-sub {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.btn-icon {
  padding: 5px 10px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  margin-left: 6px;
  background: var(--bg-surface-selected);
  cursor: pointer;
}

.btn-icon.danger:hover {
  color: #F87171;
  border-color: #EF4444;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

.modal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1.2rem;
  cursor: pointer;
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
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.form-group input, .form-select {
  background: var(--bg-app);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}
</style>
