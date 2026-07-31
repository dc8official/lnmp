<template>
  <div class="rca-container">
    <!-- Header / Refresh Bar -->
    <div class="rca-header">
      <div class="header-title-group">
        <h3 class="rca-title">
          <span class="icon">🔍</span> Comparative Root Cause Analysis (RCA)
        </h3>
        <span v-if="endpointData?.is_l2_segment || rcaData?.is_l2_segment" class="l2-badge">
          ⚡ Local L2 Network Segment
        </span>
      </div>
      <div class="header-actions">
        <button 
          class="btn-discovery" 
          @click="runRouteDiscovery" 
          :disabled="discovering"
          title="Manually execute traceroute and refresh last-known-good baseline route"
        >
          <span v-if="discovering" class="spinner-inline"></span>
          <span v-else>📡 Run Route Discovery</span>
        </button>
        <button class="btn-refresh" @click="loadData" :disabled="loading">
          {{ loading ? 'Updating...' : '↻ Refresh RCA' }}
        </button>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="alert-error">
      <span>⚠️ {{ error }}</span>
      <button class="btn-retry" @click="loadData">Retry</button>
    </div>

    <!-- Loading State -->
    <div v-if="loading && !rcaData" class="loading-state">
      <div class="spinner"></div>
      <p>Analyzing route baselines and failure snapshots...</p>
    </div>

    <!-- RCA Summary & Status Banner -->
    <div v-else-if="rcaData" class="rca-content">
      <div class="summary-banner" :class="getBannerClass(rcaData)">
        <div class="banner-icon">
          {{ rcaData.failed_hop_ip ? '🚨' : '✅' }}
        </div>
        <div class="banner-text">
          <div class="banner-title-row">
            <span class="banner-status-badge" :class="rcaData.is_resolved ? 'resolved' : 'active'">
              {{ rcaData.is_resolved ? 'INCIDENT RESOLVED' : 'ACTIVE OUTAGE' }}
            </span>
            <span class="incident-time">
              Recorded: {{ formatDate(rcaData.incident_timestamp) }}
            </span>
          </div>
          <p class="summary-message">{{ rcaData.rca_summary || 'No diagnostic RCA details recorded.' }}</p>
          <div class="summary-meta-pills" v-if="rcaData.failed_hop_ip">
            <span class="meta-pill failure">
              <strong>Failed Hop:</strong> Hop {{ rcaData.failed_hop_number }} ({{ rcaData.failed_hop_ip }})
            </span>
            <span class="meta-pill good" v-if="rcaData.last_known_good_hop_ip">
              <strong>Last Known Good:</strong> {{ rcaData.last_known_good_hop_ip }}
            </span>
          </div>
        </div>
      </div>

      <!-- Side-by-Side Path Inspector Table -->
      <div class="path-inspector-card">
        <div class="card-header">
          <h4>🛣 Route Baseline vs. Failure Snapshot</h4>
          <span class="subtext">Comparative differential analysis of live traceroute against last-known-online baseline</span>
        </div>

        <div class="table-responsive">
          <table class="path-table">
            <thead>
              <tr>
                <th class="col-hop">HOP #</th>
                <th class="col-baseline">LAST KNOWN ONLINE BASELINE (IP & RTT)</th>
                <th class="col-failure">FAILURE TRACE SNAPSHOT (IP & RTT)</th>
                <th class="col-status">DIFFERENTIAL STATUS</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="row in combinedHops" 
                :key="row.hop"
                :class="{ 'row-failure': row.isFailureHop, 'row-divergence': row.isDivergent }"
              >
                <td class="col-hop">
                  <span class="hop-badge">Hop {{ row.hop }}</span>
                </td>
                <td class="col-baseline">
                  <div class="hop-cell" v-if="row.baseline">
                    <span class="ip-addr" :class="{ 'text-muted': !row.baseline.ip }">
                      {{ row.baseline.ip || 'TIMEOUT (* * *)' }}
                    </span>
                    <span class="rtt-val" v-if="row.baseline.rtt_ms !== null && row.baseline.rtt_ms !== undefined">
                      {{ row.baseline.rtt_ms.toFixed(2) }} ms
                    </span>
                  </div>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="col-failure">
                  <div class="hop-cell" v-if="row.failure">
                    <span class="ip-addr" :class="{ 'text-muted': !row.failure.ip, 'text-danger': row.isFailureHop }">
                      {{ row.failure.ip || 'TIMEOUT (* * *)' }}
                    </span>
                    <span class="rtt-val" v-if="row.failure.rtt_ms !== null && row.failure.rtt_ms !== undefined">
                      {{ row.failure.rtt_ms.toFixed(2) }} ms
                    </span>
                  </div>
                  <span v-else class="text-muted">—</span>
                </td>
                <td class="col-status">
                  <span v-if="row.isFailureHop" class="diff-badge failure-point">
                    ⚠️ FAILURE POINT
                  </span>
                  <span v-else-if="row.isDivergent" class="diff-badge divergent">
                    ⚡ DIVERGENCE
                  </span>
                  <span v-else-if="row.isMatched" class="diff-badge matched">
                    ✓ MATCHED
                  </span>
                  <span v-else class="diff-badge neutral">
                    —
                  </span>
                </td>
              </tr>

              <tr v-if="combinedHops.length === 0">
                <td colspan="4" class="empty-table">
                  No route baseline or failure trace snapshots available for comparison.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Empty State when no RCA incidents present -->
    <div v-else class="empty-rca-state">
      <div class="empty-icon">🛡️</div>
      <h4>No RCA Incidents Recorded</h4>
      <p>This endpoint has no recorded outage RCA incidents. Run route discovery to establish a last-known-good baseline.</p>
    </div>

    <!-- Endpoint Governance Controls Section -->
    <div class="governance-card">
      <div class="card-header">
        <h4>⚙️ Endpoint Governance Controls</h4>
        <span class="subtext">Configure automated RCA differential engine and scheduled midnight discovery cycles</span>
      </div>

      <div class="toggles-grid">
        <!-- Toggle 1: Enable RCA -->
        <div class="governance-toggle-item">
          <div class="toggle-info">
            <label class="toggle-title">Enable Root Cause Analysis (RCA)</label>
            <p class="toggle-description">
              Automatically triggers differential route analysis and divergence mapping when this endpoint transitions to DOWN.
            </p>
          </div>
          <div class="toggle-control">
            <label class="switch">
              <input 
                type="checkbox" 
                v-model="governance.enable_rca" 
                @change="updateGovernance"
                :disabled="savingGovernance"
              />
              <span class="slider round"></span>
            </label>
            <span class="toggle-status-text" :class="governance.enable_rca ? 'text-active' : 'text-disabled'">
              {{ governance.enable_rca ? 'ACTIVE' : 'OFF' }}
            </span>
          </div>
        </div>

        <!-- Toggle 2: Midnight Scheduled Discovery -->
        <div class="governance-toggle-item">
          <div class="toggle-info">
            <label class="toggle-title">Midnight Scheduled Discovery</label>
            <p class="toggle-description">
              Includes this endpoint in sequential 00:00 midnight traceroute discovery worker passes to update baseline routes.
            </p>
          </div>
          <div class="toggle-control">
            <label class="switch">
              <input 
                type="checkbox" 
                v-model="governance.enable_scheduled_discovery" 
                @change="updateGovernance"
                :disabled="savingGovernance"
              />
              <span class="slider round"></span>
            </label>
            <span class="toggle-status-text" :class="governance.enable_scheduled_discovery ? 'text-active' : 'text-disabled'">
              {{ governance.enable_scheduled_discovery ? 'ACTIVE' : 'OFF' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getEndpointRca, getEndpoint, updateEndpoint, refreshEndpointBaseline } from '../services/api.js'

const props = defineProps({
  endpointId: {
    type: String,
    required: true
  },
  endpoint: {
    type: Object,
    default: null
  }
})

const loading = ref(true)
const error = ref(null)
const discovering = ref(false)
const savingGovernance = ref(false)

const rcaData = ref(null)
const endpointData = ref(props.endpoint)

const governance = ref({
  enable_rca: true,
  enable_scheduled_discovery: true,
  is_l2_segment: false
})

// Helper date formatter
function formatDate(isoStr) {
  if (!isoStr) return 'N/A'
  return new Date(isoStr).toLocaleString()
}

function getBannerClass(rca) {
  if (!rca) return ''
  if (rca.is_resolved) return 'banner-resolved'
  return 'banner-down'
}

// Side-by-side comparative hop merger
const combinedHops = computed(() => {
  if (!rcaData.value) return []

  const baselineHops = rcaData.value.baseline_snapshot?.hops || []
  const failureHops = rcaData.value.failure_trace_snapshot?.hops || []

  const maxHops = Math.max(baselineHops.length, failureHops.length)
  const rows = []

  const failedHopIp = rcaData.value.failed_hop_ip
  const failedHopNum = rcaData.value.failed_hop_number

  for (let i = 1; i <= maxHops; i++) {
    const bHop = baselineHops.find(h => h.hop === i)
    const fHop = failureHops.find(h => h.hop === i)

    const isFailureHop = (failedHopNum === i) || (failedHopIp && fHop && fHop.ip === failedHopIp)
    
    // Check divergence between baseline and failure snapshot at hop i
    let isDivergent = false
    if (bHop && fHop) {
      if (bHop.ip !== fHop.ip) {
        isDivergent = true
      }
    } else if ((bHop && !fHop) || (!bHop && fHop)) {
      isDivergent = true
    }

    const isMatched = bHop && fHop && bHop.ip === fHop.ip && !isFailureHop

    rows.push({
      hop: i,
      baseline: bHop || null,
      failure: fHop || null,
      isFailureHop,
      isDivergent,
      isMatched
    })
  }

  return rows
})

async function loadData() {
  if (!props.endpointId) return
  loading.value = true
  error.value = null

  try {
    const [rcaRes, epRes] = await Promise.all([
      getEndpointRca(props.endpointId).catch(err => ({ data: { data: null } })),
      props.endpoint ? Promise.resolve({ data: { data: props.endpoint } }) : getEndpoint(props.endpointId)
    ])

    rcaData.value = rcaRes.data?.data || null
    if (epRes.data?.data) {
      endpointData.value = epRes.data.data
      governance.value.enable_rca = epRes.data.data.enable_rca !== false
      governance.value.enable_scheduled_discovery = epRes.data.data.enable_scheduled_discovery !== false
      governance.value.is_l2_segment = epRes.data.data.is_l2_segment === true
    }
  } catch (err) {
    console.error('Failed to load RCA data:', err)
    error.value = 'Failed to load RCA incident telemetry.'
  } finally {
    loading.value = false
  }
}

async function runRouteDiscovery() {
  if (!props.endpointId) return
  discovering.value = true
  try {
    await refreshEndpointBaseline(props.endpointId)
    await loadData()
    alert('Route discovery initiated! Baseline route has been refreshed.')
  } catch (err) {
    console.error('Route discovery failed:', err)
    alert('Failed to trigger route discovery.')
  } finally {
    discovering.value = false
  }
}

async function updateGovernance() {
  if (!props.endpointId) return
  savingGovernance.value = true
  try {
    await updateEndpoint(props.endpointId, {
      enable_rca: governance.value.enable_rca,
      enable_scheduled_discovery: governance.value.enable_scheduled_discovery
    })
  } catch (err) {
    console.error('Failed to update governance settings:', err)
    alert('Failed to save governance settings.')
    // Revert state on failure
    await loadData()
  } finally {
    savingGovernance.value = false
  }
}

watch(() => props.endpointId, () => {
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.rca-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: #F3F4F6;
  font-family: Inter, system-ui, -apple-system, sans-serif;
}

.rca-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rca-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: #F9FAFB;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.l2-badge {
  background: rgba(59, 130, 246, 0.15);
  color: #60A5FA;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-discovery {
  background: #2563EB;
  color: #FFFFFF;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-discovery:hover {
  background: #1D4ED8;
}

.btn-discovery:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-refresh {
  background: #374151;
  color: #D1D5DB;
  border: 1px solid #4B5563;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
}

.btn-refresh:hover {
  background: #4B5563;
  color: #FFFFFF;
}

/* Alert Error */
.alert-error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid #EF4444;
  color: #F87171;
  padding: 12px 16px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-retry {
  background: #EF4444;
  color: #FFFFFF;
  border: none;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
}

/* Summary Banner */
.summary-banner {
  display: flex;
  gap: 16px;
  padding: 18px;
  border-radius: 10px;
  background: #1F2937;
  border: 1px solid #374151;
}

.summary-banner.banner-down {
  background: rgba(127, 29, 29, 0.4);
  border: 1px solid #EF4444;
}

.summary-banner.banner-resolved {
  background: rgba(6, 95, 70, 0.4);
  border: 1px solid #10B981;
}

.banner-icon {
  font-size: 2rem;
  line-height: 1;
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.banner-status-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.banner-status-badge.active {
  background: #EF4444;
  color: #FFFFFF;
}

.banner-status-badge.resolved {
  background: #10B981;
  color: #FFFFFF;
}

.incident-time {
  font-size: 0.8rem;
  color: #9CA3AF;
}

.summary-message {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  color: #F9FAFB;
}

.summary-meta-pills {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.meta-pill {
  font-size: 0.85rem;
  padding: 4px 10px;
  border-radius: 6px;
}

.meta-pill.failure {
  background: rgba(239, 68, 68, 0.2);
  color: #FCA5A5;
  border: 1px solid rgba(239, 68, 68, 0.4);
}

.meta-pill.good {
  background: rgba(16, 185, 129, 0.2);
  color: #6EE7B7;
  border: 1px solid rgba(16, 185, 129, 0.4);
}

/* Side-by-side Path Inspector Table */
.path-inspector-card {
  background: #111827;
  border: 1px solid #1F2937;
  border-radius: 10px;
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  background: #1F2937;
  border-bottom: 1px solid #374151;
}

.card-header h4 {
  margin: 0;
  font-size: 1rem;
  color: #F9FAFB;
}

.subtext {
  font-size: 0.8rem;
  color: #9CA3AF;
  margin-top: 4px;
  display: block;
}

.table-responsive {
  overflow-x: auto;
}

.path-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.path-table th, .path-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #1F2937;
}

.path-table th {
  background: #1F2937;
  color: #9CA3AF;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
}

.path-table tr.row-failure {
  background: rgba(239, 68, 68, 0.15);
}

.path-table tr.row-divergence {
  background: rgba(245, 158, 11, 0.1);
}

.hop-badge {
  font-weight: 600;
  color: #9CA3AF;
  background: #1F2937;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.hop-cell {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ip-addr {
  font-family: monospace;
  font-size: 0.9rem;
}

.ip-addr.text-danger {
  color: #F87171;
  font-weight: 700;
}

.rtt-val {
  color: #60A5FA;
  font-size: 0.8rem;
  font-family: monospace;
}

.diff-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}

.diff-badge.failure-point {
  background: #EF4444;
  color: #FFFFFF;
}

.diff-badge.divergent {
  background: #F59E0B;
  color: #FFFFFF;
}

.diff-badge.matched {
  background: rgba(16, 185, 129, 0.2);
  color: #34D399;
}

.diff-badge.neutral {
  color: #6B7280;
}

.empty-table, .empty-rca-state {
  text-align: center;
  padding: 30px;
  color: #9CA3AF;
}

.empty-rca-state .empty-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
}

.empty-rca-state h4 {
  margin: 0;
  color: #F3F4F6;
}

/* Governance Controls */
.governance-card {
  background: #111827;
  border: 1px solid #1F2937;
  border-radius: 10px;
  overflow: hidden;
}

.toggles-grid {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.governance-toggle-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #1F2937;
}

.governance-toggle-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toggle-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #F3F4F6;
}

.toggle-description {
  font-size: 0.8rem;
  color: #9CA3AF;
  margin: 0;
}

.toggle-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-status-text {
  font-size: 0.8rem;
  font-weight: 700;
  min-width: 45px;
}

.toggle-status-text.text-active {
  color: #34D399;
}

.toggle-status-text.text-disabled {
  color: #9CA3AF;
}

/* Switch Styles */
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: #374151;
  transition: .3s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #2563EB;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

.spinner-inline {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #FFFFFF;
  border-radius: 50%;
  animation: spin 0.8s infinite linear;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #2563EB;
  border-radius: 50%;
  animation: spin 1s infinite linear;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
