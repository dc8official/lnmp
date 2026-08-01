<template>
  <div class="endpoints-view">
    <!-- Header Toolbar -->
    <div class="view-header">
      <div>
        <h1 class="page-title">Monitored Endpoints & Governance</h1>
        <p class="page-sub">Manage network targets, differential RCA engine, and route discovery governance</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="fetchEndpoints" :disabled="loading">
          {{ loading ? 'Refreshing...' : '↻ Refresh List' }}
        </button>
        <button class="btn-primary" @click="openCreateModal">
          + Add Endpoint
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert-error">
      {{ error }}
    </div>

    <!-- Endpoints Table -->
    <div class="table-card">
      <div v-if="loading && endpoints.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Loading endpoints...</p>
      </div>

      <div v-else-if="endpoints.length === 0" class="empty-state">
        <p>No endpoints configured. Click "+ Add Endpoint" to create your first monitored node.</p>
      </div>

      <table v-else class="data-table">
        <thead>
          <tr>
            <th>Hostname / IP</th>
            <th>Device Type</th>
            <th>Status</th>
            <th>RCA & Discovery Governance</th>
            <th>Manual Parent</th>
            <th class="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ep in endpoints" :key="ep.id">
            <td>
              <div class="host-info">
                <div class="host-line">
                  <router-link :to="`/endpoints/${ep.id}`" class="host-link">
                    {{ ep.hostname }}
                  </router-link>
                  <span v-if="ep.is_l2_segment" class="l2-pill" title="Local Layer 2 Segment Target">L2</span>
                </div>
                <span class="ip-sub">{{ ep.ip_address }}</span>
              </div>
            </td>
            <td>
              <span class="device-tag">{{ ep.device_type }}</span>
            </td>
            <td>
              <span class="status-badge" :class="getStatusClass(ep.current_detailed_state || ep.current_operational_state)">
                {{ ep.current_detailed_state || ep.current_operational_state || 'ACTIVE' }}
              </span>
            </td>
            <td>
              <div class="governance-pills">
                <span class="toggle-pill" :class="ep.enable_rca !== false ? 'active' : 'disabled'" title="Comparative Differential RCA">
                  {{ ep.enable_rca !== false ? '● RCA Active' : '○ RCA Off' }}
                </span>
                <span class="toggle-pill" :class="ep.enable_scheduled_discovery !== false ? 'active-blue' : 'disabled'" title="Midnight Scheduled Route Discovery">
                  {{ ep.enable_scheduled_discovery !== false ? '● Midnight Discovery' : '○ Manual Discovery' }}
                </span>
              </div>
            </td>
            <td>
              <span class="parent-label">
                {{ getParentName(ep.manual_parent_id) }}
              </span>
            </td>
            <td class="text-right">
              <button 
                class="btn-icon action-discovery" 
                @click="triggerDiscovery(ep)" 
                :disabled="discoveringIds.has(ep.id)"
                title="Run Route Discovery and Refresh Baseline"
              >
                <span v-if="discoveringIds.has(ep.id)" class="spinner-sm"></span>
                <span v-else>📡 Discovery</span>
              </button>
              <button class="btn-icon" @click="openEditModal(ep)" title="Edit Settings">⚙ Edit</button>
              <button class="btn-icon danger" @click="confirmDelete(ep)" title="Delete Endpoint">🗑 Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create / Edit Endpoint Modal -->
    <div class="modal-overlay" v-if="showModal" @click.self="closeModal">
      <div class="modal-card">
        <div class="modal-header">
          <h3>{{ isEditing ? 'Edit Endpoint Configuration' : 'Add New Monitored Endpoint' }}</h3>
          <button class="btn-close" @click="closeModal">✕</button>
        </div>

        <form @submit.prevent="saveEndpoint" class="modal-form">
          <div class="form-grid">
            <div class="form-group">
              <label>IP Address *</label>
              <input v-model="form.ip_address" type="text" placeholder="192.168.1.1" required :disabled="isEditing" />
            </div>

            <div class="form-group">
              <label>Hostname *</label>
              <input v-model="form.hostname" type="text" placeholder="core-router-01" required />
            </div>

            <div class="form-group">
              <label>Device Type *</label>
              <input v-model="form.device_type" type="text" placeholder="ROUTER / SWITCH / SERVER" required />
            </div>

            <div class="form-group">
              <label>Location</label>
              <input v-model="form.location" type="text" placeholder="Data Center 1, Rack B" />
            </div>
          </div>

          <div class="form-group">
            <label>Description</label>
            <textarea v-model="form.description" rows="2" placeholder="Primary gateway router"></textarea>
          </div>

          <!-- Upstream Manual Parent Node Selector -->
          <div class="form-group">
            <label>Upstream Parent Node (Manual Parent Override)</label>
            <select v-model="form.manual_parent_id" class="form-select">
              <option :value="null">-- Auto-Discover via Traceroute --</option>
              <option
                v-for="ep in parentCandidates"
                :key="ep.id"
                :value="ep.id"
              >
                {{ ep.hostname }} ({{ ep.ip_address }})
              </option>
            </select>
            <p class="field-help">Manually overrides automatic topology traceroute parent detection.</p>
          </div>

          <div class="form-divider">V1.5 Endpoint Governance & RCA Controls</div>

          <!-- V1.5 Toggle Switches -->
          <div class="toggles-list">
            <label class="switch-row">
              <div class="switch-info">
                <span class="switch-label">Enable Root Cause Analysis (RCA)</span>
                <span class="switch-sub">Fires comparative differential route engine upon DOWN outage transition</span>
              </div>
              <input type="checkbox" v-model="form.enable_rca" />
              <span class="slider"></span>
            </label>

            <label class="switch-row">
              <div class="switch-info">
                <span class="switch-label">Midnight Scheduled Discovery</span>
                <span class="switch-sub">Queues sequential traceroute passes at 00:00 midnight to refresh route baseline</span>
              </div>
              <input type="checkbox" v-model="form.enable_scheduled_discovery" />
              <span class="slider"></span>
            </label>

            <label class="switch-row">
              <div class="switch-info">
                <span class="switch-label">Layer 2 Segment Target</span>
                <span class="switch-sub">Flags target as directly connected in local subnet/VLAN without transit hops</span>
              </div>
              <input type="checkbox" v-model="form.is_l2_segment" />
              <span class="slider"></span>
            </label>

            <label class="switch-row">
              <div class="switch-info">
                <span class="switch-label">Run Diagnostic Trace on Outage</span>
                <span class="switch-sub">Automatically fires background traceroute upon failed ping sub-cycle</span>
              </div>
              <input type="checkbox" v-model="form.allow_incident_trace" />
              <span class="slider"></span>
            </label>

            <label class="switch-row">
              <div class="switch-info">
                <span class="switch-label">Enable ICMP Monitoring</span>
                <span class="switch-sub">Actively pings target every cycle</span>
              </div>
              <input type="checkbox" v-model="form.monitoring_enabled" />
              <span class="slider"></span>
            </label>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="closeModal">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Saving...' : (isEditing ? 'Save Changes' : 'Create Endpoint') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getEndpoints, createEndpoint, updateEndpoint, deleteEndpoint, refreshEndpointBaseline } from '../services/api.js'

