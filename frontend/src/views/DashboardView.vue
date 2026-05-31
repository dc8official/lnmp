<template>
  <div class="dashboard-wrapper">
    <!-- Navigation / Header Bar -->
    <header class="app-nav">
      <div class="brand">
        <i class="pi pi-shield brand-icon"></i>
        <span>lnmp Monitoring</span>
      </div>
      <div class="user-profile" v-if="user">
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

      <div v-else class="endpoint-grid">
        <EndpointCard 
          v-for="endpoint in endpoints" 
          :key="endpoint.id" 
          :endpoint="endpoint" 
          :isAdmin="isAdmin"
          @select="navigateToEndpoint"
          @edit="openEditDialog"
          @delete="confirmDeleteEndpoint"
        />
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
  logout 
} from '../services/api.js'
import EndpointCard from '../components/EndpointCard.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import Checkbox from 'primevue/checkbox'

const router = useRouter()
const endpoints = ref([])
const loading = ref(false)
const error = ref(null)
const lastRefreshed = ref(null)
const user = ref(null)

// Form states
const displayDialog = ref(false)
const displayDeleteDialog = ref(false)
const formSaving = ref(false)
const isEditing = ref(false)
const targetEndpointId = ref(null)

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
const dialogHeader = computed(() => isEditing.value ? 'Modify Endpoint' : 'Register Endpoint')

const fetchEndpoints = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await getEndpoints()
    endpoints.value = response.data.data
    lastRefreshed.value = new Date()
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

onMounted(() => {
  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    user.value = JSON.parse(storedUser)
  }
  fetchEndpoints()
})
</script>

<style scoped>
.dashboard-wrapper {
  min-height: 100vh;
  background-color: #f8fafc;
}
.app-nav {
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  padding: 0.75rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 700;
  font-size: 1.1rem;
  color: #0f172a;
}
.brand-icon {
  color: #049f6c;
}
.user-profile {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.user-badge {
  font-size: 0.8rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-weight: 600;
}
.user-badge.admin {
  background-color: rgba(4, 159, 108, 0.1);
  color: #049f6c;
}
.user-badge.viewer {
  background-color: #f1f5f9;
  color: #64748b;
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
  font-size: 1.8rem;
  color: #0f172a;
  margin-bottom: 0.25rem;
}
.subtitle {
  color: #64748b;
  font-size: 0.95rem;
}
.error-message {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background-color: #fee2e2;
  color: #b91c1c;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border-left: 4px solid #ef4444;
}
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  padding: 4rem 0;
  gap: 1rem;
}
.spinner-icon {
  font-size: 2.5rem;
  color: #049f6c;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4rem 2rem;
  text-align: center;
  background-color: white;
  border-radius: 12px;
  border: 1px dashed #cbd5e1;
  color: #64748b;
}
.empty-icon {
  font-size: 3rem;
  color: #94a3b8;
  margin-bottom: 1rem;
}
.empty-state h3 {
  color: #0f172a;
  margin-bottom: 0.5rem;
}
.endpoint-grid {
  display: grid;
  gap: 1.5rem;
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
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}
.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
}
.checkbox-group label {
  font-weight: 500;
  cursor: pointer;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid #f1f5f9;
  padding-top: 1rem;
}
.delete-confirm-content {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.5rem 0;
}
.warning-icon {
  font-size: 2.5rem;
  color: #ef4444;
}
.warning-subtext {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-top: 0.25rem;
}
:deep(.p-dropdown), :deep(.p-inputtext), :deep(.p-textarea) {
  width: 100%;
}
</style>
