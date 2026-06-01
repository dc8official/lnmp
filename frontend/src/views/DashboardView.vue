<template>
  <div class="dashboard">
    <!-- Header Toolbar -->
    <div class="dashboard-toolbar">
      <div class="toolbar-left">
        <h1 class="page-title">{{ activeTab === 'endpoints' ? 'Network Dashboard' : 'User Accounts' }}</h1>
        <p class="page-sub" v-if="activeTab === 'endpoints' && !loading && !error">
          {{ endpoints.length }} monitored endpoint{{ endpoints.length !== 1 ? 's' : '' }}
          <span class="separator">·</span>
          Sync: {{ lastRefreshedLabel }}
        </p>
        <p class="page-sub" v-else-if="activeTab === 'users' && !usersLoading && !usersError">
          {{ users.length }} registered user account{{ users.length !== 1 ? 's' : '' }}
        </p>
      </div>
      <div class="toolbar-right">
        <button 
          v-if="activeTab === 'endpoints'" 
          class="btn-secondary" 
          @click="fetchEndpoints" 
          :disabled="loading"
        >
          <span>{{ loading ? 'Refreshing...' : '↻ Refresh' }}</span>
        </button>
        <button 
          v-if="activeTab === 'endpoints' && isAdmin" 
          class="btn-primary" 
          @click="openAddDialog"
        >
          + Add Endpoint
        </button>

        <button 
          v-if="activeTab === 'users'" 
          class="btn-secondary" 
          @click="fetchUsers" 
          :disabled="usersLoading"
        >
          <span>{{ usersLoading ? 'Refreshing...' : '↻ Refresh' }}</span>
        </button>
        <button 
          v-if="activeTab === 'users' && isAdmin" 
          class="btn-primary" 
          @click="openAddUserDialog"
        >
          + Add User
        </button>
      </div>
    </div>

    <!-- Admin Console Tabs -->
    <div class="dashboard-tabs" v-if="isAdmin">
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'endpoints' }" 
        @click="activeTab = 'endpoints'"
      >
        Monitored Endpoints
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'users' }" 
        @click="activeTab = 'users'"
      >
        User Management
      </button>
    </div>

    <!-- Endpoints Content -->
    <div v-if="activeTab === 'endpoints'">
      <div v-if="error" class="alert-error">
        {{ error }}
      </div>

      <div v-if="loading && endpoints.length === 0" class="empty-state">
        <div class="spinner"></div>
        <p>Synchronizing network status...</p>
      </div>

      <div v-else-if="!loading && endpoints.length === 0 && !error" class="empty-state">
        <p class="empty-title">No endpoints configured</p>
        <p class="empty-sub">Add your first monitored endpoint to begin uptime tracking.</p>
        <button v-if="isAdmin" class="btn-primary" @click="openAddDialog">
          + Add Endpoint
        </button>
      </div>

      <div v-else class="endpoint-grid">
        <EndpointCard
          v-for="ep in endpoints"
          :key="ep.id"
          :endpoint="ep"
          :isAdmin="isAdmin"
          :selected="selectedIds.includes(ep.id)"
          @select="navigateTo"
          @toggle-select="toggleEndpointSelect"
          @edit="openEditDialog"
          @delete="confirmDeleteEndpoint"
        />
      </div>

      <!-- Selection Contextual Banner -->
      <transition name="fade">
        <div v-if="selectedIds.length > 0" class="selection-banner">
          <div class="banner-content">
            <span class="selection-count">
              <strong>{{ selectedIds.length }}</strong> target(s) selected for CSV export
            </span>
            <button 
              class="btn-primary btn-small" 
              :disabled="exporting" 
              @click="exportSelectedCSV"
            >
              {{ exporting ? 'Exporting...' : 'Export Selected CSV' }}
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- User Accounts Content (Admin Only) -->
    <div v-else-if="activeTab === 'users' && isAdmin">
      <div v-if="usersError" class="alert-error">
        {{ usersError }}
      </div>

      <div v-if="usersLoading && users.length === 0" class="empty-state">
        <div class="spinner"></div>
        <p>Loading user list...</p>
      </div>

      <div v-else class="table-card">
        <div class="table-responsive">
          <table class="audit-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Credentials State</th>
                <th>Last Signed In</th>
                <th class="actions-header">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="usr in users" :key="usr.id" :class="{ 'self-row': usr.id === user?.id }">
                <td class="username-col">
                  <strong>{{ usr.username }}</strong>
                  <span v-if="usr.id === user?.id" class="self-tag">(You)</span>
                </td>
                <td>
                  <span class="role-badge">{{ usr.role }}</span>
                </td>
                <td>
                  <span :class="['badge', usr.is_active ? 'badge-up' : 'badge-down']">
                    <span :class="['status-dot', usr.is_active ? 'dot-up' : 'dot-down']"></span>
                    {{ usr.is_active ? 'Active' : 'Disabled' }}
                  </span>
                </td>
                <td>
                  <span v-if="usr.must_change_password" class="badge badge-up-unstable">
                    Password Reset Pending
                  </span>
                  <span v-else class="badge badge-up">
                    Secure
                  </span>
                </td>
                <td>
                  {{ usr.last_login ? new Date(usr.last_login).toLocaleString() : 'Never' }}
                </td>
                <td class="actions-col">
                  <button class="btn-action-warning" @click="openResetPasswordDialog(usr)">
                    Reset Pass
                  </button>
                  <button 
                    v-if="usr.id !== user?.id"
                    :class="usr.is_active ? 'btn-action-danger' : 'btn-action-success'"
                    @click="toggleUserActive(usr)"
                  >
                    {{ usr.is_active ? 'Disable' : 'Enable' }}
                  </button>
                  <button 
                    v-if="usr.id !== user?.id" 
                    class="btn-action-danger" 
                    @click="confirmDeleteUser(usr)"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── Unified Redesign Modals ── -->

    <!-- Add / Edit Endpoint Modal -->
    <div v-if="displayDialog" class="modal-overlay" @click.self="displayDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">{{ isEditing ? 'Modify Endpoint' : 'Register Endpoint' }}</h2>
          <button class="modal-close" @click="displayDialog = false">×</button>
        </div>
        <form @submit.prevent="saveEndpoint">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">Hostname *</label>
              <input 
                class="form-input" 
                v-model="form.hostname" 
                placeholder="e.g. core-router.local" 
                required 
              />
            </div>
            <div class="form-group">
              <label class="form-label">IP Address *</label>
              <input 
                class="form-input" 
                v-model="form.ip_address" 
                placeholder="e.g. 192.168.1.1" 
                required 
                :disabled="isEditing" 
              />
            </div>
            <div class="form-group">
              <label class="form-label">Device Type *</label>
              <select class="form-input" v-model="form.device_type" required>
                <option v-for="type in deviceTypes" :key="type" :value="type">
                  {{ type }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Location (optional)</label>
              <input 
                class="form-input" 
                v-model="form.location" 
                placeholder="e.g. Datacenter rack A5" 
              />
            </div>
            <div class="form-group">
              <label class="form-label">Description (optional)</label>
              <textarea 
                class="form-input form-textarea" 
                v-model="form.description" 
                rows="3" 
                placeholder="Additional endpoint metadata"
              ></textarea>
            </div>
            <div class="form-group checkbox-form-group">
              <input 
                type="checkbox" 
                id="monitoring_enabled" 
                v-model="form.monitoring_enabled" 
              />
              <label for="monitoring_enabled">Enable automated uptime checks</label>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="displayDialog = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="formSaving">
              {{ formSaving ? 'Saving...' : 'Save Endpoint' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="displayDeleteDialog" class="modal-overlay" @click.self="displayDeleteDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Confirm Deletion</h2>
          <button class="modal-close" @click="displayDeleteDialog = false">×</button>
        </div>
        <div class="modal-body text-center">
          <p class="modal-alert-text">Are you sure you want to delete this endpoint?</p>
          <p class="warning-subtext">This action will stop active monitoring and is completely irreversible.</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-secondary" @click="displayDeleteDialog = false">Cancel</button>
          <button type="button" class="btn-danger" :disabled="formSaving" @click="executeDeleteEndpoint">
            {{ formSaving ? 'Deleting...' : 'Delete Host' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Forced Password Change Modal (Initial Setup) -->
    <div v-if="displayChangePasswordDialog" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Initial Setup — Password Reset Required</h2>
        </div>
        <form @submit.prevent="executeChangePassword">
          <div class="modal-body">
            <div class="alert-info">
              For security reasons, you are required to change your default password on your initial sign-in.
            </div>
            
            <div v-if="changePasswordError" class="alert-error">
              {{ changePasswordError }}
            </div>

            <div class="form-group">
              <label class="form-label">Current Password *</label>
              <input 
                type="password"
                class="form-input" 
                v-model="changePasswordForm.old_password" 
                placeholder="Enter current password" 
                required 
                :disabled="changePasswordLoading"
              />
            </div>
            <div class="form-group">
              <label class="form-label">New Password *</label>
              <input 
                type="password"
                class="form-input" 
                v-model="changePasswordForm.new_password" 
                placeholder="Enter new password (min 8 chars)" 
                required 
                :disabled="changePasswordLoading"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Confirm New Password *</label>
              <input 
                type="password"
                class="form-input" 
                v-model="changePasswordForm.confirm_password" 
                placeholder="Confirm new password" 
                required 
                :disabled="changePasswordLoading"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn-primary full-width-btn" :disabled="changePasswordLoading">
              {{ changePasswordLoading ? 'Updating...' : 'Update Password & Sign In' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add User Modal (Admin Only) -->
    <div v-if="displayAddUserDialog" class="modal-overlay" @click.self="displayAddUserDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Register New User Account</h2>
          <button class="modal-close" @click="displayAddUserDialog = false">×</button>
        </div>
        <form @submit.prevent="saveUser">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">Username *</label>
              <input 
                class="form-input" 
                v-model="userForm.username" 
                placeholder="Enter username (min 3 chars)" 
                required 
              />
            </div>
            <div class="form-group">
              <label class="form-label">Password</label>
              <input 
                type="password"
                class="form-input" 
                v-model="userForm.password" 
                placeholder="Defaults to 'password123' if blank" 
              />
              <small class="form-help">New users must change this temporary password on initial sign-in.</small>
            </div>
            <div class="form-group">
              <label class="form-label">Privilege Role *</label>
              <select class="form-input" v-model="userForm.role" required>
                <option value="VIEWER">VIEWER</option>
                <option value="ADMIN">ADMIN</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="displayAddUserDialog = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="userFormSaving">
              {{ userFormSaving ? 'Registering...' : 'Register User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reset User Password Modal (Admin Only) -->
    <div v-if="displayResetUserPasswordDialog" class="modal-overlay" @click.self="displayResetUserPasswordDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Reset Password — {{ targetUsername }}</h2>
          <button class="modal-close" @click="displayResetUserPasswordDialog = false">×</button>
        </div>
        <form @submit.prevent="executeResetUserPassword">
          <div class="modal-body">
            <div class="alert-info warning-alert">
              This will immediately invalidate the current password for <strong>{{ targetUsername }}</strong>. They will be forced to set a new password on their next sign-in.
            </div>
            <div class="form-group">
              <label class="form-label">New Temporary Password</label>
              <input 
                type="password"
                class="form-input" 
                v-model="resetPasswordForm.password" 
                placeholder="Defaults to 'password123' if blank" 
              />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="displayResetUserPasswordDialog = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="userFormSaving">
              {{ userFormSaving ? 'Resetting...' : 'Reset Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { 
  getEndpoints, 
  createEndpoint, 
  updateEndpoint, 
  deleteEndpoint, 
  changePassword,
  getUsers,
  createUser,
  resetUserPassword,
  updateUser,
  deleteUser,
  exportBatchTelemetry
} from '../services/api.js'
import EndpointCard from '../components/EndpointCard.vue'

const router = useRouter()
const isDarkMode = ref(true)

const endpoints = ref([])
const loading = ref(false)
const error = ref(null)
const lastRefreshed = ref(null)
const user = ref(null)

const selectedIds = ref([])
const exporting = ref(false)

const toggleEndpointSelect = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx > -1) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

const exportSelectedCSV = async () => {
  if (selectedIds.value.length === 0) return
  
  exporting.value = true
  try {
    const now = new Date()
    const endTime = now.toISOString()
    const past = new Date()
    past.setDate(past.getDate() - 7)
    const startTime = past.toISOString()
    
    const response = await exportBatchTelemetry(selectedIds.value, startTime, endTime)
    
    const blob = new Blob([response.data], { type: 'text/csv' })
    const link = document.createElement('a')
    link.href = window.URL.createObjectURL(blob)
    link.download = `batch_telemetry_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    selectedIds.value = []
  } catch (err) {
    console.error('Failed to export CSV:', err)
    alert('Failed to export selected telemetry CSV. Ensure the server is responsive.')
  } finally {
    exporting.value = false
  }
}

// Tab state
const activeTab = ref('endpoints')

// User management states
const users = ref([])
const usersLoading = ref(false)
const usersError = ref(null)
const displayAddUserDialog = ref(false)
const displayResetUserPasswordDialog = ref(false)
const userFormSaving = ref(false)
const targetUserId = ref(null)
const targetUsername = ref('')
const userForm = ref({ username: '', password: '', role: 'VIEWER' })
const resetPasswordForm = ref({ password: '' })

// Form states
const displayDialog = ref(false)
const displayDeleteDialog = ref(false)
const formSaving = ref(false)
const isEditing = ref(false)
const targetEndpointId = ref(null)

// Change password states
const displayChangePasswordDialog = ref(false)
const changePasswordLoading = ref(false)
const changePasswordError = ref(null)
const changePasswordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const deviceTypes = ['Server', 'Router', 'Switch', 'Access Point', 'Firewall', 'Printer', 'Other']

const form = ref({
  hostname: '',
  ip_address: '',
  device_type: 'Router',
  location: '',
  description: '',
  monitoring_enabled: true
})

const isAdmin = computed(() => user.value?.role === 'ADMIN')

const fetchUsers = async () => {
  if (!isAdmin.value) return
  usersLoading.value = true
  usersError.value = null
  try {
    const response = await getUsers()
    users.value = response.data.data || []
  } catch (err) {
    usersError.value = err.response?.data?.error?.message || 'Failed to fetch users list.'
  } finally {
    usersLoading.value = false
  }
}

const openAddUserDialog = () => {
  userForm.value = { username: '', password: '', role: 'VIEWER' }
  displayAddUserDialog.value = true
}

const saveUser = async () => {
  if (userForm.value.username.trim().length < 3) {
    alert('Username must be at least 3 characters long.')
    return
  }
  userFormSaving.value = true
  try {
    await createUser({
      username: userForm.value.username,
      password: userForm.value.password ? userForm.value.password : null,
      role: userForm.value.role
    })
    displayAddUserDialog.value = false
    await fetchUsers()
    alert('User account created successfully!')
  } catch (err) {
    alert(err.response?.data?.detail || 'Failed to create user.')
  } finally {
    userFormSaving.value = false
  }
}

const openResetPasswordDialog = (usr) => {
  targetUserId.value = usr.id
  targetUsername.value = usr.username
  resetPasswordForm.value = { password: '' }
  displayResetUserPasswordDialog.value = true
}

const executeResetUserPassword = async () => {
  userFormSaving.value = true
  try {
    await resetUserPassword(targetUserId.value, {
      password: resetPasswordForm.value.password ? resetPasswordForm.value.password : null
    })
    displayResetUserPasswordDialog.value = false
    alert(`Password reset successfully for user '${targetUsername.value}'!`)
    await fetchUsers()
  } catch (err) {
    alert(err.response?.data?.detail || 'Failed to reset user password.')
  } finally {
    userFormSaving.value = false
  }
}

const toggleUserActive = async (usr) => {
  try {
    await updateUser(usr.id, {
      is_active: !usr.is_active
    })
    await fetchUsers()
  } catch (err) {
    alert(err.response?.data?.detail || 'Failed to update user status.')
  }
}

const confirmDeleteUser = async (usr) => {
  if (confirm(`Are you sure you want to deactivate and remove user '${usr.username}'?`)) {
    try {
      await deleteUser(usr.id)
      await fetchUsers()
      alert(`User '${usr.username}' deactivated successfully.`)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to deactivate user.')
    }
  }
}

const fetchEndpoints = async () => {
  if (user.value?.must_change_password) {
    endpoints.value = []
    return
  }

  loading.value = true
  error.value = null
  try {
    const response = await getEndpoints()
    endpoints.value = response.data.data || []
    lastRefreshed.value = new Date()
    selectedIds.value = []
  } catch (err) {
    if (err.response?.status === 401) {
      localStorage.removeItem('user')
      router.push('/login')
    } else {
      error.value = err.response?.data?.error?.message || 'Failed to connect to backend engine. Verify backend is running.'
    }
  } finally {
    loading.value = false
  }
}

const navigateTo = (id) => {
  router.push(`/endpoints/${id}`)
}

const lastRefreshedLabel = computed(() => {
  if (!lastRefreshed.value) return 'never'
  return lastRefreshed.value.toLocaleTimeString()
})

// Dialog management
const openAddDialog = () => {
  isEditing.value = false
  form.value = {
    hostname: '',
    ip_address: '',
    device_type: 'Router',
    location: '',
    description: '',
    monitoring_enabled: true
  }
  displayDialog.value = true
}

const openEditDialog = (endpoint) => {
  isEditing.value = true
  targetEndpointId.value = endpoint.id
  form.value = {
    hostname: endpoint.hostname,
    ip_address: endpoint.ip_address,
    device_type: endpoint.device_type,
    location: endpoint.location || '',
    description: endpoint.description || '',
    monitoring_enabled: endpoint.monitoring_enabled
  }
  displayDialog.value = true
}

const saveEndpoint = async () => {
  formSaving.value = true
  try {
    if (isEditing.value) {
      await updateEndpoint(targetEndpointId.value, {
        hostname: form.value.hostname,
        device_type: form.value.device_type,
        location: form.value.location,
        description: form.value.description,
        monitoring_enabled: form.value.monitoring_enabled
      })
    } else {
      await createEndpoint(form.value)
    }
    displayDialog.value = false
    await fetchEndpoints()
  } catch (err) {
    alert(err.response?.data?.detail || 'Failed to save endpoint definitions.')
  } finally {
    formSaving.value = false
  }
}

const confirmDeleteEndpoint = (id) => {
  targetEndpointId.value = id
  displayDeleteDialog.value = true
}

const executeDeleteEndpoint = async () => {
  formSaving.value = true
  try {
    await deleteEndpoint(targetEndpointId.value)
    displayDeleteDialog.value = false
    await fetchEndpoints()
  } catch (err) {
    alert(err.response?.data?.detail || 'Failed to delete endpoint.')
  } finally {
    formSaving.value = false
  }
}

const executeChangePassword = async () => {
  if (changePasswordForm.value.new_password !== changePasswordForm.value.confirm_password) {
    changePasswordError.value = 'Passwords do not match.'
    return
  }
  if (changePasswordForm.value.new_password.length < 8) {
    changePasswordError.value = 'New password must be at least 8 characters long.'
    return
  }

  changePasswordLoading.value = true
  changePasswordError.value = null
  try {
    await changePassword({
      old_password: changePasswordForm.value.old_password,
      new_password: changePasswordForm.value.new_password
    })
    
    // Update local storage user details
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      const parsed = JSON.parse(storedUser)
      parsed.must_change_password = false
      localStorage.setItem('user', JSON.stringify(parsed))
      user.value = parsed
    }
    
    displayChangePasswordDialog.value = false
    await fetchEndpoints()
  } catch (err) {
    changePasswordError.value = err.response?.data?.detail || 'Failed to update password. Verify current password.'
  } finally {
    changePasswordLoading.value = false
  }
}

onMounted(async () => {
  const currentTheme = localStorage.getItem('theme') || 'dark'
  isDarkMode.value = currentTheme === 'dark'
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }

  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    try {
      user.value = JSON.parse(storedUser)
      if (user.value?.must_change_password) {
        displayChangePasswordDialog.value = true
      }
    } catch (e) {
      console.error('Failed to parse onMounted user state:', e)
    }
  }
  await fetchEndpoints()
  if (isAdmin.value) {
    await fetchUsers()
  }
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 8px;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.page-sub {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.separator {
  margin: 0 6px;
}

.toolbar-right {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

/* ── Buttons Design System ── */
.btn-primary {
  background: var(--accent);
  color: var(--text-inverse);
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: background 0.15s, opacity 0.15s;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid var(--border-color-strong);
  transition: background 0.15s;
}

.btn-secondary:hover {
  background: var(--bg-surface-selected);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger {
  background: var(--color-down);
  color: var(--text-inverse);
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: background 0.15s, opacity 0.15s;
}

.btn-danger:hover {
  background: #b91c1c;
}

.btn-small {
  padding: 6px 12px;
  font-size: 11px;
}

/* ── Tabs ── */
.dashboard-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  gap: 8px;
  margin-bottom: 12px;
}

.tab-btn {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  transition: all 0.15s ease;
  margin-bottom: -1px;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--text-primary);
  border-bottom: 2px solid var(--accent);
}

/* ── Grid ── */
.endpoint-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(1, 1fr);
}

@media (min-width: 640px) {
  .endpoint-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .endpoint-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (min-width: 1280px) {
  .endpoint-grid { grid-template-columns: repeat(4, 1fr); }
}

/* ── Alerts ── */
.alert-error {
  background: var(--color-down-bg);
  color: var(--color-down);
  border: 1px solid var(--color-down);
  padding: 12px 16px;
  border-radius: var(--radius);
  font-size: 14px;
  margin-bottom: 20px;
}

.alert-info {
  background: var(--color-unknown-bg);
  color: var(--text-primary);
  border: 1px solid var(--border-color-strong);
  padding: 12px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  margin-bottom: 16px;
  font-weight: 500;
}

.warning-alert {
  background: var(--color-up-unstable-bg);
  color: var(--color-up-unstable);
  border-color: var(--color-up-unstable);
}

/* ── Empty States ── */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.empty-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.empty-sub {
  color: var(--text-muted);
  margin: 0;
  font-size: 13px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Tables Redesign ── */
.table-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
}

.audit-table th {
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  font-weight: 600;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.05em;
}

.audit-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}

.audit-table tr:last-child td {
  border-bottom: none;
}

.audit-table tr:hover td {
  background: var(--bg-surface-hover);
}

.self-row td {
  background: var(--bg-surface-selected);
}

.self-tag {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 4px;
}

.role-badge {
  font-family: monospace;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

/* Row Action Buttons */
.actions-header {
  text-align: right !important;
}

.actions-col {
  text-align: right;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-action-warning {
  background: transparent;
  color: var(--color-up-unstable);
  border: 1px solid var(--color-up-unstable);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.15s;
}

.btn-action-warning:hover {
  background: var(--color-up-unstable-bg);
}

.btn-action-danger {
  background: transparent;
  color: var(--color-down);
  border: 1px solid var(--color-down);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.15s;
}

.btn-action-danger:hover {
  background: var(--color-down-bg);
}

.btn-action-success {
  background: transparent;
  color: var(--color-up);
  border: 1px solid var(--color-up);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.15s;
}

.btn-action-success:hover {
  background: var(--color-up-bg);
}

/* ── Contextual Floating Selection Banner ── */
.selection-banner {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-surface);
  border: 1px solid var(--accent);
  box-shadow: var(--shadow-hover);
  border-radius: var(--radius);
  padding: 12px 24px;
  z-index: 150;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 20px;
  white-space: nowrap;
}

.selection-count {
  font-size: 13px;
  color: var(--text-primary);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 15px);
}

/* ── Unified Native Modals Overlays ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 20px;
  backdrop-filter: blur(2px);
}

.modal {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  width: 100%;
  max-width: 460px;
  box-shadow: var(--shadow-hover);
  animation: modal-slide-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

@keyframes modal-slide-in {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.modal-close {
  font-size: 20px;
  color: var(--text-muted);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: var(--bg-surface-selected);
  color: var(--text-primary);
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 70vh;
  overflow-y: auto;
}

.text-center {
  text-align: center;
}

.modal-alert-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.warning-subtext {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.checkbox-form-group {
  flex-direction: row !important;
  align-items: center;
  gap: 8px !important;
  margin-top: 4px;
}

.checkbox-form-group input {
  width: 14px;
  height: 14px;
  accent-color: var(--accent);
  cursor: pointer;
}

.checkbox-form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.form-input {
  background: var(--bg-app);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
  width: 100%;
  outline: none;
}

.form-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--bg-surface-selected);
}

.form-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  min-height: 70px;
}

.form-help {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: -2px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-surface-hover);
}

.full-width-btn {
  width: 100%;
  text-align: center;
  justify-content: center;
}
</style>
