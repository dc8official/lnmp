<template>
  <div class="dashboard-wrapper">
    <!-- Navigation / Header Bar -->
    <header class="app-nav">
      <div class="brand">
        <i class="pi pi-shield brand-icon"></i>
        <span>lnmp <span class="version-tag">v1(beta)</span> Monitoring</span>
      </div>
      <div class="user-profile" v-if="user">
        <Button
          :icon="isDarkMode ? 'pi pi-sun' : 'pi pi-moon'"
          @click="toggleTheme"
          text
          severity="secondary"
          size="small"
          class="theme-toggle-btn"
          style="color: #A3A3A3 !important; padding: 0.25rem !important;"
        />
        <span class="user-badge" :class="user.role.toLowerCase()">
          {{ user.username }} ({{ user.role }})
        </span>
        <Button 
          icon="pi pi-sign-out" 
          label="Sign Out" 
          @click="handleLogout" 
          severity="danger" 
          text
          size="small"
        />
      </div>
    </header>

    <div class="dashboard-container">
      <!-- Tabs toggle for Admins -->
      <div class="dashboard-tabs" v-if="isAdmin">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'endpoints' }" 
          @click="activeTab = 'endpoints'"
        >
          <i class="pi pi-server tab-icon"></i>
          <span>Monitored Endpoints</span>
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'users' }" 
          @click="activeTab = 'users'"
        >
          <i class="pi pi-users tab-icon"></i>
          <span>User Management</span>
        </button>
      </div>

      <!-- Endpoints Tab Content -->
      <div v-if="activeTab === 'endpoints'">
        <header class="dashboard-header">
          <div class="header-info">
            <h1>Network Dashboard</h1>
            <p class="subtitle" v-if="!loading && !error">
              Active Endpoints: <strong>{{ endpoints.length }}</strong> | Last sync: {{ lastRefreshedTime }}
            </p>
          </div>
          <div class="action-buttons">
            <Button 
              v-if="isAdmin"
              icon="pi pi-plus" 
              label="Add Endpoint" 
              @click="openAddDialog" 
              severity="success"
            />
            <Button 
              icon="pi pi-refresh" 
              label="Refresh" 
              @click="fetchEndpoints" 
              :loading="loading"
              severity="secondary"
            />
          </div>
        </header>

        <div v-if="error" class="error-message">
          <i class="pi pi-exclamation-triangle"></i>
          <span>{{ error }}</span>
        </div>

        <div v-else-if="loading && endpoints.length === 0" class="loading-state">
          <i class="pi pi-spin pi-spinner spinner-icon"></i>
          <p>Synchronizing network status...</p>
        </div>

        <div v-else-if="endpoints.length === 0" class="empty-state">
          <i class="pi pi-search empty-icon"></i>
          <h3>No endpoints found</h3>
          <p v-if="isAdmin">Click "Add Endpoint" to register your first monitored host.</p>
          <p v-else>Please contact the system administrator to configure monitored nodes.</p>
        </div>

        <div v-else>
          <!-- Dynamic Selection Contextual Banner -->
          <transition name="fade">
            <div v-if="selectedIds.length > 0" class="selection-banner">
              <div class="banner-content">
                <span class="selection-count">
                  <i class="pi pi-check-circle selection-icon"></i>
                  <strong>{{ selectedIds.length }}</strong> target(s) selected for CSV export
                </span>
                <Button 
                  label="Export Selected CSV" 
                  icon="pi pi-download" 
                  size="small" 
                  class="export-btn"
                  :loading="exporting"
                  @click="exportSelectedCSV"
                />
              </div>
            </div>
          </transition>

          <div class="endpoint-grid">
            <EndpointCard 
              v-for="endpoint in endpoints" 
              :key="endpoint.id" 
              :endpoint="endpoint" 
              :isAdmin="isAdmin"
              :selected="selectedIds.includes(endpoint.id)"
              @select="navigateToEndpoint"
              @toggle-select="toggleEndpointSelect"
              @edit="openEditDialog"
              @delete="confirmDeleteEndpoint"
            />
          </div>
        </div>
      </div>

      <!-- User Management Tab Content (Admin Only) -->
      <div v-else-if="activeTab === 'users' && isAdmin">
        <header class="dashboard-header">
          <div class="header-info">
            <h1>User Accounts</h1>
            <p class="subtitle">
              Manage platform users, update role privileges, and execute password resets.
            </p>
          </div>
          <div class="action-buttons">
            <Button 
              icon="pi pi-user-plus" 
              label="Add User" 
              @click="openAddUserDialog" 
              severity="success"
            />
            <Button 
              icon="pi pi-refresh" 
              label="Refresh" 
              @click="fetchUsers" 
              :loading="usersLoading"
              severity="secondary"
            />
          </div>
        </header>

        <div v-if="usersError" class="error-message">
          <i class="pi pi-exclamation-triangle"></i>
          <span>{{ usersError }}</span>
        </div>

        <div v-else-if="usersLoading && users.length === 0" class="loading-state">
          <i class="pi pi-spin pi-spinner spinner-icon"></i>
          <p>Loading user list...</p>
        </div>

        <div v-else class="users-list-wrapper">
          <div class="users-table-card">
            <table class="users-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Credentials State</th>
                  <th>Last Signed In</th>
                  <th>Created Date</th>
                  <th class="actions-header">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="usr in users" :key="usr.id" :class="{ 'self-row': usr.id === user?.id }">
                  <td class="username-col">
                    <i class="pi pi-user user-row-icon"></i>
                    <span>{{ usr.username }}</span>
                    <span v-if="usr.id === user?.id" class="self-tag">(You)</span>
                  </td>
                  <td>
                    <span class="user-badge" :class="usr.role.toLowerCase()">
                      {{ usr.role }}
                    </span>
                  </td>
                  <td>
                    <span class="status-indicator" :class="{ active: usr.is_active }">
                      <span class="dot"></span>
                      {{ usr.is_active ? 'Active' : 'Disabled' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="usr.must_change_password" class="reset-alert-badge">
                      <i class="pi pi-key"></i> Password Reset Pending
                    </span>
                    <span v-else class="reset-ok-badge">
                      <i class="pi pi-check-circle"></i> Secure
                    </span>
                  </td>
                  <td class="date-col">
                    {{ usr.last_login ? new Date(usr.last_login).toLocaleString() : 'Never' }}
                  </td>
                  <td class="date-col">
                    {{ new Date(usr.created_at).toLocaleDateString() }}
                  </td>
                  <td class="actions-col">
                    <Button 
                      icon="pi pi-lock-open" 
                      label="Reset Pass" 
                      size="small" 
                      severity="warning" 
                      text 
                      @click="openResetPasswordDialog(usr)"
                    />
                    <Button 
                      v-if="usr.id !== user?.id"
                      :icon="usr.is_active ? 'pi pi-ban' : 'pi pi-check'" 
                      :label="usr.is_active ? 'Disable' : 'Enable'" 
                      size="small" 
                      :severity="usr.is_active ? 'danger' : 'success'" 
                      text 
                      @click="toggleUserActive(usr)"
                    />
                    <Button 
                      v-if="usr.id !== user?.id"
                      icon="pi pi-trash" 
                      size="small" 
                      severity="danger" 
                      text 
                      @click="confirmDeleteUser(usr)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Add / Edit Dialog -->
    <Dialog 
      v-model:visible="displayDialog" 
      :header="dialogHeader" 
      modal 
      :style="{ width: '480px' }" 
      class="custom-dialog"
    >
      <form @submit.prevent="saveEndpoint" class="endpoint-form">
        <div class="form-grid">
          <div class="form-group">
            <label for="hostname">Hostname *</label>
            <InputText id="hostname" v-model="form.hostname" placeholder="e.g. core-router.local" required />
          </div>

          <div class="form-group">
            <label for="ip_address">IP Address *</label>
            <InputText id="ip_address" v-model="form.ip_address" placeholder="e.g. 192.168.1.1" required :disabled="isEditing" />
          </div>

          <div class="form-group">
            <label for="device_type">Device Type *</label>
            <Dropdown 
              id="device_type" 
              v-model="form.device_type" 
              :options="deviceTypes" 
              placeholder="Select device type"
              required 
            />
          </div>

          <div class="form-group">
            <label for="location">Location</label>
            <InputText id="location" v-model="form.location" placeholder="e.g. Datacenter rack A5" />
          </div>

          <div class="form-group full-width">
            <label for="description">Description</label>
            <Textarea id="description" v-model="form.description" rows="3" placeholder="Additional endpoint metadata" autoResize />
          </div>

          <div class="form-group checkbox-group full-width">
            <Checkbox id="monitoring_enabled" v-model="form.monitoring_enabled" :binary="true" />
            <label for="monitoring_enabled">Enable automated uptime checks</label>
          </div>
        </div>

        <div class="dialog-footer">
          <Button label="Cancel" icon="pi pi-times" severity="secondary" text @click="displayDialog = false" />
          <Button type="submit" label="Save" icon="pi pi-check" :loading="formSaving" severity="success" />
        </div>
      </form>
    </Dialog>

    <!-- Delete Confirmation Dialog -->
    <Dialog 
      v-model:visible="displayDeleteDialog" 
      header="Confirm Deletion" 
      modal 
      :style="{ width: '400px' }"
    >
      <div class="delete-confirm-content">
        <i class="pi pi-exclamation-triangle warning-icon"></i>
        <div>
          <p>Are you sure you want to delete this endpoint?</p>
          <p class="warning-subtext">This action will stop active monitoring and is irreversible.</p>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" icon="pi pi-times" severity="secondary" text @click="displayDeleteDialog = false" />
        <Button label="Delete" icon="pi pi-trash" :loading="formSaving" severity="danger" @click="executeDeleteEndpoint" />
      </template>
    </Dialog>

    <!-- Forced Password Change Dialog (Initial Setup) -->
    <Dialog 
      v-model:visible="displayChangePasswordDialog" 
      header="Initial Setup — Password Reset Required" 
      modal 
      :closable="false"
      :style="{ width: '420px' }"
      class="forced-password-dialog"
    >
      <form @submit.prevent="executeChangePassword" class="endpoint-form">
        <div class="info-alert">
          <i class="pi pi-info-circle"></i>
          <span>For security reasons, you are required to change your default password on your initial sign-in.</span>
        </div>

        <div v-if="changePasswordError" class="error-container">
          <Message severity="error" :closable="false">{{ changePasswordError }}</Message>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label for="old_password">Current Password *</label>
            <Password 
              id="old_password" 
              v-model="changePasswordForm.old_password" 
              placeholder="Enter current password"
              :feedback="false" 
              toggleMask 
              required 
              :disabled="changePasswordLoading"
              class="full-width-password"
              inputClass="full-width"
            />
          </div>

          <div class="form-group">
            <label for="new_password">New Password *</label>
            <Password 
              id="new_password" 
              v-model="changePasswordForm.new_password" 
              placeholder="Enter new password (min 8 chars)"
              toggleMask 
              required 
              :disabled="changePasswordLoading"
              class="full-width-password"
              inputClass="full-width"
            />
          </div>

          <div class="form-group">
            <label for="confirm_password">Confirm New Password *</label>
            <Password 
              id="confirm_password" 
              v-model="changePasswordForm.confirm_password" 
              placeholder="Confirm new password"
              :feedback="false" 
              toggleMask 
              required 
              :disabled="changePasswordLoading"
              class="full-width-password"
              inputClass="full-width"
            />
          </div>
        </div>

        <div class="dialog-footer">
          <Button 
            type="submit" 
            label="Update Password & Sign In" 
            icon="pi pi-check" 
            :loading="changePasswordLoading" 
            severity="success" 
            class="full-width-btn"
          />
        </div>
      </form>
    </Dialog>

    <!-- Add User Dialog (Admin Only) -->
    <Dialog 
      v-model:visible="displayAddUserDialog" 
      header="Register New User Account" 
      modal 
      :style="{ width: '440px' }" 
      class="custom-dialog"
    >
      <form @submit.prevent="saveUser" class="endpoint-form">
        <div class="form-grid">
          <div class="form-group">
            <label for="new_username">Username *</label>
            <InputText id="new_username" v-model="userForm.username" placeholder="Enter username (min 3 chars)" required />
          </div>

          <div class="form-group">
            <label for="new_user_password">Password</label>
            <InputText type="password" id="new_user_password" v-model="userForm.password" placeholder="Defaults to 'password123' if blank" />
            <small class="form-help">The new user will be required to change this password on their initial login.</small>
          </div>

          <div class="form-group">
            <label for="new_user_role">Privilege Role *</label>
            <Dropdown 
              id="new_user_role" 
              v-model="userForm.role" 
              :options="['VIEWER', 'ADMIN']" 
              placeholder="Select privilege tier"
              required 
            />
          </div>
        </div>

        <div class="dialog-footer">
          <Button label="Cancel" icon="pi pi-times" severity="secondary" text @click="displayAddUserDialog = false" />
          <Button type="submit" label="Register User" icon="pi pi-user-plus" :loading="userFormSaving" severity="success" />
        </div>
      </form>
    </Dialog>

    <!-- Reset User Password Dialog (Admin Only) -->
    <Dialog 
      v-model:visible="displayResetUserPasswordDialog" 
      :header="`Reset Password — ${targetUsername}`" 
      modal 
      :style="{ width: '400px' }" 
      class="custom-dialog"
    >
      <form @submit.prevent="executeResetUserPassword" class="endpoint-form">
        <div class="form-grid">
          <div class="info-alert warning-alert">
            <i class="pi pi-exclamation-triangle"></i>
            <span>This will immediately invalidate the current password for <strong>{{ targetUsername }}</strong>. They will be forced to set a new password on their next sign-in.</span>
          </div>

          <div class="form-group">
            <label for="reset_user_password">New Temporary Password</label>
            <InputText type="password" id="reset_user_password" v-model="resetPasswordForm.password" placeholder="Defaults to 'password123' if blank" />
            <small class="form-help">Enter a temporary password or leave blank for 'password123'.</small>
          </div>
        </div>

        <div class="dialog-footer">
          <Button label="Cancel" icon="pi pi-times" severity="secondary" text @click="displayResetUserPasswordDialog = false" />
          <Button type="submit" label="Reset Password" icon="pi pi-lock-open" :loading="userFormSaving" severity="warning" />
        </div>
      </form>
    </Dialog>
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
  logout,
  exportBatchTelemetry
} from '../services/api.js'
import EndpointCard from '../components/EndpointCard.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import Checkbox from 'primevue/checkbox'
import Password from 'primevue/password'
import Message from 'primevue/message'

const router = useRouter()
const isDarkMode = ref(true)

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  if (isDarkMode.value) {
    localStorage.setItem('theme', 'dark')
    document.body.classList.add('dark-mode')
    document.body.classList.remove('light-mode')
  } else {
    localStorage.setItem('theme', 'light')
    document.body.classList.add('light-mode')
    document.body.classList.remove('dark-mode')
  }
}

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
  device_type: '',
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
    users.value = response.data.data
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
const dialogHeader = computed(() => isEditing.value ? 'Modify Endpoint' : 'Register Endpoint')

