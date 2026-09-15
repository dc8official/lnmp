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

    <!-- Unmatched Exporter Discovery Banner -->
    <div
      v-if="unmatchedExporters.length > 0"
      class="unmatched-banner"
      role="alert"
      aria-live="polite"
    >
      <div class="unmatched-icon">⚠</div>
      <div class="unmatched-content">
        <div class="unmatched-title">
          Unmatched Exporter Discovery: {{ unmatchedExporters.length }} Unknown Router/Switch Detected
        </div>
        <div class="unmatched-desc">
          Incoming NetFlow/IPFIX streams detected from unmonitored IP(s):
          <span
            v-for="u in unmatchedExporters"
            :key="u.ip_address"
            class="unmatched-ip-chip tnum"
          >
            {{ u.ip_address }}
          </span>
        </div>
      </div>
      <div class="unmatched-actions">
        <button
          class="btn-primary btn-small"
          @click="openMappingModal(unmatchedExporters[0].ip_address)"
        >
          Link as Exporter Alias
        </button>
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
      <div class="section-header">
        <div class="section-title">Top Forensic Conversations (IP-to-IP Pairs)</div>
        <span class="section-hint">Forensic tier granularity</span>
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
            <tr v-for="(c, idx) in topConversations" :key="idx">
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
                <span class="tnum font-mono">{{ c.dst_port }}</span>
              </td>
              <td class="text-right tnum font-bold">{{ formatBytes(c.total_bytes) }}</td>
              <td class="text-right tnum text-muted">{{ formatNumber(c.flow_count) }}</td>
            </tr>
            <tr v-if="topConversations.length === 0">
              <td colspan="6" class="text-center text-muted">No conversations recorded in this window.</td>
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
import { ref, onMounted, computed } from 'vue'
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

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#888888', font: { family: 'Inter', size: 11 } },
    },
    y: {
      ticks: {
        color: '#888888',
        font: { family: 'JetBrains Mono', size: 11 },
        callback: (val) => formatBps(val),
      },
      grid: { color: 'rgba(128, 128, 128, 0.1)' },
    },
  },
  plugins: {
    legend: {
      position: 'top',
      labels: { color: '#888888', font: { family: 'Inter', size: 12 } },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${formatBps(ctx.raw)}`,
      },
    },
  },
}

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
</style>
