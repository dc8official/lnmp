<template>
  <div class="bandwidth-view">
    <!-- Header Toolbar -->
    <div class="bandwidth-toolbar">
      <div class="toolbar-left">
        <h1 class="page-title">Fleet-wide Bandwidth & Flow Telemetry</h1>
        <div class="toolbar-sub-row">
          <span class="page-sub">
            v3.2.0 Flow Engine
            <span class="separator">·</span>
            NetFlow v5, NetFlow v9 & IPFIX
          </span>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- Auto-Refresh Interval Selector (UI-07) -->
        <div class="auto-refresh-selector">
          <label class="refresh-label">Refresh:</label>
          <select v-model="autoRefreshInterval" @change="handleAutoRefreshChange" class="refresh-select">
            <option value="0">Off</option>
            <option value="15">15s</option>
            <option value="30">30s</option>
            <option value="60">60s</option>
          </select>
        </div>

        <!-- Window Filter Pills -->
        <div class="window-pills" role="group" aria-label="Time Window Selector">
          <button
            v-for="w in windowOptions"
            :key="w"
            class="btn-pill"
            :class="{ active: selectedWindow === w }"
            @click="setWindow(w)"
            :aria-pressed="selectedWindow === w"
          >
            {{ w }}
          </button>
        </div>

        <button
          class="btn-secondary"
          @click="refreshData"
          :disabled="loading"
          aria-label="Refresh telemetry data"
        >
          <span>{{ loading ? 'Syncing...' : '↻ Refresh' }}</span>
        </button>
      </div>
    </div>

    <!-- Unmatched Exporter Discovery Banner (BUG-05 Multi-IP Grid) -->
    <div
      v-if="unmatchedExporters.length > 0"
      class="unmatched-banner"
      role="alert"
      aria-live="polite"
    >
      <div class="unmatched-header-row">
        <div class="unmatched-icon">⚠</div>
        <div class="unmatched-title">
          Unmatched Flow Exporters: {{ unmatchedExporters.length }} Unknown Router/Switch Stream{{ unmatchedExporters.length > 1 ? 's' : '' }} Detected
        </div>
      </div>
      <div class="unmatched-grid">
        <div 
          v-for="u in unmatchedExporters" 
          :key="u.ip_address"
          class="unmatched-card"
        >
          <div class="unmatched-card-info">
            <span class="unmatched-ip tnum font-mono">{{ u.ip_address }}</span>
            <span class="unmatched-sub text-muted" v-if="u.flow_count">
              {{ formatNumber(u.flow_count) }} flows
            </span>
          </div>
          <button
            class="btn-primary btn-small"
            @click="openMappingModal(u.ip_address)"
            :title="`Link ${u.ip_address} as endpoint alias`"
          >
            Link Exporter Alias →
          </button>
        </div>
      </div>
    </div>

    <!-- Top KPI Metric Strip -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Fleet Ingress Rate</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum ingress-text">
            {{ formatBps(overview.total_ingress_bps) }}
          </span>
        </div>
        <div class="kpi-subtext">5-min moving average</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Fleet Egress Rate</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum egress-text">
            {{ formatBps(overview.total_egress_bps) }}
          </span>
        </div>
        <div class="kpi-subtext">5-min moving average</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Active Flow Exporters</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum">
            {{ overview.active_exporters_count }}
          </span>
          <span class="kpi-denom">/ {{ totalEndpointsCount }} nodes</span>
        </div>
        <div class="kpi-subtext">Cisco, Juniper, Fortinet, Mikrotik</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Total Monitored Flows</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum">
            {{ formatNumber(overview.total_flows_count) }}
          </span>
        </div>
        <div class="kpi-subtext">Aggregated conversation bursts</div>
      </div>
    </div>

    <!-- Main Section: Stacked Area Traffic Chart -->
    <div class="chart-section table-card">
      <div class="section-header">
        <div class="section-title">
          Aggregate Bandwidth Profile (Ingress vs. Egress)
        </div>
        <span class="badge-window tnum">{{ selectedWindow }} Window</span>
      </div>
      <div class="chart-container">
        <LineChart
          v-if="chartData.labels.length > 0"
          :data="chartData"
          :options="chartOptions"
        />
        <div v-else-if="!loading" class="no-chart-data">
          No flow records accumulated for the selected {{ selectedWindow }} window.
        </div>
        <div v-else class="loading-spinner">Loading telemetry series...</div>
      </div>
    </div>

    <!-- Secondary Grid: Top Talkers & Application Donut -->
    <div class="secondary-grid">
      <!-- Top Talkers Leaderboard -->
      <div class="table-card talkers-panel">
        <div class="section-header">
          <div class="section-title">Top Communicating Endpoints</div>
          <span class="section-hint">Ranked by volume</span>
        </div>
        <div class="table-responsive">
          <table class="dense-table" aria-label="Top Talkers Table">
            <thead>
              <tr>
                <th>Target Node</th>
                <th class="text-right">Ingress</th>
                <th class="text-right">Egress</th>
                <th class="text-right">Total Bytes</th>
                <th class="text-right">Flows</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in topEndpoints" :key="t.ip_address">
                <td>
                  <div class="node-cell">
                    <span class="node-host font-bold">{{ t.hostname || t.ip_address }}</span>
                    <span class="node-ip tnum text-muted" v-if="t.hostname">{{ t.ip_address }}</span>
                  </div>
                </td>
                <td class="text-right tnum ingress-text">{{ formatBytes(t.ingress_bytes) }}</td>
                <td class="text-right tnum egress-text">{{ formatBytes(t.egress_bytes) }}</td>
                <td class="text-right tnum font-bold">{{ formatBytes(t.total_bytes) }}</td>
                <td class="text-right tnum text-muted">{{ formatNumber(t.flow_count) }}</td>
              </tr>
              <tr v-if="topEndpoints.length === 0">
                <td colspan="5" class="text-center text-muted">No talker statistics in this window.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Application / Protocol Donut -->
      <div class="table-card donut-panel">
        <div class="section-header">
          <div class="section-title">Application Distribution</div>
          <span class="section-hint">Layer 4 / Service Port</span>
        </div>
        <div class="donut-container">
          <DoughnutChart
            v-if="donutData.labels.length > 0"
            :data="donutData"
            :options="donutOptions"
          />
          <div v-else class="no-chart-data">No application telemetry available.</div>
        </div>
      </div>
    </div>

    <!-- Full Width: Top Conversations Table -->
    <div class="table-card conversations-panel">
      <div class="section-header section-header-split">
        <div>
          <div class="section-title">Top Forensic Conversations (IP-to-IP Pairs)</div>
          <span class="section-hint">Forensic tier granularity</span>
        </div>
        <div class="conversation-filter-box">
          <input 
            v-model="conversationFilter" 
            class="conversation-search-input" 
            placeholder="Search IP, hostname, or port..." 
            aria-label="Filter conversations"
          />
        </div>
      </div>
      <div class="table-responsive">
        <table class="dense-table" aria-label="Top Conversations Table">
          <thead>
            <tr>
              <th>Source IP</th>
              <th>Destination IP</th>
              <th>Protocol</th>
              <th>Service Port</th>
              <th class="text-right">Volume</th>
              <th class="text-right">Burst Count</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(c, idx) in filteredConversations" :key="idx">
              <td>
                <span class="tnum font-mono">{{ c.src_ip }}</span>
                <span v-if="c.src_hostname" class="text-muted text-xs block">({{ c.src_hostname }})</span>
              </td>
              <td>
                <span class="tnum font-mono">{{ c.dst_ip }}</span>
                <span v-if="c.dst_hostname" class="text-muted text-xs block">({{ c.dst_hostname }})</span>
              </td>
              <td>
                <span class="status-pill status-unknown">{{ c.protocol }}</span>
              </td>
              <td>
                <span class="service-port-badge" :class="getPortBadgeClass(c.dst_port)">
                  {{ formatPortLabel(c.dst_port, c.protocol) }}
                </span>
              </td>
              <td class="text-right tnum font-bold">{{ formatBytes(c.total_bytes) }}</td>
              <td class="text-right tnum text-muted">{{ formatNumber(c.flow_count) }}</td>
            </tr>
            <tr v-if="filteredConversations.length === 0">
              <td colspan="6" class="text-center text-muted">
                {{ topConversations.length === 0 ? 'No conversations recorded in this window.' : 'No conversations matching current search filter.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Mapping Modal for Unmatched Exporter -->
    <div v-if="showMappingModal" class="modal-overlay" @click.self="showMappingModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Link Exporter Alias</h3>
          <button class="btn-close" @click="showMappingModal = false">✕</button>
        </div>
        <div class="modal-form">
          <p class="text-sm text-secondary">
            Map unmatched IP <strong class="tnum">{{ selectedUnmatchedIp }}</strong> as an alias to an existing monitored endpoint router/switch:
          </p>

          <div class="form-group">
            <label for="endpoint-select">Monitored Target *</label>
            <select
              id="endpoint-select"
              v-model="targetEndpointId"
              class="form-select"
              required
            >
              <option :value="null" disabled>Select target node...</option>
              <option
                v-for="ep in availableEndpoints"
                :key="ep.id"
                :value="ep.id"
              >
                {{ ep.hostname }} ({{ ep.ip_address }})
              </option>
            </select>
          </div>

          <div v-if="mappingError" class="alert-error" role="alert">
            {{ mappingError }}
          </div>

          <div class="modal-actions">
            <button class="btn-secondary" @click="showMappingModal = false">Cancel</button>
            <button
              class="btn-primary"
              @click="submitExporterMapping"
              :disabled="!targetEndpointId || mappingLoading"
            >
              {{ mappingLoading ? 'Saving...' : 'Link Exporter IP' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Line as LineChart, Doughnut as DoughnutChart } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import {
  getBandwidthOverview,
  getTrafficSeries,
  getTopTalkers,
  getApplicationDistribution,
  getFlowExporters,
  mapFlowExporter,
  getEndpoints,
} from '../services/api.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const windowOptions = ['1h', '6h', '24h', '7d', '30d']
const selectedWindow = ref('1h')
const loading = ref(false)

// Auto-Refresh state (UI-07)
const autoRefreshInterval = ref('0')
let refreshTimer = null

function handleAutoRefreshChange() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  const secs = parseInt(autoRefreshInterval.value, 10)
  if (secs > 0) {
    refreshTimer = setInterval(() => {
      if (!loading.value) {
        refreshData()
      }
    }, secs * 1000)
  }
}

const overview = ref({
  total_ingress_bps: 0,
  total_egress_bps: 0,
  active_exporters_count: 0,
  unmatched_exporters_count: 0,
  total_flows_count: 0,
})

const totalEndpointsCount = ref(0)
const availableEndpoints = ref([])
const unmatchedExporters = ref([])

const topEndpoints = ref([])
const topConversations = ref([])
const applicationStats = ref([])

// Top conversations search filter (UI-09)
const conversationFilter = ref('')
const filteredConversations = computed(() => {
  if (!conversationFilter.value.trim()) return topConversations.value
  const q = conversationFilter.value.toLowerCase().trim()
  return topConversations.value.filter((c) => {
    return (
      (c.src_ip && c.src_ip.toLowerCase().includes(q)) ||
      (c.dst_ip && c.dst_ip.toLowerCase().includes(q)) ||
      (c.src_hostname && c.src_hostname.toLowerCase().includes(q)) ||
      (c.dst_hostname && c.dst_hostname.toLowerCase().includes(q)) ||
      String(c.dst_port).includes(q) ||
      (c.protocol && c.protocol.toLowerCase().includes(q))
    )
  })
})

function formatPortLabel(port, proto) {
  const p = Number(port)
  switch (p) {
    case 443: return '443 / HTTPS'
    case 80: return '80 / HTTP'
    case 53: return '53 / DNS'
    case 22: return '22 / SSH'
    case 123: return '123 / NTP'
    case 161: return '161 / SNMP'
    case 2055: return '2055 / NetFlow'
    case 4739: return '4739 / IPFIX'
    default: return `${port}`
  }
}

function getPortBadgeClass(port) {
  const p = Number(port)
  if (p === 443 || p === 80) return 'port-web'
  if (p === 53) return 'port-dns'
  if (p === 22) return 'port-ssh'
  if (p === 2055 || p === 4739) return 'port-telemetry'
  return 'port-generic'
}

// Mapping Modal
const showMappingModal = ref(false)
const selectedUnmatchedIp = ref('')
const targetEndpointId = ref(null)
const mappingLoading = ref(false)
const mappingError = ref(null)

// Chart Data
const seriesPoints = ref([])

const chartData = computed(() => {
  const labels = seriesPoints.value.map((p) => {
    const d = new Date(p.timestamp)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })

  return {
    labels,
    datasets: [
      {
        label: 'Ingress (bps)',
        data: seriesPoints.value.map((p) => p.ingress_bps),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.25)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
      },
      {
        label: 'Egress (bps)',
        data: seriesPoints.value.map((p) => p.egress_bps),
        borderColor: '#0ea5e9',
        backgroundColor: 'rgba(14, 165, 233, 0.25)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
      },
    ],
  }
})

// Dynamic theme-adaptive Chart.js options (UI-08)
const chartOptions = computed(() => {
  const isDark = typeof document !== 'undefined' && 
    (document.documentElement.classList.contains('dark') || !document.documentElement.classList.contains('light'))
  const textColor = isDark ? '#9ca3af' : '#4b5563'
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'

  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: textColor, font: { family: 'Inter', size: 11 } },
      },
      y: {
        ticks: {
          color: textColor,
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (val) => formatBps(val),
        },
        grid: { color: gridColor },
      },
    },
    plugins: {
      legend: {
        position: 'top',
        labels: { color: textColor, font: { family: 'Inter', size: 12 } },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${formatBps(ctx.raw)}`,
        },
      },
    },
  }
})

const donutData = computed(() => {
  const labels = applicationStats.value.map((a) => a.service_label)
  const data = applicationStats.value.map((a) => a.total_bytes)
  const colors = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#EC4899', '#06B6D4', '#14B8A6', '#84CC16', '#6366F1'
  ]

  return {
    labels,
    datasets: [
      {
        data,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 1,
      },
    ],
  }
})

const donutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'right',
      labels: { color: '#888888', font: { size: 11 } },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.label}: ${formatBytes(ctx.raw)}`,
      },
    },
  },
}