const fetchEndpoints = async () => {
  // If forced to change password, suspend API loading to avoid token-expire errors
  if (user.value?.must_change_password) {
    endpoints.value = []
    return
  }

  loading.value = true
  error.value = null
  try {
    const response = await getEndpoints()
    endpoints.value = response.data.data
    lastRefreshed.value = new Date()
    selectedIds.value = []
  } catch (err) {
    if (err.response?.status === 401) {
      handleLogoutLocal()
    } else {
      error.value = err.response?.data?.error?.message || 'Failed to connect to backend engine. Verify backend is running.'
    }
  } finally {
    loading.value = false
  }
}

const navigateToEndpoint = (id) => {
  router.push(`/endpoints/${id}`)
}

const lastRefreshedTime = computed(() => {
  if (!lastRefreshed.value) return 'Never'
  return lastRefreshed.value.toLocaleTimeString()
})

const handleLogoutLocal = () => {
  localStorage.removeItem('user')
  router.push('/login')
}

const handleLogout = async () => {
  try {
    await logout()
  } catch (err) {
    console.error('Logout error on backend', err)
  } finally {
    handleLogoutLocal()
  }
}

// Dialog management
const openAddDialog = () => {
  isEditing.value = false
  form.value = {
    hostname: '',
    ip_address: '',
    device_type: '',
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

// Forced password change logic
const executeChangePassword = async () => {
  if (changePasswordForm.value.new_password !== changePasswordForm.value.confirm_password) {
    changePasswordError.value = 'New passwords do not match.'
    return
  }
  if (changePasswordForm.value.new_password.length < 8) {
    changePasswordError.value = 'Password must be at least 8 characters long.'
    return
  }
  if (changePasswordForm.value.new_password.toLowerCase() === 'admin') {
    changePasswordError.value = 'Password cannot be set to the default "admin" password.'
    return
  }

  changePasswordLoading.value = true
  changePasswordError.value = null

  try {
    await changePassword({
      old_password: changePasswordForm.value.old_password,
      new_password: changePasswordForm.value.new_password
    })

    // Reset MUST change password locally and fetch endpoints
    user.value.must_change_password = false
    localStorage.setItem('user', JSON.stringify(user.value))
    displayChangePasswordDialog.value = false
    
    alert('Password updated successfully! Welcome to your dashboard.')
    await fetchEndpoints()
  } catch (err) {
    changePasswordError.value = err.response?.data?.detail || 'Failed to change password. Verify your current password is correct.'
  } finally {
    changePasswordLoading.value = false
  }
}

onMounted(() => {
  const currentTheme = localStorage.getItem('theme') || 'dark'
  isDarkMode.value = currentTheme === 'dark'

  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    user.value = JSON.parse(storedUser)
    if (user.value.must_change_password) {
      displayChangePasswordDialog.value = true
    }
  }
  fetchEndpoints()
  if (isAdmin.value) {
    fetchUsers()
  }
})
</script>

<style scoped>
.dashboard-wrapper {
  min-height: 100vh;
  background-color: var(--canvas-bg);
}
.app-nav {
  background-color: var(--card-bg);
  border-bottom: 1px solid var(--card-border);
  padding: 0.75rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: none;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 700;
  font-size: 1.1rem;
  color: #FFFFFF;
}
.brand-icon {
  color: #A3A3A3;
}
.user-profile {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.user-badge {
  font-size: 0.8rem;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-weight: 600;
  border: 1px solid #262626;
}
.user-badge.admin {
  background-color: #000000;
  color: #FFFFFF;
}
.user-badge.viewer {
  background-color: #000000;
  color: #A3A3A3;
}
.dashboard-container {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.action-buttons {
  display: flex;
  gap: 0.75rem;
}
h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: #FFFFFF;
  margin-bottom: 0.25rem;
  letter-spacing: -0.02em;
}
.subtitle {
  color: #A3A3A3;
  font-size: 0.9rem;
}
.error-message {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background-color: #000000;
  color: #FF0000;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
  border: 1px solid #262626;
  border-left: 4px solid #FF0000;
  font-size: 0.9rem;
  font-weight: 600;
}
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #A3A3A3;
  padding: 6rem 0;
  gap: 1rem;
}
.spinner-icon {
  font-size: 2rem;
  color: #FFFFFF;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4rem 2rem;
  text-align: center;
  background-color: #000000;
  border-radius: 4px;
  border: 1px dashed #262626;
  color: #A3A3A3;
}
.empty-icon {
  font-size: 2.5rem;
  color: #A3A3A3;
  margin-bottom: 1rem;
}
.empty-state h3 {
  color: #FFFFFF;
  margin-bottom: 0.5rem;
}
.endpoint-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(1, 1fr);
}

