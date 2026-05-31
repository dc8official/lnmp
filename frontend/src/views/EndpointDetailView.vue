<template>
  <div class="detail-wrapper">
    <!-- Navigation Bar -->
    <nav class="app-nav">
      <div class="brand">
        <i class="pi pi-shield brand-icon"></i>
        <span>lnmp Platform</span>
      </div>
      <div class="user-profile" v-if="user">
        <span class="user-badge" :class="user.role.toLowerCase()">
          {{ user.role }}: {{ user.username }}
        </span>
        <Button label="Dashboard" icon="pi pi-home" class="p-button-text p-button-sm" @click="goToDashboard" />
        <Button label="Sign Out" icon="pi pi-sign-out" class="p-button-text p-button-sm p-button-danger" @click="handleLogout" />
      </div>
    </nav>

    <!-- Main Container -->
    <div class="detail-container">
      
      <!-- Back & Action Header -->
      <div class="back-header">
        <Button 
          label="Back to Dashboard" 
          icon="pi pi-arrow-left" 
          severity="secondary" 
          outlined 
          class="back-btn" 
          @click="goToDashboard" 
        />
        
        <div v-if="endpoint" class="device-actions">
          <span class="status-badge" :class="endpoint.endpoint_status.toLowerCase()">
            {{ endpoint.endpoint_status }}
          </span>
          <span class="monitoring-badge" :class="endpoint.monitoring_enabled ? 'enabled' : 'disabled'">
            <i class="pi" :class="endpoint.monitoring_enabled ? 'pi-eye' : 'pi-eye-slash'"></i>
            {{ endpoint.monitoring_enabled ? 'Active' : 'Paused' }}
          </span>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading && !endpoint" class="loading-state">
        <i class="pi pi-spin pi-spinner spinner-icon"></i>
        <p>Analyzing telemetry and assembling uptime charts...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="error-message">
        <i class="pi pi-exclamation-triangle"></i>
        <div>
          <h4>Telemetry Load Failure</h4>
          <p>{{ error }}</p>
          <Button label="Retry Query" icon="pi pi-refresh" severity="danger" class="mt-2" @click="loadData" />
        </div>
      </div>

      <!-- Main Dashboard Content -->
      <div v-else-if="endpoint" class="content-layout">
        
        <!-- Endpoint Overview Header Card -->
        <Card class="overview-card">
          <template #content>
            <div class="meta-grid">
              <div class="meta-item main-meta">
                <i class="pi" :class="getDeviceIcon(endpoint.device_type)"></i>
                <div>
                  <h2>{{ endpoint.hostname }}</h2>
                  <p class="ip-display">{{ endpoint.ip_address }}</p>
                </div>
              </div>
              <div class="meta-item">
                <span class="meta-label">Device Type</span>
                <span class="meta-value">{{ endpoint.device_type }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Physical Location</span>
                <span class="meta-value">{{ endpoint.location || 'Not Specified' }}</span>
              </div>
              <div class="meta-item full-width">
                <span class="meta-label">Metadata Description</span>
                <span class="meta-value desc">{{ endpoint.description || 'No description provided.' }}</span>
              </div>
            </div>
          </template>
        </Card>

        <!-- Date Query & Filter Toolbar -->
        <div class="toolbar-card">
          <div class="toolbar-left">
            <span class="toolbar-title">Analysis Period:</span>
            <div class="range-buttons">
              <Button 
                label="Last 24h" 
                :outlined="filterRange !== '24h'" 
                severity="success" 
                size="small"
                @click="setRange('24h')" 
              />
              <Button 
                label="Last 7 Days" 
                :outlined="filterRange !== '7d'" 
                severity="success" 
                size="small"
                @click="setRange('7d')" 
              />
              <Button 
                label="Last 30 Days" 
                :outlined="filterRange !== '30d'" 
                severity="success" 
                size="small"
                @click="setRange('30d')" 
              />
              <Button 
                label="Custom Range" 
                :outlined="filterRange !== 'custom'" 
                severity="success" 
                size="small"
                @click="setRange('custom')" 
              />
            </div>
          </div>

          <!-- Custom range calendar controls -->
          <div v-if="filterRange === 'custom'" class="toolbar-right">
            <div class="date-input-group">
              <label for="start_date">Start</label>
              <input type="date" id="start_date" v-model="customStartDate" class="date-picker-input" />
            </div>
            <div class="date-input-group">
              <label for="end_date">End</label>
              <input type="date" id="end_date" v-model="customEndDate" class="date-picker-input" />
            </div>
            <Button 
              label="Query" 
              icon="pi pi-search" 
              severity="success" 
              size="small"
              :loading="loading" 
              @click="loadData" 
            />
          </div>
        </div>

        <!-- Metrics Grid -->
        <div v-if="uptimeReport" class="metrics-grid">
          
          <div class="metric-card uptime">
            <div class="metric-header">
              <span>Availability Rate</span>
              <i class="pi pi-percentage"></i>
            </div>
            <div class="metric-body">
              <span class="value" :class="getUptimeClass(uptimeReport.uptime_percentage)">
                {{ uptimeReport.uptime_percentage }}%
              </span>
              <span class="subtext">SLA Target: 99.90%</span>
            </div>
          </div>

          <div class="metric-card incidents">
            <div class="metric-header">
              <span>Outages / Incidents</span>
              <i class="pi pi-exclamation-circle"></i>
            </div>
            <div class="metric-body">
              <span class="value" :class="uptimeReport.incident_count > 0 ? 'alert' : 'clean'">
                {{ uptimeReport.incident_count }}
              </span>
              <span class="subtext">Unstable transitions recorded</span>
            </div>
          </div>

          <div class="metric-card active-time">
            <div class="metric-header">
              <span>Operational Uptime</span>
              <i class="pi pi-clock"></i>
            </div>
            <div class="metric-body">
              <span class="value">{{ formatDuration(uptimeReport.uptime_seconds) }}</span>
              <span class="subtext">Aggregate UP duration</span>
            </div>
          </div>

          <div class="metric-card downtime">
            <div class="metric-header">
              <span>Down / Outage Duration</span>
              <i class="pi pi-ban"></i>
            </div>
            <div class="metric-body">
              <span class="value" :class="{ 'has-down': uptimeReport.downtime_seconds > 0 }">
                {{ formatDuration(uptimeReport.downtime_seconds) }}
              </span>
              <span class="subtext">Aggregate OFFLINE duration</span>
            </div>
          </div>

        </div>

        <!-- State Timeline Component -->
        <div class="visualizer-container">
          <div class="panel-header">
            <h3><i class="pi pi-align-left header-icon"></i>State Transition Timeline</h3>
            <span class="panel-desc">Visual timeline showing transitions between UP, UNSTABLE, and DOWN states</span>
          </div>
          <StateTimeline 
            :events="events" 
            :gaps="[]" 
            :periodStart="periodStartStr" 
            :periodEnd="periodEndStr" 
          />
        </div>

        <!-- RTT Latency Trend Component -->
        <div class="visualizer-container">
          <div class="panel-header">
            <h3><i class="pi pi-chart-line header-icon"></i>ICMP Latency & Jitter Trend (RTT)</h3>
            <span class="panel-desc">Line graph representing round-trip-time (ms) averages per cycle</span>
          </div>
          <RTTTrendPanel :events="events" />
        </div>

        <!-- Detailed Event Logs Table -->
        <div class="visualizer-container">
          <div class="panel-header table-header">
            <div>
              <h3><i class="pi pi-list header-icon"></i>Detailed Transition Audit Logs</h3>
              <span class="panel-desc">Historical record of all telemetry events in the queried period</span>
            </div>
            <span class="total-badge">{{ events.length }} cycles</span>
          </div>

          <div class="table-responsive">
            <table class="audit-table">
              <thead>
                <tr>
                  <th>Start Time (Local)</th>
                  <th>End Time (Local)</th>
                  <th>Duration</th>
                  <th>Operational State</th>
                  <th>Detailed State</th>
                  <th>Health Score</th>
                  <th>Avg RTT</th>
                  <th>Cycles</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="events.length === 0">
                  <td colspan="8" class="table-empty">
                    No telemetry records logged for this target during the selected period.
                  </td>
                </tr>
                <tr v-for="ev in sortedEvents" :key="ev.id">
                  <td>{{ formatDate(ev.start_time) }}</td>
                  <td>{{ ev.end_time ? formatDate(ev.end_time) : 'Ongoing (Active)' }}</td>
                  <td class="font-mono">{{ ev.duration_seconds ? formatDuration(ev.duration_seconds) : 'N/A' }}</td>
                  <td>
                    <span class="table-badge" :class="ev.operational_state.toLowerCase()">
                      {{ ev.operational_state }}
                    </span>
                  </td>
                  <td>
                    <span class="table-detail-badge" :class="ev.detailed_state.toLowerCase()">
                      {{ ev.detailed_state }}
                    </span>
                  </td>
                  <td class="font-mono font-bold" :class="getHealthClass(ev.health_score)">
                    {{ ev.health_score }}%
                  </td>
                  <td class="font-mono">
                    {{ ev.avg_rtt_ms != null ? `${ev.avg_rtt_ms} ms` : '-' }}
                  </td>
                  <td class="font-mono">{{ ev.monitoring_cycle_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEndpoint, getUptimeReport, getEndpointEvents, logout } from '../services/api.js'
import StateTimeline from '../components/StateTimeline.vue'
import RTTTrendPanel from '../components/RTTTrendPanel.vue'

import Card from 'primevue/card'
import Button from 'primevue/button'

const route = useRoute()
const router = useRouter()
const endpointId = route.params.id

const user = ref(null)
const endpoint = ref(null)
const uptimeReport = ref(null)
const events = ref([])
const loading = ref(true)
const error = ref(null)

// Date Range filters
const filterRange = ref('7d')
const customStartDate = ref(getPastDateStr(7))
const customEndDate = ref(getPastDateStr(0))

// Detailed date strings for timeline component
const periodStartStr = ref('')
const periodEndStr = ref('')

function getPastDateStr(daysAgo) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return d.toISOString().split('T')[0]
}

const sortedEvents = computed(() => {
  return [...events.value].sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
})

const setRange = (range) => {
  filterRange.value = range
  if (range !== 'custom') {
    loadData()
  }
}

const loadData = async () => {
  loading.value = true
  error.value = null
  
  let start = ''
  let end = getPastDateStr(0)
  
  if (filterRange.value === '24h') {
    start = getPastDateStr(1)
  } else if (filterRange.value === '7d') {
    start = getPastDateStr(7)
  } else if (filterRange.value === '30d') {
    start = getPastDateStr(30)
  } else {
    start = customStartDate.value
    end = customEndDate.value
  }
  
  // Format period boundary strings for visual components
  periodStartStr.value = `${start}T00:00:00Z`
  periodEndStr.value = `${end}T23:59:59Z`
  
  try {
    const [endpointRes, uptimeRes, eventsRes] = await Promise.all([
      getEndpoint(endpointId),
      getUptimeReport(endpointId, start, end),
      getEndpointEvents(endpointId, start, end)
    ])
    
    endpoint.value = endpointRes.data.data
    uptimeReport.value = uptimeRes.data.data
    events.value = eventsRes.data.data
  } catch (err) {
    console.error('Failed to query endpoint telemetry:', err)
    error.value = err.response?.data?.detail || 'Failed to assemble endpoint timeline. Verify server backend is responsive.'
  } finally {
    loading.value = false
  }
}

const getDeviceIcon = (type) => {
  switch (type) {
    case 'Server': return 'pi-server main-icon-styled server'
    case 'Router': return 'pi-directions main-icon-styled router'
    case 'Switch': return 'pi-sitemap main-icon-styled switch'
    case 'Access Point': return 'pi-wifi main-icon-styled wifi'
    case 'Firewall': return 'pi-lock main-icon-styled firewall'
    default: return 'pi-desktop main-icon-styled'
  }
}

const formatDuration = (seconds) => {
  if (seconds == null || seconds < 0) return '0s'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h ${minutes % 60}m`
}

const formatDate = (isoString) => {
  if (!isoString) return '-'
  return new Date(isoString).toLocaleString()
}

const getUptimeClass = (pct) => {
  if (pct >= 99.9) return 'perfect'
  if (pct >= 99.0) return 'good'
  if (pct >= 95.0) return 'warning'
  return 'critical'
}

const getHealthClass = (score) => {
  if (score >= 95) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

const goToDashboard = () => {
  router.push('/')
}

const handleLogout = async () => {
  try {
    await logout()
  } catch (err) {
    console.error('Logout error on backend', err)
  } finally {
    localStorage.removeItem('user')
    router.push('/login')
  }
}

onMounted(() => {
  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    user.value = JSON.parse(storedUser)
  }
  loadData()
})
</script>

<style scoped>
.detail-wrapper {
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

.detail-container {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.back-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.device-actions {
  display: flex;
  gap: 0.75rem;
}

.status-badge {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  text-transform: uppercase;
}

.status-badge.active {
  background-color: rgba(34, 197, 94, 0.12);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.status-badge.disabled {
  background-color: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.monitoring-badge {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.monitoring-badge.enabled {
  background-color: rgba(4, 159, 108, 0.1);
  color: #049f6c;
  border: 1px solid rgba(4, 159, 108, 0.2);
}

.monitoring-badge.disabled {
  background-color: #fef2f2;
  color: #ef4444;
  border: 1px solid #fee2e2;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  padding: 8rem 0;
  gap: 1rem;
}

.spinner-icon {
  font-size: 3rem;
  color: #049f6c;
}

.error-message {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  background-color: #fee2e2;
  color: #b91c1c;
  padding: 1.5rem;
  border-radius: 8px;
  border-left: 5px solid #ef4444;
  margin-bottom: 2rem;
}

.error-message h4 {
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.content-layout {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.overview-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 1.5rem;
}

@media (min-width: 768px) {
  .meta-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.main-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
}

@media (min-width: 768px) {
  .main-meta {
    grid-column: span 1;
  }
}

.main-icon-styled {
  font-size: 2.2rem;
  padding: 0.8rem;
  border-radius: 10px;
  background-color: #f1f5f9;
  color: #475569;
}

.main-icon-styled.server {
  background-color: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.main-icon-styled.router {
  background-color: rgba(14, 165, 233, 0.1);
  color: #0284c7;
}

.main-icon-styled.switch {
  background-color: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
}

.main-icon-styled.wifi {
  background-color: rgba(236, 72, 153, 0.1);
  color: #db2777;
}

.main-icon-styled.firewall {
  background-color: rgba(244, 63, 94, 0.1);
  color: #e11d48;
}

.ip-display {
  font-family: monospace;
  color: #64748b;
  font-size: 1rem;
  font-weight: 600;
  margin-top: 0.15rem;
}

.meta-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.meta-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #94a3b8;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.meta-value {
  font-size: 0.95rem;
  font-weight: 600;
  color: #1e293b;
}

.meta-value.desc {
  font-weight: 400;
  color: #475569;
  line-height: 1.5;
}

.full-width {
  grid-column: span 1;
}

@media (min-width: 768px) {
  .full-width {
    grid-column: span 3;
    border-top: 1px solid #f1f5f9;
    padding-top: 1rem;
  }
}

/* Date Filters Toolbar */
.toolbar-card {
  background: white;
  border-radius: 12px;
  padding: 1rem 1.5rem;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-start;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

@media (min-width: 1024px) {
  .toolbar-card {
    flex-direction: row;
    align-items: center;
  }
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.toolbar-title {
  font-weight: 700;
  color: #334155;
  font-size: 0.9rem;
}

.range-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  width: 100%;
}

@media (min-width: 1024px) {
  .toolbar-right {
    width: auto;
    justify-content: flex-end;
  }
}

.date-input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.date-input-group label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
}

.date-picker-input {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  font-size: 0.85rem;
  outline: none;
  font-family: inherit;
  color: #334155;
}

.date-picker-input:focus {
  border-color: #049f6c;
}

/* Metrics Cards Grid */
.metrics-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(1, 1fr);
}

@media (min-width: 576px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

.metric-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.metric-header i {
  font-size: 1.1rem;
  color: #94a3b8;
}

.metric-body {
  display: flex;
  flex-direction: column;
}

.metric-body .value {
  font-size: 1.6rem;
  font-weight: 800;
  color: #0f172a;
}

.metric-body .subtext {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 0.25rem;
}

.value.perfect { color: #16a34a; }
.value.good { color: #15803d; }
.value.warning { color: #d97706; }
.value.critical { color: #dc2626; }

.value.alert { color: #dc2626; }
.value.clean { color: #16a34a; }
.value.has-down { color: #dc2626; }

/* Visualizer Container panels */
.visualizer-container {
  background: white;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 1.5rem;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}

.panel-header {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 1rem;
}

.panel-header h3 {
  font-size: 1.1rem;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-icon {
  color: #049f6c;
}

.panel-desc {
  font-size: 0.8rem;
  color: #64748b;
  display: block;
  margin-top: 0.25rem;
}

/* Detailed Audit Table */
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.total-badge {
  background-color: #f1f5f9;
  color: #475569;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
}

.audit-table th {
  background-color: #f8fafc;
  color: #475569;
  font-weight: 700;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid #e2e8f0;
}

.audit-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.audit-table tr:hover {
  background-color: #f8fafc;
}

.table-empty {
  text-align: center;
  padding: 3rem 0 !important;
  color: #94a3b8;
  font-size: 0.9rem;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 700;
}

.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger { color: #ef4444; }

.table-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  text-transform: uppercase;
}

.table-badge.up {
  background-color: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.table-badge.down {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.table-detail-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.table-detail-badge.up {
  background-color: #f0fdf4;
  color: #15803d;
}

.table-detail-badge.up-unstable {
  background-color: #fffbeb;
  color: #b45309;
}

.table-detail-badge.down-unstable {
  background-color: #fff7ed;
  color: #c2410c;
}

.table-detail-badge.down {
  background-color: #fef2f2;
  color: #b91c1c;
}
</style>