function setWindow(w) {
  selectedWindow.value = w
  refreshData()
}

function formatBps(bps) {
  if (!bps || bps <= 0) return '0 bps'
  if (bps >= 1e9) return `${(bps / 1e9).toFixed(2)} Gbps`
  if (bps >= 1e6) return `${(bps / 1e6).toFixed(2)} Mbps`
  if (bps >= 1e3) return `${(bps / 1e3).toFixed(1)} kbps`
  return `${Math.round(bps)} bps`
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(2)} TB`
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(2)} GB`
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(2)} MB`
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} KB`
  return `${bytes} B`
}

function formatNumber(num) {
  if (!num) return '0'
  return new Intl.NumberFormat().format(num)
}

function openMappingModal(ip) {
  selectedUnmatchedIp.value = ip
  targetEndpointId.value = availableEndpoints.value.length > 0 ? availableEndpoints.value[0].id : null
  mappingError.value = null
  showMappingModal.value = true
}

async function submitExporterMapping() {
  if (!targetEndpointId.value || !selectedUnmatchedIp.value) return
  mappingLoading.value = true
  mappingError.value = null
  try {
    await mapFlowExporter(selectedUnmatchedIp.value, targetEndpointId.value)
    showMappingModal.value = false
    await refreshData()
  } catch (err) {
    mappingError.value = err.response?.data?.detail || 'Failed to map exporter IP.'
  } finally {
    mappingLoading.value = false
  }
}