@media (min-width: 768px) {
  .endpoint-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (min-width: 1024px) {
  .endpoint-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Dialog and Form styling */
.endpoint-form {
  padding: 0.5rem 0 0 0;
}
.form-grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.form-group label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #A3A3A3;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
}
.checkbox-group label {
  font-weight: 600;
  cursor: pointer;
  color: #FFFFFF;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid #262626;
  padding-top: 1rem;
}
.delete-confirm-content {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.5rem 0;
}
.warning-icon {
  font-size: 2rem;
  color: #FF0000;
}
.warning-subtext {
  font-size: 0.8rem;
  color: #A3A3A3;
  margin-top: 0.25rem;
}

/* Forced password reset styling */
.info-alert {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background-color: #000000;
  color: #FFFFFF;
  padding: 0.85rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 1.25rem;
  border: 1px solid #262626;
  border-left: 3px solid #FFFFFF;
}
.error-container {
  margin-bottom: 1rem;
}
.full-width-btn {
  width: 100%;
  padding: 0.65rem !important;
  font-weight: 700 !important;
}

/* PrimeVue Component Overrides */
:deep(.p-dropdown), :deep(.p-inputtext), :deep(.p-textarea) {
  width: 100%;
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  color: #FFFFFF !important;
  border-radius: 4px !important;
  outline: none !important;
}
:deep(.p-dropdown:focus), :deep(.p-inputtext:focus), :deep(.p-textarea:focus) {
  border-color: #A3A3A3 !important;
}
:deep(.p-dropdown-panel) {
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  color: #FFFFFF !important;
}
:deep(.p-dropdown-item) {
  color: #A3A3A3 !important;
}
:deep(.p-dropdown-item:hover), :deep(.p-dropdown-item.p-highlight) {
  color: #FFFFFF !important;
  background-color: rgba(255,255,255,0.08) !important;
}
:deep(.p-dialog) {
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  color: #FFFFFF !important;
  box-shadow: none !important;
  border-radius: 4px !important;
}
:deep(.p-dialog-header), :deep(.p-dialog-content), :deep(.p-dialog-footer) {
  background-color: #000000 !important;
  color: #FFFFFF !important;
  border: none !important;
}
:deep(.p-dialog-title) {
  color: #FFFFFF !important;
  font-weight: 700 !important;
  font-size: 1.1rem !important;
}
:deep(.p-button.p-button-success) {
  background-color: #FFFFFF !important;
  border-color: #FFFFFF !important;
  color: #000000 !important;
  border-radius: 4px !important;
  font-weight: 700 !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
:deep(.p-button.p-button-success:hover) {
  background-color: #A3A3A3 !important;
  border-color: #A3A3A3 !important;
}
:deep(.p-button.p-button-secondary) {
  background-color: #000000 !important;
  border-color: #262626 !important;
  color: #A3A3A3 !important;
  border-radius: 4px !important;
}
:deep(.p-button.p-button-secondary:hover) {
  color: #FFFFFF !important;
  border-color: #A3A3A3 !important;
}
:deep(.p-button.p-button-danger) {
  background-color: #FF0000 !important;
  border-color: #FF0000 !important;
  color: #FFFFFF !important;
  border-radius: 4px !important;
  font-weight: 700 !important;
}
:deep(.p-button.p-button-danger:hover) {
  background-color: #CC0000 !important;
  border-color: #CC0000 !important;
}
:deep(.p-checkbox-box) {
  background-color: #000000 !important;
  border: 1px solid #262626 !important;
  border-radius: 4px !important;
}
:deep(.p-checkbox-checked .p-checkbox-box) {
  background-color: #FFFFFF !important;
  border-color: #FFFFFF !important;
  color: #000000 !important;
}
.full-width-password {
  width: 100%;
}
:deep(.full-width-password input) {
  width: 100%;
}

/* Tabs styling */
.dashboard-tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid #262626;
  margin-bottom: 2rem;
  padding-bottom: 0.1px;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #A3A3A3;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.15s ease;
  outline: none;
}
.tab-btn:hover {
  color: #FFFFFF;
}
.tab-btn.active {
  color: #FFFFFF;
  border-bottom-color: #FFFFFF;
}
.tab-icon {
  font-size: 1rem;
}

/* User table styling */
.users-list-wrapper {
  margin-top: 1.5rem;
}
.users-table-card {
  background-color: var(--card-bg);
  border-radius: 4px;
  border: 1px solid var(--card-border);
  box-shadow: none;
  overflow-x: auto;
}
.users-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
}
.users-table th {
  background-color: #0A0A0A;
  color: #A3A3A3;
  font-weight: 700;
  padding: 1rem 1.5rem;
  border-bottom: 2px solid #262626;
  white-space: nowrap;
}
.users-table td {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #262626;
  color: #FFFFFF;
  vertical-align: middle;
}
.users-table tbody tr:last-child td {
  border-bottom: none;
}
.users-table tr.self-row {
  background-color: rgba(255, 255, 255, 0.02);
}
.users-table tr:hover {
  background-color: #0A0A0A;
}
.username-col {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 700;
}
.user-row-icon {
  color: #A3A3A3;
}
.self-tag {
  font-size: 0.7rem;
  color: #FFFFFF;
  border: 1px solid #262626;
  background-color: #0A0A0A;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  background-color: transparent;
  color: #A3A3A3;
  border: 1px solid #262626;
  text-transform: uppercase;
}
.status-indicator.active {
  color: #FFFFFF;
}
.status-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #FF0000;
}
.status-indicator.active .dot {
  background-color: #588157;
}
.reset-alert-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  background-color: transparent;
  color: #F59E0B;
  border: 1px solid #262626;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}
