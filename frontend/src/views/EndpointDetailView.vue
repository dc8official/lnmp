<template>
  <div class="detail-wrapper">


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
          <Button 
            icon="pi pi-refresh" 
            label="Refresh" 
            @click="loadData" 
            :loading="loading"
            severity="secondary"
            size="small"
            class="refresh-btn"
          />
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
              <input type="datetime-local" id="start_date" v-model="customStartDate" class="date-picker-input" />
            </div>
            <div class="date-input-group">
              <label for="end_date">End</label>
              <input type="datetime-local" id="end_date" v-model="customEndDate" class="date-picker-input" />
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
            :events="chartEvents" 
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
          <RTTTrendPanel :events="chartEvents" />
        </div>

        <!-- Detailed Event Logs Table -->
        <div class="visualizer-container">
          <div class="panel-header table-header">
            <div>
              <h3><i class="pi pi-list header-icon"></i>Detailed Transition Audit Logs</h3>
              <span class="panel-desc">Historical record of all telemetry events in the queried period</span>
            </div>
            <span class="total-badge">{{ totalEvents }} cycles</span>
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

          <!-- Compact flat monochrome footer utility -->
          <div class="table-pagination-footer">
            <div class="pagination-info">
              Showing {{ pageStart }} - {{ pageEnd }} of {{ totalEvents }} logs
            </div>
            
            <div class="pagination-controls-wrapper">
              <!-- Sharp navigation arrows -->
              <div class="pagination-nav-arrows">
                <button 
                  class="nav-arrow-btn" 
                  :disabled="tablePage <= 1 || loadingTable" 
                  @click="goToPage(tablePage - 1)"
                >
                  &lt;
                </button>
                <span class="current-page-display">Page {{ tablePage }} of {{ totalPages }}</span>
                <button 
                  class="nav-arrow-btn" 
                  :disabled="tablePage >= totalPages || loadingTable" 
                  @click="goToPage(tablePage + 1)"
                >
                  &gt;
                </button>
              </div>

              <!-- Compact row-density selector drop-down -->
              <div class="density-selector-container">
                <select v-model="tableSize" @change="onDensityChange" class="density-dropdown" :disabled="loadingTable">
                  <option :value="50">Show 50</option>
                  <option :value="100">Show 100</option>
                  <option :value="250">Show 250</option>
                </select>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { getEndpoint, getUptimeReport, getEndpointEvents, logout } from '../services/api.js'
import StateTimeline from '../components/StateTimeline.vue'
import RTTTrendPanel from '../components/RTTTrendPanel.vue'

import Card from 'primevue/card'
import Button from 'primevue/button'

const route = useRoute()
const router = useRouter()
const endpointId = route.params.id

const isDarkMode = ref(true)

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  if (isDarkMode.value) {
    localStorage.setItem('theme', 'dark')
    document.documentElement.classList.add('dark')
  } else {
    localStorage.setItem('theme', 'light')
    document.documentElement.classList.remove('dark')
  }
}



const user = ref(null)
const endpoint = ref(null)
const uptimeReport = ref(null)
const events = ref([])
const chartEvents = ref([])
const loading = ref(true)
const error = ref(null)

const tablePage = ref(1)
const tableSize = ref(100)
const totalEvents = ref(0)
const totalPages = ref(1)
const loadingTable = ref(false)

const pageStart = computed(() => {
  if (totalEvents.value === 0) return 0
  return (tablePage.value - 1) * tableSize.value + 1
})

const pageEnd = computed(() => {
  return Math.min(tablePage.value * tableSize.value, totalEvents.value)
})

function getPastDateStr(daysAgo) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return d.toISOString().split('T')[0]
}

function getPastDateTimeStr(daysAgo) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  const year = d.getUTCFullYear()
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  const hours = String(d.getUTCHours()).padStart(2, '0')
  const minutes = String(d.getUTCMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

// Date Range filters
const filterRange = ref('24h')
const customStartDate = ref(getPastDateTimeStr(7))
const customEndDate = ref(getPastDateTimeStr(0))

// Detailed date strings for timeline component
const periodStartStr = ref('')
const periodEndStr = ref('')

const sortedEvents = computed(() => {
  return [...events.value].sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
})

const setRange = (range) => {
  filterRange.value = range
  if (range !== 'custom') {
    loadData()
  }
}

const loadTableEvents = async () => {
  loadingTable.value = true
  
  let start = ''
  let end = ''
  
  if (filterRange.value === '24h') {
    start = getPastDateTimeStr(1)
    end = getPastDateTimeStr(0)
  } else {
    end = getPastDateStr(0)
    if (filterRange.value === '7d') {
      start = getPastDateStr(7)
    } else if (filterRange.value === '30d') {
      start = getPastDateStr(30)
    } else {
      start = customStartDate.value
      end = customEndDate.value
    }
  }
  
  try {
    const res = await getEndpointEvents(endpointId, start, end, tablePage.value, tableSize.value)
    events.value = res.data.data
    totalEvents.value = res.data.meta?.total || 0
    totalPages.value = res.data.meta?.total_pages || 1
  } catch (err) {
    console.error('Failed to reload table events:', err)
  } finally {
    loadingTable.value = false
  }
}

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    tablePage.value = page
    loadTableEvents()
  }
}