async function refreshData() {
  loading.value = true
  try {
    const [ovRes, seriesRes, talkersRes, appRes, expRes, epListRes] = await Promise.all([
      getBandwidthOverview(),
      getTrafficSeries(selectedWindow.value),
      getTopTalkers(selectedWindow.value, 10),
      getApplicationDistribution(selectedWindow.value),
      getFlowExporters(),
      getEndpoints(),
    ])

    if (ovRes.data?.data) {
      overview.value = ovRes.data.data
    }
    if (seriesRes.data?.data?.points) {
      seriesPoints.value = seriesRes.data.data.points
    }
    if (talkersRes.data?.data) {
      topEndpoints.value = talkersRes.data.data.top_endpoints || []
      topConversations.value = talkersRes.data.data.top_conversations || []
    }
    if (appRes.data?.data?.applications) {
      applicationStats.value = appRes.data.data.applications
    }
    if (expRes.data?.data) {
      unmatchedExporters.value = expRes.data.data.unmatched || []
    }
    if (epListRes.data?.data) {
      availableEndpoints.value = epListRes.data.data
      totalEndpointsCount.value = epListRes.data.data.length
    }
  } catch (err) {
    console.error('Failed to load bandwidth telemetry data:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshData()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.bandwidth-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.bandwidth-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.toolbar-sub-row {
  margin-top: 4px;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.page-sub {
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.window-pills {
  display: flex;
  background: var(--bg-surface-selected);
  border-radius: var(--radius-sm, 6px);
  padding: 2px;
  gap: 2px;
}

.btn-pill {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-pill.active {
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: var(--shadow);
}

/* Unmatched Discovery Alert */
.unmatched-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-radius: var(--radius, 8px);
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.4);
  color: #b45309;
}
html.dark .unmatched-banner {
  background: rgba(245, 158, 11, 0.15);
  border-color: rgba(245, 158, 11, 0.5);
  color: #fbbf24;
}

.unmatched-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.unmatched-content {
  flex: 1;
}

.unmatched-title {
  font-size: 0.875rem;
  font-weight: 700;
}

.unmatched-desc {
  font-size: 0.8125rem;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.unmatched-ip-chip {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-weight: 600;
}

/* KPI Metric Strip */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.kpi-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius, 8px);
  padding: 16px;
  box-shadow: var(--shadow);
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 6px 0 2px 0;
}

.kpi-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.kpi-denom {
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.kpi-subtext {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.ingress-text {
  color: #10b981;
}
.egress-text {
  color: #0ea5e9;
}

/* Charts & Panels */
.chart-section {
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
}

.section-title {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
}

.section-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.badge-window {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  font-weight: 600;
}

.chart-container {
  height: 320px;
  position: relative;
}

.no-chart-data, .loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Secondary Grid */
.secondary-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

@media (max-width: 1024px) {
  .secondary-grid {
    grid-template-columns: 1fr;
  }
}

.donut-panel {
  padding: 16px;
}

.donut-container {
  height: 280px;
  position: relative;
}

.node-cell {
  display: flex;
  flex-direction: column;
}

.node-host {
  font-size: 0.8125rem;
}

.node-ip {
  font-size: 0.75rem;
}

.text-right {
  text-align: right;
}
.text-center {
  text-align: center;
}
.font-bold {
  font-weight: 700;
}
.font-mono {
  font-family: var(--font-mono);
}
.block {
  display: block;
}
.text-xs {
  font-size: 0.6875rem;
}

/* Auto-Refresh (UI-07) */
.auto-refresh-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}

.refresh-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
}

.refresh-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  outline: none;
  cursor: pointer;
}

/* Unmatched Exporter Grid (BUG-05) */
.unmatched-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.unmatched-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 8px;
  width: 100%;
}

.unmatched-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-surface);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.unmatched-card-info {
  display: flex;
  flex-direction: column;
}

.unmatched-ip {
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.unmatched-sub {
  font-size: 0.7rem;
}

/* Top Conversations Header & Search (UI-09) */
.section-header-split {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.conversation-search-input {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  width: 220px;
  outline: none;
}

.conversation-search-input:focus {
  border-color: var(--accent, #3b82f6);
}

/* Service Port Badges (UI-09) */
.service-port-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  font-feature-settings: 'tnum';
  font-weight: 600;
}

.port-web {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.port-dns {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.port-ssh {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.port-telemetry {
  background: rgba(139, 92, 246, 0.12);
  color: #8b5cf6;
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.port-generic {
  background: rgba(107, 114, 128, 0.12);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}
</style>