.reset-ok-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  background-color: transparent;
  color: #FFFFFF;
  border: 1px solid #262626;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}
.date-col {
  color: #A3A3A3;
  font-size: 0.8rem;
  font-family: monospace;
}
.actions-header {
  text-align: right;
}
.actions-col {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.warning-alert {
  background-color: #000000 !important;
  color: #F59E0B !important;
  border: 1px solid #262626 !important;
  border-left: 3px solid #F59E0B !important;
}
.form-help {
  font-size: 0.75rem;
  color: #A3A3A3;
  margin-top: 0.25rem;
}

/* ==========================================================================
   Light Mode Theme Scoping Overrides
   ========================================================================== */
:global(body.light-mode) .dashboard-wrapper {
  background-color: #ffffff;
}
:global(body.light-mode) .app-nav {
  background-color: #ffffff;
  border-bottom: 1px solid #cbd5e1;
}
:global(body.light-mode) .brand {
  color: #0f172a;
}
:global(body.light-mode) .brand-icon {
  color: #0f172a;
}
:global(body.light-mode) .user-badge.admin {
  background-color: rgba(4, 159, 108, 0.08);
  color: #049f6c;
  border: 1px solid rgba(4, 159, 108, 0.15);
}
:global(body.light-mode) .user-badge.viewer {
  background-color: #f1f5f9;
  color: #475569;
  border: 1px solid #cbd5e1;
}
:global(body.light-mode) .stat-card,
:global(body.light-mode) .users-table-card,
:global(body.light-mode) .incident-ticker {
  background-color: #fafafa !important;
  border: 1px solid #cbd5e1 !important;
}

.version-tag {
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--text-muted, #737373);
  margin-left: 0.25rem;
  font-weight: 500;
  text-transform: none;
}
:global(body.light-mode) .stat-value {
  color: #0f172a;
}
:global(body.light-mode) .stat-title {
  color: #475569;
}
:global(body.light-mode) .stat-desc {
  color: #64748b;
}
:global(body.light-mode) .section-header h2 {
  color: #0f172a;
}
:global(body.light-mode) .refresh-text {
  color: #475569;
}
:global(body.light-mode) .dashboard-tabs {
  border-bottom: 1px solid #cbd5e1;
}
:global(body.light-mode) .tab-btn {
  color: #475569;
}
:global(body.light-mode) .tab-btn:hover {
  color: #0f172a;
}
:global(body.light-mode) .tab-btn.active {
  color: #049f6c;
  border-bottom-color: #049f6c;
}
:global(body.light-mode) .users-table th {
  background-color: #f8fafc;
  color: #475569;
  border-bottom: 2px solid #e2e8f0;
}
:global(body.light-mode) .users-table td {
  color: #334155;
  border-bottom: 1px solid #e2e8f0;
}
:global(body.light-mode) .users-table tr.self-row {
  background-color: rgba(4, 159, 108, 0.02);
}
:global(body.light-mode) .users-table tr:hover {
  background-color: #f8fafc;
}
:global(body.light-mode) .self-tag {
  color: #049f6c;
  background-color: rgba(4, 159, 108, 0.08);
  border: 1px solid rgba(4, 159, 108, 0.15);
}
:global(body.light-mode) .status-indicator {
  color: #475569;
  background-color: #f1f5f9;
  border: 1px solid #cbd5e1;
}
:global(body.light-mode) .status-indicator.active {
  color: #049f6c;
  background-color: rgba(4, 159, 108, 0.08);
  border: 1px solid rgba(4, 159, 108, 0.15);
}
:global(body.light-mode) .date-col {
  color: #475569;
}
:global(body.light-mode) .warning-alert {
  background-color: #fffbeb !important;
  color: #b45309 !important;
  border: 1px solid #fef3c7 !important;
  border-left: 3px solid #f59e0b !important;
}
:global(body.light-mode) .form-help {
  color: #64748b;
}

/* Light mode PrimeVue overrides */
:global(body.light-mode) :deep(.p-button) {
  background-color: #ffffff !important;
  border: 1px solid #cbd5e1 !important;
  color: #475569 !important;
}
:global(body.light-mode) :deep(.p-button:hover) {
  background-color: #f8fafc !important;
  border-color: #94a3b8 !important;
  color: #0f172a !important;
}
:global(body.light-mode) :deep(.p-button:not(.p-button-outlined)) {
  background-color: #0f172a !important;
  border-color: #0f172a !important;
  color: #ffffff !important;
}
:global(body.light-mode) :deep(.p-button:not(.p-button-outlined):hover) {
  background-color: #334155 !important;
  border-color: #334155 !important;
  color: #ffffff !important;
}
:global(body.light-mode) :deep(.p-button-danger) {
  background-color: #fef2f2 !important;
  border-color: #fee2e2 !important;
  color: #ef4444 !important;
}
:global(body.light-mode) :deep(.p-button-danger:hover) {
  background-color: #fef2f2 !important;
  border-color: #fca5a5 !important;
}
:global(body.light-mode) :deep(.p-inputtext) {
  background-color: #ffffff !important;
  border: 1px solid #cbd5e1 !important;
  color: #0f172a !important;
}
:global(body.light-mode) :deep(.p-inputtext:focus) {
  border-color: #049f6c !important;
}
:global(body.light-mode) :deep(.p-dialog) {
  background-color: #ffffff !important;
  border: 1px solid #cbd5e1 !important;
  color: #0f172a !important;
  box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1) !important;
}
:global(body.light-mode) :deep(.p-dialog-header),
:global(body.light-mode) :deep(.p-dialog-content),
:global(body.light-mode) :deep(.p-dialog-footer) {
  background-color: #ffffff !important;
  color: #0f172a !important;
}

:global(body.light-mode) .selection-icon {
  color: #0f172a !important;
}

/* Selection Contextual Banner Styles */
.selection-banner {
  background-color: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 4px;
  padding: 0.75rem 1.5rem;
  margin-bottom: 1.5rem;
  font-family: monospace;
  font-size: 0.85rem;
  transition: all 0.2s ease;
}

.banner-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selection-count {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-primary);
}

.selection-icon {
  color: #049f6c;
}

.export-btn {
  background-color: #049f6c !important;
  border-color: #049f6c !important;
  color: #ffffff !important;
}

.export-btn:hover {
  background-color: #037f56 !important;
  border-color: #037f56 !important;
}

/* fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