const endpoints = ref([])
const loading = ref(true)
const error = ref(null)
const saving = ref(false)
const discoveringIds = ref(new Set())

const showModal = ref(false)
const isEditing = ref(false)
const editingId = ref(null)

const form = ref({
  ip_address: '',
  hostname: '',
  device_type: '',
  location: '',
  description: '',
  monitoring_enabled: true,
  allow_incident_trace: true,
  allow_topology_discovery: true,
  enable_rca: true,
  enable_scheduled_discovery: true,
  is_l2_segment: false,
  manual_parent_id: null,
})

const parentCandidates = computed(() => {
  if (!isEditing.value) return endpoints.value
  return endpoints.value.filter(ep => ep.id !== editingId.value)
})

function getStatusClass(status) {
  switch (status) {
    case 'UP': return 'status-up'
    case 'UP-UNSTABLE':
    case 'DOWN-UNSTABLE': return 'status-unstable'
    case 'DOWN': return 'status-down'
    default: return ''
  }
}

function getParentName(parentId) {
  if (!parentId) return 'Auto (Traceroute)'
  const found = endpoints.value.find(ep => ep.id === parentId)
  return found ? `${found.hostname} (${found.ip_address})` : parentId
}

async function fetchEndpoints() {
  loading.value = true
  error.value = null
  try {
    const res = await getEndpoints()
    endpoints.value = res.data?.data || res.data || []
  } catch (err) {
    console.error('Failed to fetch endpoints:', err)
    error.value = 'Failed to load endpoints.'
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  isEditing.value = false
  editingId.value = null
  form.value = {
    ip_address: '',
    hostname: '',
    device_type: 'ROUTER',
    location: '',
    description: '',
    monitoring_enabled: true,
    allow_incident_trace: true,
    allow_topology_discovery: true,
    enable_rca: true,
    enable_scheduled_discovery: true,
    is_l2_segment: false,
    manual_parent_id: null,
  }
  showModal.value = true
}

function openEditModal(ep) {
  isEditing.value = true
  editingId.value = ep.id
  form.value = {
    ip_address: ep.ip_address,
    hostname: ep.hostname,
    device_type: ep.device_type,
    location: ep.location || '',
    description: ep.description || '',
    monitoring_enabled: ep.monitoring_enabled !== false,
    allow_incident_trace: ep.allow_incident_trace !== false,
    allow_topology_discovery: ep.allow_topology_discovery !== false,
    enable_rca: ep.enable_rca !== false,
    enable_scheduled_discovery: ep.enable_scheduled_discovery !== false,
    is_l2_segment: ep.is_l2_segment === true,
    manual_parent_id: ep.manual_parent_id || null,
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function saveEndpoint() {
  saving.value = true
  try {
    if (isEditing.value) {
      await updateEndpoint(editingId.value, {
        hostname: form.value.hostname,
        device_type: form.value.device_type,
        location: form.value.location,
        description: form.value.description,
        monitoring_enabled: form.value.monitoring_enabled,
        allow_incident_trace: form.value.allow_incident_trace,
        allow_topology_discovery: form.value.allow_topology_discovery,
        enable_rca: form.value.enable_rca,
        enable_scheduled_discovery: form.value.enable_scheduled_discovery,
        is_l2_segment: form.value.is_l2_segment,
        manual_parent_id: form.value.manual_parent_id,
      })
    } else {
      await createEndpoint(form.value)
    }
    closeModal()
    await fetchEndpoints()
  } catch (err) {
    console.error('Failed to save endpoint:', err)
    alert('Error saving endpoint settings.')
  } finally {
    saving.value = false
  }
}

async function triggerDiscovery(ep) {
  discoveringIds.value.add(ep.id)
  try {
    await refreshEndpointBaseline(ep.id)
    await fetchEndpoints()
    alert(`Route discovery completed for ${ep.hostname} (${ep.ip_address}).`)
  } catch (err) {
    console.error('Route discovery failed:', err)
    alert(`Route discovery failed for ${ep.hostname}.`)
  } finally {
    discoveringIds.value.delete(ep.id)
  }
}

async function confirmDelete(ep) {
  if (confirm(`Are you sure you want to delete endpoint ${ep.hostname} (${ep.ip_address})?`)) {
    try {
      await deleteEndpoint(ep.id)
      await fetchEndpoints()
    } catch (err) {
      console.error('Failed to delete endpoint:', err)
      alert('Error deleting endpoint.')
    }
  }
}

onMounted(() => {
  fetchEndpoints()
})
</script>

<style scoped>
.endpoints-view {
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

.host-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.host-link {
  color: #60A5FA;
  font-weight: 600;
}

.l2-pill {
  background: rgba(59, 130, 246, 0.2);
  color: #60A5FA;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.ip-sub {
  display: block;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.governance-pills {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toggle-pill {
  font-size: 0.78rem;
  padding: 2px 8px;
  border-radius: 6px;
  width: fit-content;
}

.toggle-pill.active { background: rgba(16, 185, 129, 0.15); color: #34D399; }
.toggle-pill.active-blue { background: rgba(59, 130, 246, 0.15); color: #60A5FA; }
.toggle-pill.disabled { background: rgba(107, 114, 128, 0.15); color: #9CA3AF; }

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

.btn-icon.action-discovery {
  color: #60A5FA;
  border-color: rgba(59, 130, 246, 0.4);
}

.btn-icon.action-discovery:hover {
  background: rgba(59, 130, 246, 0.15);
}

.btn-icon.danger:hover {
  color: #F87171;
  border-color: #EF4444;
}

.spinner-sm {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-color);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s infinite linear;
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
  width: 600px;
  max-width: 92vw;
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
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

.form-group input, .form-group textarea, .form-select {
  background: var(--bg-app);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.field-help {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 2px 0 0 0;
}

.form-divider {
  font-size: 0.85rem;
  font-weight: 600;
  color: #3B82F6;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 6px;
  margin-top: 8px;
}

.toggles-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

.switch-info {
  display: flex;
  flex-direction: column;
}

.switch-label {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 500;
}

.switch-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Switch styling */
.switch-row input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #2563EB;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Light mode contrast overrides */
:global(html:not(.dark)) .host-link {
  color: #1d4ed8;
}

:global(html:not(.dark)) .toggle-pill.active {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}

:global(html:not(.dark)) .toggle-pill.active-blue {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
}

:global(html:not(.dark)) .toggle-pill.disabled {
  background: rgba(100, 116, 139, 0.1);
  color: #475569;
}

:global(html:not(.dark)) .l2-pill {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.25);
}

:global(html:not(.dark)) .btn-icon.action-discovery {
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.25);
}

:global(html:not(.dark)) .btn-icon.action-discovery:hover {
  background: rgba(37, 99, 235, 0.08);
}

:global(html:not(.dark)) .form-divider {
  color: #1d4ed8;
}
</style>