const onDensityChange = () => {
  tablePage.value = 1
  loadTableEvents()
}

const loadData = async () => {
  loading.value = true
  error.value = null
  tablePage.value = 1
  
  let start = ''
  let end = ''
  
  if (filterRange.value === '24h') {
    start = getPastDateTimeStr(1)
    end = getPastDateTimeStr(0)
  } else {
    end = getPastDateStr(0)
    if (filterRange.value === '7d') {
      start = getPastDateStr(7)
    } else if (filterRange.value === '30d') {
      start = getPastDateStr(30)
    } else {
      start = customStartDate.value
      end = customEndDate.value
    }
  }
  
  // Format period boundary strings for visual components
  if (filterRange.value === 'custom' || filterRange.value === '24h') {
    periodStartStr.value = `${start}:00Z`
    periodEndStr.value = `${end}:00Z`
  } else {
    periodStartStr.value = `${start}T00:00:00Z`
    periodEndStr.value = `${end}T23:59:59Z`
  }
  
  try {
    const [endpointRes, uptimeRes, eventsRes, tableEventsRes] = await Promise.all([
      getEndpoint(endpointId),
      getUptimeReport(endpointId, start, end),
      getEndpointEvents(endpointId, start, end, 1, 250), // Fetch up to 250 records for continuous charts
      getEndpointEvents(endpointId, start, end, 1, tableSize.value) // Fetch paginated events starting from page 1
    ])
    
    endpoint.value = endpointRes.data.data
    uptimeReport.value = uptimeRes.data.data
    chartEvents.value = eventsRes.data.data
    events.value = tableEventsRes.data.data
    
    totalEvents.value = tableEventsRes.data.meta?.total || 0
    totalPages.value = tableEventsRes.data.meta?.total_pages || 1
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
  const currentTheme = localStorage.getItem('theme') || 'dark'
  isDarkMode.value = currentTheme === 'dark'
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }

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
  color: #FFFFFF;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.user-badge.admin {
  background-color: #0A0A0A;
  border: 1px solid #262626;
  color: #FFFFFF;
}

.user-badge.viewer {
  background-color: #0A0A0A;
  border: 1px solid #262626;
  color: #A3A3A3;
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
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background-color: #000000;
}

.status-badge.active {
  border: 1px solid #262626;
  color: #FFFFFF;
}

.status-badge.disabled {
  border: 1px solid #262626;
  color: #A3A3A3;
}

.monitoring-badge {
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background-color: #000000;
}

.monitoring-badge.enabled {
  border: 1px solid #262626;
  color: #FFFFFF;
}

.monitoring-badge.disabled {
  border: 1px solid #FF0000;
  color: #FF0000;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #A3A3A3;
  padding: 8rem 0;
  gap: 1rem;
  font-family: monospace;
}

.spinner-icon {
  font-size: 2.5rem;
  color: #FFFFFF;
}

.error-message {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  background-color: #000000;
  color: #FF0000;
  padding: 1.5rem;
  border-radius: 4px;
  border: 1px solid #FF0000;
  margin-bottom: 2rem;
}

