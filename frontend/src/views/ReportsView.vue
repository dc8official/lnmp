<template>
  <div class="reports-view">
    <!-- Header Toolbar -->
    <div class="reports-toolbar">
      <div class="toolbar-left">
        <h1 class="page-title">Fleet Reports & SLA Console</h1>
        <p class="page-sub">Comprehensive fleet availability, outage incident ledger, and telemetry exports</p>
      </div>
      <div class="toolbar-right">
        <button 
          class="btn-secondary" 
          @click="loadAllReports" 
          :disabled="loading"
        >
          <span>{{ loading ? 'Refreshing...' : '↻ Refresh Data' }}</span>
        </button>
        <button 
          class="btn-primary" 
          @click="handleExportCsv" 
          :disabled="exporting || endpoints.length === 0"
        >
          <i class="pi" :class="exporting ? 'pi-spin pi-spinner' : 'pi-download'" style="margin-right: 0.5rem;"></i>
          <span>{{ exporting ? 'Exporting...' : '📥 Export Telemetry (CSV)' }}</span>
        </button>
      </div>
    </div>

    <!-- Analysis Period Toolbar -->
    <div class="period-toolbar">
      <div class="period-pills">
        <button 
          class="pill-btn" 
          :class="{ active: filterRange === '24h' }" 
          @click="setRange('24h')"
        >
          24 Hours
        </button>
        <button 
          class="pill-btn" 
          :class="{ active: filterRange === '7d' }" 
          @click="setRange('7d')"
        >
          7 Days
        </button>
        <button 
          class="pill-btn" 
          :class="{ active: filterRange === '30d' }" 
          @click="setRange('30d')"
        >
          30 Days
        </button>
        <button 
          class="pill-btn" 
          :class="{ active: filterRange === 'custom' }" 
          @click="setRange('custom')"
        >
          Custom Range
        </button>
      </div>

      <!-- Custom Range Inline Inputs -->
      <div v-if="filterRange === 'custom'" class="custom-range-row">
        <div class="date-group">
          <label>Start (UTC)</label>
          <input type="datetime-local" v-model="customStart" class="input-datetime" />
        </div>
        <div class="date-group">
          <label>End (UTC)</label>
          <input type="datetime-local" v-model="customEnd" class="input-datetime" />
        </div>
        <button class="btn-query" @click="loadAllReports" :disabled="loading">
          Apply Range
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert-error" role="alert">
      {{ error }}
    </div>

    <!-- Fleet KPI Strip -->
    <div class="kpi-strip">
      <div class="kpi-card">
        <span class="kpi-label">Mean Fleet SLA</span>
        <span class="kpi-value tnum text-accent">{{ fleetSla }}%</span>
        <span class="kpi-sub">Target: 99.90%</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Active Targets</span>
        <span class="kpi-value tnum">{{ activeEndpointsCount }} / {{ endpoints.length }}</span>
        <span class="kpi-sub">Monitored nodes</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total Outages</span>
        <span class="kpi-value tnum" :class="totalIncidentCount > 0 ? 'text-down' : 'text-up'">
          {{ totalIncidentCount }}
        </span>
        <span class="kpi-sub">Service disruptions</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total Fleet Downtime</span>
        <span class="kpi-value tnum" :class="totalDowntimeSeconds > 0 ? 'text-down' : ''">
          {{ formatDuration(totalDowntimeSeconds) }}
        </span>
        <span class="kpi-sub">Cumulative outage duration</span>
      </div>
    </div>

    <!-- Fleet Availability & SLA Table -->
    <div class="table-card">
      <div class="table-card-header">
        <div>
          <h3>Fleet Availability & SLA Performance</h3>
          <p class="table-sub">Individual uptime percentage, outage incident counts, and operational duration</p>
        </div>
        <div class="table-search-box">
          <input 
            type="text" 
            v-model="searchQuery" 
            placeholder="Search by hostname or IP..." 
            class="search-input"
          />
        </div>
      </div>

      <div class="table-responsive">
        <table class="dense-table" aria-label="Fleet Availability Table">
          <thead>
            <tr>
              <th @click="toggleSort('hostname')" class="sortable-th">
                Target / Hostname 
                <span class="sort-icon">{{ sortKey === 'hostname' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th>Device Type</th>
              <th @click="toggleSort('operational_state')" class="sortable-th">
                Current State
                <span class="sort-icon">{{ sortKey === 'operational_state' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th @click="toggleSort('uptime_percentage')" class="sortable-th">
                Uptime SLA (%)
                <span class="sort-icon">{{ sortKey === 'uptime_percentage' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th @click="toggleSort('incident_count')" class="sortable-th">
                Incidents
                <span class="sort-icon">{{ sortKey === 'incident_count' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th @click="toggleSort('uptime_seconds')" class="sortable-th">
                UP Duration
                <span class="sort-icon">{{ sortKey === 'uptime_seconds' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th @click="toggleSort('downtime_seconds')" class="sortable-th">
                DOWN Duration
                <span class="sort-icon">{{ sortKey === 'downtime_seconds' ? (sortAsc ? '▲' : '▼') : '↕' }}</span>
              </th>
              <th class="text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && reportRows.length === 0">
              <td colspan="8" class="table-empty">
                <div class="spinner"></div>
                <p>Computing fleet telemetry and compiling SLA summaries...</p>
              </td>
            </tr>
            <tr v-else-if="filteredReportRows.length === 0">
              <td colspan="8" class="table-empty">
                No endpoints match the query or filter criteria.
              </td>
            </tr>
            <tr v-for="row in sortedReportRows" :key="row.id">
              <td>
                <div class="host-col">
                  <router-link :to="`/endpoints/${row.id}`" class="host-name">
                    {{ row.hostname }}
                  </router-link>
                  <span class="host-ip tnum">{{ row.ip_address }}</span>
                </div>
              </td>
              <td>
                <span class="device-pill">{{ row.device_type }}</span>
              </td>
              <td>
                <span class="state-pill" :class="row.operational_state.toLowerCase()">
                  {{ row.detailed_state || row.operational_state }}
                </span>
              </td>
              <td>
                <span class="sla-badge tnum" :class="getSlaClass(row.uptime_percentage)">
                  {{ row.uptime_percentage != null ? row.uptime_percentage.toFixed(2) + '%' : '100.00%' }}
                </span>
              </td>
              <td class="tnum" :class="row.incident_count > 0 ? 'text-down' : ''">
                {{ row.incident_count }}
              </td>
              <td class="tnum font-mono">
                {{ formatDuration(row.uptime_seconds) }}
              </td>
              <td class="tnum font-mono" :class="row.downtime_seconds > 0 ? 'text-down font-bold' : ''">
                {{ formatDuration(row.downtime_seconds) }}
              </td>
              <td class="text-right">
                <router-link :to="`/endpoints/${row.id}`" class="btn-inspect">
                  Inspect →
                </router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getEndpoints, getUptimeReport, exportBatchTelemetry } from '../services/api.js'

const loading = ref(false)
const exporting = ref(false)
const error = ref(null)

const endpoints = ref([])
const reportRows = ref([])
const searchQuery = ref('')

const filterRange = ref('24h')
const customStart = ref(new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 16))
const customEnd = ref(new Date().toISOString().slice(0, 16))

const sortKey = ref('uptime_percentage')
const sortAsc = ref(true)

function setRange(range) {
  filterRange.value = range
  if (range !== 'custom') {
    loadAllReports()
  }
}

function getQueryRange() {
  const now = new Date()
  let start = ''
  let end = now.toISOString()

  if (filterRange.value === '24h') {
    start = new Date(now.getTime() - 24 * 3600 * 1000).toISOString()
  } else if (filterRange.value === '7d') {
    start = new Date(now.getTime() - 7 * 24 * 3600 * 1000).toISOString()
  } else if (filterRange.value === '30d') {
    start = new Date(now.getTime() - 30 * 24 * 3600 * 1000).toISOString()
  } else {
    start = new Date(customStart.value).toISOString()
    end = new Date(customEnd.value).toISOString()
  }
  return { start, end }
}

async function loadAllReports() {
  loading.value = true
  error.value = null
  const { start, end } = getQueryRange()

  try {
    const epRes = await getEndpoints()
    const epList = epRes.data?.data || []
    endpoints.value = epList

    const uptimePromises = epList.map(async (ep) => {
      try {
        const repRes = await getUptimeReport(ep.id, start, end)
        const repData = repRes.data?.data || {}
        return {
          id: ep.id,
          hostname: ep.hostname,
          ip_address: ep.ip_address,
          device_type: ep.device_type || 'SERVER',
          operational_state: ep.current_operational_state || ep.endpoint_status || 'UP',
          detailed_state: ep.current_detailed_state || 'UP',
          monitoring_enabled: ep.monitoring_enabled,
          uptime_percentage: repData.uptime_percentage != null ? repData.uptime_percentage : (parseFloat(ep.uptime_percentage_24h) || 100.0),
          incident_count: repData.incident_count || 0,
          uptime_seconds: repData.uptime_seconds || 0,
          downtime_seconds: repData.downtime_seconds || 0,
          total_seconds: repData.total_seconds || 0,
        }
      } catch (err) {
        return {
          id: ep.id,
          hostname: ep.hostname,
          ip_address: ep.ip_address,
          device_type: ep.device_type || 'SERVER',
          operational_state: ep.current_operational_state || ep.endpoint_status || 'UP',
          detailed_state: ep.current_detailed_state || 'UP',
          monitoring_enabled: ep.monitoring_enabled,
          uptime_percentage: parseFloat(ep.uptime_percentage_24h) || 100.0,
          incident_count: 0,
          uptime_seconds: 0,
          downtime_seconds: 0,
          total_seconds: 0,
        }
      }
    })

    reportRows.value = await Promise.all(uptimePromises)
  } catch (err) {
    console.error('Failed to load fleet reports:', err)
    error.value = err.response?.data?.detail || 'Failed to assemble fleet report metrics.'
  } finally {
    loading.value = false
  }
}

const fleetSla = computed(() => {
  if (reportRows.value.length === 0) return '100.00'
  const sum = reportRows.value.reduce((acc, r) => acc + (r.uptime_percentage || 100.0), 0)
  return (sum / reportRows.value.length).toFixed(2)
})

const activeEndpointsCount = computed(() => {
  return reportRows.value.filter(r => r.monitoring_enabled).length
})

const totalIncidentCount = computed(() => {
  return reportRows.value.reduce((acc, r) => acc + (r.incident_count || 0), 0)
})

const totalDowntimeSeconds = computed(() => {
  return reportRows.value.reduce((acc, r) => acc + (r.downtime_seconds || 0), 0)
})

const filteredReportRows = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return reportRows.value
  return reportRows.value.filter(r => 
    r.hostname.toLowerCase().includes(q) ||
    r.ip_address.toLowerCase().includes(q) ||
    r.device_type.toLowerCase().includes(q)
  )
})

const sortedReportRows = computed(() => {
  const rows = [...filteredReportRows.value]
  rows.sort((a, b) => {
    let valA = a[sortKey.value]
    let valB = b[sortKey.value]

    if (typeof valA === 'string') {
      return sortAsc.value ? valA.localeCompare(valB) : valB.localeCompare(valA)
    }
    valA = valA ?? 0
    valB = valB ?? 0
    return sortAsc.value ? valA - valB : valB - valA
  })
  return rows
})

function toggleSort(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}

function getSlaClass(val) {
  if (val == null) return 'sla-good'
  if (val >= 99.9) return 'sla-good'
  if (val >= 98.0) return 'sla-warn'
  return 'sla-bad'
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0s'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60

  const parts = []
  if (d > 0) parts.push(`${d}d`)
  if (h > 0) parts.push(`${h}h`)
  if (m > 0) parts.push(`${m}m`)
  if (s > 0 && d === 0 && h === 0) parts.push(`${s}s`)
  return parts.join(' ') || `${seconds}s`
}

async function handleExportCsv() {
  if (endpoints.value.length === 0) return
  exporting.value = true
  const { start, end } = getQueryRange()

  try {
    const ids = endpoints.value.map(ep => ep.id)
    const res = await exportBatchTelemetry(ids, start, end)
    const blob = new Blob([res.data], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `fleet_telemetry_report_${filterRange.value}_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    console.error('CSV export failed:', err)
    alert('Failed to generate batch CSV export.')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadAllReports()
})
</script>

<style scoped>
.reports-view {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.reports-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary, #fafafa);
  margin: 0;
  letter-spacing: -0.02em;
}

.page-sub {
  font-size: 0.875rem;
  color: var(--text-secondary, #a1a1aa);
  margin-top: 0.25rem;
}

.toolbar-right {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.period-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--bg-surface, #121215);
  border: 1px solid var(--border-color, #27272a);
  border-radius: 8px;
}

.period-pills {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.pill-btn {
  padding: 0.375rem 0.875rem;
  border-radius: 6px;
  border: 1px solid var(--border-color, #27272a);
  background: transparent;
  color: var(--text-secondary, #a1a1aa);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill-btn:hover {
  background: var(--bg-surface-elevated, #18181b);
  color: var(--text-primary, #fafafa);
}

.pill-btn.active {
  background: var(--text-primary, #fafafa);
  color: var(--bg-primary, #09090b);
  border-color: var(--text-primary, #fafafa);
}

.custom-range-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color, #27272a);
}

.date-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.date-group label {
  font-size: 0.75rem;
  color: var(--text-tertiary, #71717a);
  font-weight: 600;
}

.input-datetime {
  background: var(--bg-surface-elevated, #18181b);
  border: 1px solid var(--border-color, #27272a);
  color: var(--text-primary, #fafafa);
  border-radius: 6px;
  padding: 0.375rem 0.625rem;
  font-size: 0.8125rem;
}

.btn-query {
  padding: 0.375rem 0.875rem;
  background: var(--text-primary, #fafafa);
  color: var(--bg-primary, #09090b);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.8125rem;
  cursor: pointer;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.kpi-card {
  padding: 1.25rem;
  background: var(--bg-surface, #121215);
  border: 1px solid var(--border-color, #27272a);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.kpi-label {
  font-size: 0.8125rem;
  color: var(--text-secondary, #a1a1aa);
  font-weight: 600;
}

.kpi-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--text-primary, #fafafa);
  letter-spacing: -0.03em;
}

.kpi-sub {
  font-size: 0.75rem;
  color: var(--text-tertiary, #71717a);
}

.text-accent {
  color: #38bdf8;
}

.text-up {
  color: #4ade80;
}

.text-down {
  color: #f87171;
}

.table-card {
  background: var(--bg-surface, #121215);
  border: 1px solid var(--border-color, #27272a);
  border-radius: 8px;
  overflow: hidden;
}

.table-card-header {
  padding: 1.25rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  border-bottom: 1px solid var(--border-color, #27272a);
}

.table-card-header h3 {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary, #fafafa);
  margin: 0;
}

.table-sub {
  font-size: 0.8125rem;
  color: var(--text-secondary, #a1a1aa);
  margin-top: 0.25rem;
}

.search-input {
  width: 260px;
  background: var(--bg-surface-elevated, #18181b);
  border: 1px solid var(--border-color, #27272a);
  color: var(--text-primary, #fafafa);
  border-radius: 6px;
  padding: 0.45rem 0.75rem;
  font-size: 0.8125rem;
}

.table-responsive {
  overflow-x: auto;
}

.dense-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
  text-align: left;
}

.dense-table th {
  padding: 0.75rem 1rem;
  background: var(--bg-surface-elevated, #18181b);
  color: var(--text-secondary, #a1a1aa);
  font-weight: 600;
  border-bottom: 1px solid var(--border-color, #27272a);
}

.sortable-th {
  cursor: pointer;
  user-select: none;
}

.sortable-th:hover {
  color: var(--text-primary, #fafafa);
}

.sort-icon {
  font-size: 0.6875rem;
  margin-left: 0.25rem;
  opacity: 0.6;
}

.dense-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color, #27272a);
  color: var(--text-primary, #fafafa);
  vertical-align: middle;
}

.dense-table tbody tr:hover {
  background: var(--bg-surface-elevated, #18181b);
}

.host-col {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.host-name {
  font-weight: 600;
  color: var(--text-primary, #fafafa);
  text-decoration: none;
}

.host-name:hover {
  text-decoration: underline;
}

.host-ip {
  font-size: 0.75rem;
  color: var(--text-secondary, #a1a1aa);
  font-family: var(--font-mono, monospace);
}

.device-pill {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.15rem 0.4rem;
  background: var(--bg-surface-elevated, #18181b);
  border: 1px solid var(--border-color, #27272a);
  border-radius: 4px;
  color: var(--text-secondary, #a1a1aa);
  text-transform: uppercase;
}

.state-pill {
  font-size: 0.6875rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  text-transform: uppercase;
}

.state-pill.up {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.state-pill.unstable, .state-pill.up-unstable, .state-pill.down-unstable {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.state-pill.down {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}

.sla-badge {
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.sla-good {
  color: #4ade80;
  background: rgba(74, 222, 128, 0.1);
}

.sla-warn {
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.1);
}

.sla-bad {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}

.btn-inspect {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #a1a1aa);
  text-decoration: none;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-color, #27272a);
  border-radius: 4px;
  transition: all 0.15s ease;
}

.btn-inspect:hover {
  background: var(--text-primary, #fafafa);
  color: var(--bg-primary, #09090b);
}

.table-empty {
  text-align: center;
  padding: 3rem 1rem !important;
  color: var(--text-secondary, #a1a1aa);
}

.font-mono {
  font-family: var(--font-mono, monospace);
}

.font-bold {
  font-weight: 700;
}

.text-right {
  text-align: right;
}

.btn-primary {
  background: var(--btn-primary-bg, #fafafa);
  color: var(--btn-primary-text, #09090b);
  border: none;
  font-weight: 600;
  font-size: 0.8125rem;
  padding: 0.5rem 0.875rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #e4e4e7;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  color: var(--text-primary, #fafafa);
  border: 1px solid var(--border-color, #27272a);
  font-weight: 600;
  font-size: 0.8125rem;
  padding: 0.5rem 0.875rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-surface-elevated, #18181b);
}
</style>
