<template>
  <div class="bandwidth-view">
    <!-- Header Toolbar -->
    <div class="bandwidth-toolbar">
      <div class="toolbar-left">
        <h1 class="page-title">Network Bandwidth & Flow Telemetry</h1>
        <div class="toolbar-sub-row">
          <span class="page-sub">
            v3.3.0 Flow Engine
            <span class="separator">·</span>
            NetFlow v5, NetFlow v9 & IPFIX
          </span>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- Scope Switcher (Network Aggregate vs Individual Exporter) -->
        <div class="scope-selector">
          <label class="scope-label" for="scope-select">Scope:</label>
          <div class="scope-input-wrapper">
            <input
              v-if="flowExporters.length > 5 || unmatchedExporters.length > 0"
              v-model="exporterSearchText"
              type="text"
              class="scope-search-input"
              placeholder="Filter devices..."
              aria-label="Filter flow exporters"
            />
            <select
              id="scope-select"
              v-model="selectedExporterId"
              @change="handleScopeChange"
              class="scope-select"
            >
              <option value="">🌐 All Network Traffic (Global Overview)</option>
              <optgroup
                v-if="filteredFlowExporters.length > 0"
                :label="`Configured Flow Exporters (${filteredFlowExporters.length})`"
              >
                <option v-for="exp in filteredFlowExporters" :key="exp.id" :value="exp.id">
                  🟢 {{ exp.hostname }} ({{ exp.primary_ip }})
                </option>
              </optgroup>
              <optgroup
                v-if="filteredUnmatchedExporters.length > 0"
                :label="`Discovered Sources (Unregistered - ${filteredUnmatchedExporters.length})`"
              >
                <option
                  v-for="u in filteredUnmatchedExporters"
                  :key="u.ip_address"
                  :value="`unmatched:${u.ip_address}`"
                >
                  ⚠ {{ u.ip_address }} (Unregistered - {{ formatNumber(u.flow_count || 0) }} flows)
                </option>
              </optgroup>
              <option
                v-if="filteredFlowExporters.length === 0 && filteredUnmatchedExporters.length === 0 && exporterSearchText"
                disabled
                value=""
              >
                No matching flow exporters found
              </option>
            </select>
          </div>
        </div>

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

    <!-- Unregistered Exporter Focus Callout -->
    <div
      v-if="isUnmatchedScope"
      class="unmatched-scope-card table-card"
      role="alert"
      aria-live="polite"
    >
      <div class="unmatched-scope-header">
        <span class="unmatched-scope-icon">⚠</span>
        <div class="unmatched-scope-info">
          <div class="unmatched-scope-badge">DISCOVERED FLOW SOURCE (UNREGISTERED)</div>
          <h2 class="unmatched-scope-title">
            Unregistered Device Streaming Flows: <span class="font-mono text-accent">{{ activeUnmatchedIp }}</span>
          </h2>
          <p class="unmatched-scope-desc">
            LNMP is actively receiving NetFlow/IPFIX UDP packets from <strong>{{ activeUnmatchedIp }}</strong>, but this device is not yet registered in NetMon's endpoint inventory. Flow packets are currently staged in discovery. To enable per-interface metrics, line-speed utilization, and historical conversation tracking, enroll this source as an endpoint or link it as an alias to an existing router.
          </p>
        </div>
      </div>
      <div class="unmatched-scope-actions">
        <button
          class="btn-primary"
          @click="openEnrollModal(activeUnmatchedIp)"
        >
          + Enroll {{ activeUnmatchedIp }} as Flow Exporter
        </button>
        <button
          class="btn-secondary"
          @click="openMappingModal(activeUnmatchedIp)"
        >
          Link to Existing Endpoint Alias →
        </button>
        <button
          class="btn-text"
          @click="selectedExporterId = ''; handleScopeChange()"
        >
          Return to All Traffic
        </button>
      </div>
    </div>

    <!-- Unmatched Exporter Discovery Banner (BUG-05 Multi-IP Grid) -->
    <div
      v-if="unmatchedExporters.length > 0 && !isUnmatchedScope"
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
          <div class="unmatched-card-actions">
            <button
              class="btn-primary btn-small"
              @click="openEnrollModal(u.ip_address)"
              :title="`Enroll ${u.ip_address} as dedicated flow exporter`"
            >
              + Enroll Exporter
            </button>
            <button
              class="btn-secondary btn-small"
              @click="openMappingModal(u.ip_address)"
              :title="`Link ${u.ip_address} as endpoint alias`"
            >
              Link Alias →
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Top KPI Metric Strip -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Ingress Rate</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum ingress-text">
            {{ formatBps(overview.total_ingress_bps) }}
          </span>
        </div>
        <div class="kpi-subtext">5-min network moving average</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">Total Egress Rate</div>
        <div class="kpi-value-row">
          <span class="kpi-value tnum egress-text">
            {{ formatBps(overview.total_egress_bps) }}
          </span>
        </div>
        <div class="kpi-subtext">5-min network moving average</div>
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

    <!-- Interface Telemetry Grid (ManageEngine NetFlow Analyzer Snapshot Benchmark) -->
    <div v-if="selectedExporterId && interfaceList.length > 0" class="table-card interfaces-panel">
      <div class="section-header section-header-split">
        <div>
          <div class="section-title">Active Router Interfaces & Telemetry</div>
          <span class="section-hint">{{ interfaceList.length }} Interfaces Detected · Click row to isolate throughput</span>
        </div>
        <div v-if="selectedInterfaceIdx !== null" class="isolated-badge-row">
          <span class="status-pill status-isolated">
            Isolating Interface #{{ selectedInterfaceIdx }}
          </span>
          <button class="btn-text btn-small" @click="clearInterfaceIsolation">Clear Isolation ✕</button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="dense-table interactive-table" aria-label="Interface Telemetry Table">
          <thead>
            <tr>
              <th style="width: 80px;">Index</th>
              <th>Interface Name / Alias</th>
              <th class="text-right">Link Speed</th>
              <th class="text-right">Ingress Rate</th>
              <th class="text-right">Egress Rate</th>
              <th style="width: 200px;">Utilization</th>
              <th class="text-center" style="width: 90px;">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in interfaceList"
              :key="item.interface_idx"
              :class="{ 'row-selected': selectedInterfaceIdx === item.interface_idx }"
              @click="toggleInterfaceIsolation(item.interface_idx)"
              class="cursor-pointer"
            >
              <td class="font-mono tnum">#{{ item.interface_idx }}</td>
              <td>
                <span class="font-bold">{{ item.name }}</span>
              </td>
              <td class="text-right tnum text-muted">{{ formatSpeed(item.speed_mbps) }}</td>
              <td class="text-right tnum ingress-text">{{ formatBps(item.in_bps) }}</td>
              <td class="text-right tnum egress-text">{{ formatBps(item.out_bps) }}</td>
              <td>
                <div class="util-cell">
                  <div class="util-bar-bg">
                    <div
                      class="util-bar-fill"
                      :class="getUtilClass(item.utilization_percentage)"
                      :style="{ width: `${Math.min(100, item.utilization_percentage)}%` }"
                    ></div>
                  </div>
                  <span class="util-text tnum" :class="getUtilClass(item.utilization_percentage)">
                    {{ item.utilization_percentage.toFixed(1) }}%
                  </span>
                </div>
              </td>
              <td class="text-center">
                <span :class="item.is_active ? 'badge-active' : 'badge-idle'">
                  {{ item.is_active ? 'Active' : 'Idle' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
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

    <!-- Enrollment Modal for Unmatched Exporter -->
    <div v-if="showEnrollModal" class="modal-overlay" @click.self="showEnrollModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Enroll Flow Exporter</h3>
          <button class="btn-close" @click="showEnrollModal = false">✕</button>
        </div>
        <div class="modal-form">
          <p class="text-sm text-secondary">
            Enroll streaming device <strong class="tnum">{{ enrollForm.ip_address }}</strong> as a dedicated Flow Exporter node.
          </p>

          <div class="form-group">
            <label for="enroll-hostname">Exporter Hostname *</label>
            <input
              id="enroll-hostname"
              v-model="enrollForm.hostname"
              class="form-input"
              placeholder="e.g. Cisco-Core-01"
              required
            />
          </div>

          <div class="form-group">
            <label for="enroll-desc">Description</label>
            <input
              id="enroll-desc"
              v-model="enrollForm.description"
              class="form-input"
              placeholder="e.g. Edge router sending NetFlow v9"
            />
          </div>

          <div v-if="enrollError" class="alert-error" role="alert">
            {{ enrollError }}
          </div>

          <div class="modal-actions">
            <button class="btn-secondary" @click="showEnrollModal = false">Cancel</button>
            <button
              class="btn-primary"
              @click="submitExporterEnrollment"
              :disabled="!enrollForm.hostname || enrollLoading"
            >
              {{ enrollLoading ? 'Enrolling...' : 'Enroll Exporter' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  enrollFlowExporter,
  mapFlowExporter,
  getInterfaceTelemetry,
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

const route = useRoute()
const router = useRouter()
const selectedExporterId = ref(route.query.exporter_id || '')
const flowExporters = ref([])
const interfaceList = ref([])
const selectedInterfaceIdx = ref(null)

// Exporter Scope Filtering & Unmatched Detection State
const exporterSearchText = ref('')

const isUnmatchedScope = computed(() => {
  return typeof selectedExporterId.value === 'string' && selectedExporterId.value.startsWith('unmatched:')
})

const activeUnmatchedIp = computed(() => {
  if (isUnmatchedScope.value) {
    return selectedExporterId.value.replace('unmatched:', '')
  }
  return ''
})

const filteredFlowExporters = computed(() => {
  const all = flowExporters.value
  if (!exporterSearchText.value.trim()) return all
  const q = exporterSearchText.value.toLowerCase().trim()
  return all.filter((exp) => {
    if (exp.id === selectedExporterId.value) return true
    return (
      (exp.hostname && exp.hostname.toLowerCase().includes(q)) ||
      (exp.primary_ip && exp.primary_ip.toLowerCase().includes(q))
    )
  })
})

const filteredUnmatchedExporters = computed(() => {
  const all = unmatchedExporters.value
  if (!exporterSearchText.value.trim()) return all
  const q = exporterSearchText.value.toLowerCase().trim()
  return all.filter((u) => {
    if (`unmatched:${u.ip_address}` === selectedExporterId.value) return true
    return u.ip_address && u.ip_address.toLowerCase().includes(q)
  })
})

// Enrollment modal state
const showEnrollModal = ref(false)
const enrollForm = ref({
  ip_address: '',
  hostname: '',
  description: '',
  device_role: 'FLOW_EXPORTER',
})
const enrollLoading = ref(false)
const enrollError = ref(null)

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

function formatSpeed(speedMbps) {
  if (!speedMbps) return '1 Gbps'
  if (speedMbps >= 1000000) return `${(speedMbps / 1000000).toFixed(0)} Tbps`
  if (speedMbps >= 1000) return `${(speedMbps / 1000).toFixed(0)} Gbps`
  return `${speedMbps} Mbps`
}

function getUtilClass(util) {
  if (util >= 80) return 'util-danger'
  if (util >= 60) return 'util-warning'
  return 'util-healthy'
}

function handleScopeChange() {
  selectedInterfaceIdx.value = null
  router.push({
    query: {
      ...route.query,
      exporter_id: selectedExporterId.value || undefined,
    },
  })
  refreshData()
}

function toggleInterfaceIsolation(ifIdx) {
  if (selectedInterfaceIdx.value === ifIdx) {
    selectedInterfaceIdx.value = null
  } else {
    selectedInterfaceIdx.value = ifIdx
  }
}

function clearInterfaceIsolation() {
  selectedInterfaceIdx.value = null
}

function openEnrollModal(ip) {
  enrollForm.value = {
    ip_address: ip,
    hostname: `router-${ip.replace(/\./g, '-')}`,
    description: `Flow Exporter streaming from ${ip}`,
    device_role: 'FLOW_EXPORTER',
  }
  enrollError.value = null
  showEnrollModal.value = true
}

async function submitExporterEnrollment() {
  if (!enrollForm.value.hostname || !enrollForm.value.ip_address) return
  enrollLoading.value = true
  enrollError.value = null
  try {
    const res = await enrollFlowExporter(enrollForm.value)
    showEnrollModal.value = false
    if (res.data?.data?.id) {
      selectedExporterId.value = res.data.data.id
      router.push({
        query: {
          ...route.query,
          exporter_id: res.data.data.id,
        },
      })
    }
    await refreshData()
  } catch (err) {
    enrollError.value = err.response?.data?.detail || 'Failed to enroll flow exporter.'
  } finally {
    enrollLoading.value = false
  }
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

  let inData = seriesPoints.value.map((p) => p.ingress_bps)
  let outData = seriesPoints.value.map((p) => p.egress_bps)

  if (selectedInterfaceIdx.value !== null && interfaceList.value.length > 0) {
    const matched = interfaceList.value.find(i => i.interface_idx === selectedInterfaceIdx.value)
    if (matched) {
      const totalIn = interfaceList.value.reduce((acc, i) => acc + i.in_bps, 0) || 1
      const totalOut = interfaceList.value.reduce((acc, i) => acc + i.out_bps, 0) || 1
      const inRatio = Math.min(1.0, matched.in_bps / totalIn)
      const outRatio = Math.min(1.0, matched.out_bps / totalOut)
      inData = inData.map(v => Math.round(v * inRatio))
      outData = outData.map(v => Math.round(v * outRatio))
    }
  }

  const inLabel = selectedInterfaceIdx.value !== null
    ? `Interface #${selectedInterfaceIdx.value} Ingress (bps)`
    : 'Ingress (bps)'
  const outLabel = selectedInterfaceIdx.value !== null
    ? `Interface #${selectedInterfaceIdx.value} Egress (bps)`
    : 'Egress (bps)'

  return {
    labels,
    datasets: [
      {
        label: inLabel,
        data: inData,
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.25)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
      },
      {
        label: outLabel,
        data: outData,
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
  if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)} Mbps`
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
    const targetId = targetEndpointId.value
    await mapFlowExporter(selectedUnmatchedIp.value, targetId)
    showMappingModal.value = false
    selectedExporterId.value = targetId
    router.push({
      query: {
        ...route.query,
        exporter_id: targetId,
      },
    })
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
    const expId = (!isUnmatchedScope.value && selectedExporterId.value) ? selectedExporterId.value : null
    const [ovRes, seriesRes, talkersRes, appRes, expRes, epListRes, ifRes] = await Promise.all([
      getBandwidthOverview(),
      getTrafficSeries(selectedWindow.value, expId),
      getTopTalkers(selectedWindow.value, 10, null, expId),
      getApplicationDistribution(selectedWindow.value),
      getFlowExporters(),
      getEndpoints(),
      expId ? getInterfaceTelemetry(expId, selectedWindow.value) : Promise.resolve({ data: { data: { interfaces: [] } } }),
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
      flowExporters.value = expRes.data.data.exporters || []
    }
    if (epListRes.data?.data) {
      availableEndpoints.value = epListRes.data.data
      totalEndpointsCount.value = epListRes.data.data.length
    }
    if (ifRes?.data?.data?.interfaces) {
      interfaceList.value = ifRes.data.data.interfaces
    } else {
      interfaceList.value = []
    }
  } catch (err) {
    console.error('Failed to load bandwidth telemetry data:', err)
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query.exporter_id,
  (newId) => {
    if (newId !== selectedExporterId.value) {
      selectedExporterId.value = newId || ''
      selectedInterfaceIdx.value = null
      refreshData()
    }
  }
)

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

/* Scope Selector */
.scope-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}

.scope-input-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
}

.scope-search-input {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  width: 110px;
  outline: none;
  transition: border-color 0.15s ease, width 0.15s ease;
}

.scope-search-input:focus {
  border-color: var(--accent, #3b82f6);
  width: 150px;
}

.scope-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
}

.scope-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  outline: none;
  cursor: pointer;
  max-width: 280px;
}

/* Unmatched Scope Focused Callout */
.unmatched-scope-card {
  padding: 18px 22px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: var(--radius, 8px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
html.dark .unmatched-scope-card {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.45);
}

.unmatched-scope-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.unmatched-scope-icon {
  font-size: 2rem;
  line-height: 1;
  color: #f59e0b;
}

.unmatched-scope-info {
  flex: 1;
}

.unmatched-scope-badge {
  display: inline-block;
  font-size: 0.6875rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(245, 158, 11, 0.2);
  color: #d97706;
  margin-bottom: 6px;
}
html.dark .unmatched-scope-badge {
  color: #fbbf24;
}

.unmatched-scope-title {
  margin: 0 0 6px 0;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
}

.unmatched-scope-desc {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.unmatched-scope-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-left: 48px;
  flex-wrap: wrap;
}

.unmatched-card-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* Interface Telemetry Panel */
.interfaces-panel {
  margin-top: 1.5rem;
}

.interactive-table tr.cursor-pointer {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.interactive-table tr.row-selected {
  background: rgba(99, 102, 241, 0.15) !important;
  border-left: 3px solid #6366f1;
}

.isolated-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-isolated {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.3);
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
}

.util-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.util-bar-bg {
  flex: 1;
  height: 6px;
  background: var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 3px;
  overflow: hidden;
}

.util-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.util-bar-fill.util-healthy {
  background: #10b981;
}

.util-bar-fill.util-warning {
  background: #f59e0b;
}

.util-bar-fill.util-danger {
  background: #ef4444;
}

.util-text {
  font-size: 0.75rem;
  font-weight: 700;
  width: 45px;
  text-align: right;
}

.util-text.util-healthy {
  color: #10b981;
}

.util-text.util-warning {
  color: #f59e0b;
}

.util-text.util-danger {
  color: #ef4444;
}

.badge-active {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge-idle {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
  border: 1px solid rgba(156, 163, 175, 0.3);
}
</style>