.error-message h4 {
  font-weight: 700;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.content-layout {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.overview-card {
  background-color: var(--card-bg) !important;
  border: 1px solid var(--card-border) !important;
  border-radius: 4px !important;
  box-shadow: none !important;
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
  font-size: 1.8rem;
  padding: 0.75rem;
  border-radius: 4px;
  background-color: #0A0A0A;
  border: 1px solid #262626;
  color: #FFFFFF;
}

.ip-display {
  font-family: monospace;
  color: #A3A3A3;
  font-size: 1rem;
  font-weight: 700;
  margin-top: 0.15rem;
}

h2 {
  color: #FFFFFF;
  font-weight: 700;
  font-size: 1.35rem;
  letter-spacing: -0.01em;
}

.meta-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.meta-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #A3A3A3;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.meta-value {
  font-size: 0.95rem;
  font-weight: 700;
  color: #FFFFFF;
}

.meta-value.desc {
  font-weight: 500;
  color: #A3A3A3;
  line-height: 1.5;
}

.full-width {
  grid-column: span 1;
}

@media (min-width: 768px) {
  .full-width {
    grid-column: span 3;
    border-top: 1px solid #262626;
    padding-top: 1rem;
  }
}

/* Date Filters Toolbar */
.toolbar-card {
  background: var(--card-bg);
  border-radius: 4px;
  padding: 1rem 1.5rem;
  border: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-start;
  box-shadow: none;
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
  color: #FFFFFF;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
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
  color: #A3A3A3;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.date-picker-input {
  background-color: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 4px;
  padding: 0.35rem 0.5rem;
  font-size: 0.85rem;
  outline: none;
  font-family: monospace;
  color: var(--text-primary);
}

.date-picker-input:focus {
  border-color: var(--text-secondary);
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
  background: var(--card-bg);
  border-radius: 4px;
  border: 1px solid var(--card-border);
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  box-shadow: none;
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #A3A3A3;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-header i {
  font-size: 1rem;
  color: #A3A3A3;
}

.metric-body {
  display: flex;
  flex-direction: column;
}

.metric-body .value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #FFFFFF;
  font-family: monospace;
}

.metric-body .subtext {
  font-size: 0.75rem;
  color: #A3A3A3;
  margin-top: 0.25rem;
  font-family: monospace;
}

.value.perfect { color: var(--text-primary); }
.value.good { color: var(--text-primary); }
.value.warning { color: var(--status-warn-color); }
.value.critical { color: var(--status-down-color); }

.value.alert { color: var(--status-down-color); }
.value.clean { color: var(--text-primary); }
.value.has-down { color: var(--status-down-color); }

/* Visualizer Container panels */
.visualizer-container {
  background: var(--card-bg);
  border-radius: 4px;
  border: 1px solid var(--card-border);
  padding: 1.5rem;
  box-shadow: none;
}

.panel-header {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 1rem;
}

.panel-header h3 {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.header-icon {
  color: var(--text-primary);
}

.panel-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
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
  background-color: var(--bg-surface-selected);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  font-family: monospace;
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
  background-color: var(--bg-app);
  color: var(--text-secondary);
  font-weight: 700;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid var(--card-border);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.audit-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--card-border);
  color: var(--text-primary);
}

.audit-table tr:hover {
  background-color: var(--bg-surface-hover);
}

.table-empty {
  text-align: center;
  padding: 3rem 0 !important;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-family: monospace;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 700;
}

.text-success { color: var(--status-up-color); }
.text-warning { color: var(--status-warn-color); }
.text-danger { color: var(--status-down-color); }

.table-badge {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table-badge.up {
  color: var(--status-up-color);
}

.table-badge.down {
  color: var(--status-down-color);
}

.table-detail-badge {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table-detail-badge.up {
  color: var(--status-up-color);
}

.table-detail-badge.up-unstable,
.table-detail-badge.down-unstable {
  color: var(--status-warn-color);
}

.table-detail-badge.down {
  color: var(--status-down-color);
}

/* PrimeVue Button custom scoping overrides */
:deep(.p-button) {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-secondary) !important;
  font-family: monospace !important;
  font-size: 0.85rem !important;
  font-weight: 700 !important;
  border-radius: 4px !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: all 0.15s ease;
}
:deep(.p-button:hover) {
  background-color: var(--bg-surface-hover) !important;
  border-color: var(--border-color-strong) !important;
  color: var(--text-primary) !important;
}
/* When button is active (i.e. not outlined) */
:deep(.p-button:not(.p-button-outlined)) {
  background-color: var(--text-primary) !important;
  border-color: var(--text-primary) !important;
  color: var(--text-inverse) !important;
}
:deep(.p-button:not(.p-button-outlined):hover) {
  background-color: var(--text-secondary) !important;
  border-color: var(--text-secondary) !important;
  color: var(--text-inverse) !important;
}
/* Back button specific */
.back-btn {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-primary) !important;
}
/* Danger button (logout, retry) */
:deep(.p-button-danger) {
  background-color: var(--bg-surface) !important;
  border: 1px solid var(--status-down-color) !important;
  color: var(--status-down-color) !important;
}
:deep(.p-button-danger:hover) {
  background-color: var(--bg-surface-hover) !important;
  border-color: var(--status-down-color) !important;
  color: var(--status-down-color) !important;
}
/* Text button (header menu navigation) */
:deep(.p-button-text) {
  background: transparent !important;
  border-color: transparent !important;
  color: var(--text-secondary) !important;
}
:deep(.p-button-text:hover) {
  background-color: var(--bg-surface-selected) !important;
  color: var(--text-primary) !important;
}
:deep(.p-button-text.p-button-danger:hover) {
  background-color: var(--bg-surface-selected) !important;
  color: var(--status-down-color) !important;
}

/* ==========================================================================
   Light Mode Theme Scoping Overrides (Remaining wrapper variables)
   ========================================================================== */
:global(html:not(.dark)) .detail-wrapper {
  background-color: #ffffff;
}
:global(html:not(.dark)) .app-nav {
  background-color: #ffffff;
  border-bottom: 1px solid #cbd5e1;
}
:global(html:not(.dark)) .brand {
  color: #0f172a;
}
:global(html:not(.dark)) .brand-icon {
  color: #0f172a;
}
:global(html:not(.dark)) .user-badge.admin {
  background-color: rgba(4, 159, 108, 0.08);
  color: #049f6c;
  border: 1px solid rgba(4, 159, 108, 0.15);
}
:global(html:not(.dark)) .user-badge.viewer {
  background-color: #f1f5f9;
  color: #475569;
  border: 1px solid #cbd5e1;
}
:global(html:not(.dark)) .status-badge {
  background-color: #ffffff;
}
:global(html:not(.dark)) .status-badge.active {
  border: 1px solid #cbd5e1;
  color: #334155;
}
:global(html:not(.dark)) .status-badge.disabled {
  border: 1px solid #cbd5e1;
  color: #64748b;
}
:global(html:not(.dark)) .monitoring-badge {
  background-color: #ffffff;
}
:global(html:not(.dark)) .monitoring-badge.enabled {
  border: 1px solid #cbd5e1;
  color: #334155;
}
:global(html:not(.dark)) .monitoring-badge.disabled {
  border: 1px solid #FF0000;
  color: #FF0000;
}
:global(html:not(.dark)) .loading-state {
  color: #475569;
}
:global(html:not(.dark)) .spinner-icon {
  color: #0f172a;
}
:global(html:not(.dark)) .error-message {
  background-color: #fef2f2;
}
:global(html:not(.dark)) .overview-card,
:global(html:not(.dark)) .toolbar-card,
:global(html:not(.dark)) .visualizer-container,
:global(html:not(.dark)) .metric-card {
  background-color: #fafafa !important;
  border: 1px solid #cbd5e1 !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
}

.version-tag {
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--text-muted, #737373);
  margin-left: 0.25rem;
  font-weight: 500;
  text-transform: none;
}
:global(html:not(.dark)) .main-icon-styled {
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #475569;
}
:global(html:not(.dark)) .ip-display {
  color: #475569;
}
:global(html:not(.dark)) h2 {
  color: #0f172a;
}
:global(html:not(.dark)) .meta-label {
  color: #475569;
}
:global(html:not(.dark)) .meta-value {
  color: #0f172a;
}
:global(html:not(.dark)) .meta-value.desc {
  color: #475569;
}
:global(html:not(.dark)) .toolbar-title {
  color: #0f172a;
}
:global(html:not(.dark)) .date-picker-input {
  background-color: #ffffff;
  border: 1px solid #cbd5e1;
  color: #0f172a;
}
:global(html:not(.dark)) .date-picker-input:focus {
  border-color: #049f6c;
}
:global(html:not(.dark)) .metric-header {
  color: #475569;
}
:global(html:not(.dark)) .metric-header i {
  color: #64748b;
}
:global(html:not(.dark)) .metric-body .value {
  color: #0f172a;
}
:global(html:not(.dark)) .metric-body .subtext {
  color: #64748b;
}

/* Compact Table Pagination Footer Styles */
.table-pagination-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--card-border);
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.pagination-controls-wrapper {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.pagination-nav-arrows {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.nav-arrow-btn {
  background-color: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  cursor: pointer;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  font-size: 0.8rem;
  font-weight: bold;
  transition: all 0.15s ease;
}

.nav-arrow-btn:hover:not(:disabled) {
  border-color: var(--text-primary);
  color: var(--text-primary);
  background-color: rgba(255, 255, 255, 0.05);
}

.nav-arrow-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.current-page-display {
  font-weight: bold;
}

.density-dropdown {
  background-color: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  font-family: monospace;
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.density-dropdown:focus, .density-dropdown:hover {
  border-color: var(--text-secondary);
}

/* Light mode hover background for arrow buttons */
:global(html:not(.dark)) .nav-arrow-btn:hover:not(:disabled) {
  background-color: rgba(0, 0, 0, 0.05);
}
</style>
