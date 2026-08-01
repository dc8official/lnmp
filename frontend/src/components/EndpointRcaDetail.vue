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
      <p>This endpoint has no recorded outage RCA incidents.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getEndpointRca, getEndpoint } from '../services/api.js'

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
const rcaData = ref(null)
const endpointData = ref(props.endpoint)

function formatDate(isoStr) {
  if (!isoStr) return 'N/A'
  return new Date(isoStr).toLocaleString()
}

function getBannerClass(rca) {
  if (!rca) return ''
  if (rca.is_resolved) return 'banner-resolved'
  return 'banner-down'
}

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
    }
  } catch (err) {
    console.error('Failed to load RCA data:', err)
    error.value = 'Failed to load RCA incident telemetry.'
  } finally {
    loading.value = false
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
  color: var(--text-primary);
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
  color: var(--text-primary);
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

.btn-refresh {
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.btn-refresh:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

/* Alert Error */
.alert-error {
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid var(--status-down-color);
  color: var(--status-down-color);
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
  background: var(--bg-surface-selected);
  border: 1px solid var(--border-color);
}

.summary-banner.banner-down {
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid var(--status-down-color);
}

.summary-banner.banner-resolved {
  background: rgba(22, 163, 74, 0.12);
  border: 1px solid var(--status-up-color);
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
  color: var(--text-muted);
}

.summary-message {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-primary);
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
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  background: var(--bg-surface-selected);
  border-bottom: 1px solid var(--border-color);
}

.card-header h4 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.subtext {
  font-size: 0.8rem;
  color: var(--text-muted);
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
  border-bottom: 1px solid var(--border-color);
}

.path-table th {
  background: var(--bg-surface-selected);
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
}

.path-table tr.row-failure {
  background: rgba(239, 68, 68, 0.1);
}

.path-table tr.row-divergence {
  background: rgba(245, 158, 11, 0.08);
}

.hop-badge {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-surface-selected);
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
  color: var(--status-down-color);
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
  color: var(--text-muted);
}

.empty-table, .empty-rca-state {
  text-align: center;
  padding: 30px;
  color: var(--text-muted);
}

.empty-rca-state .empty-icon {
  font-size: 2.5rem;
  margin-bottom: 8px;
}

.empty-rca-state h4 {
  margin: 0;
  color: var(--text-primary);
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: #2563EB;
  border-radius: 50%;
  animation: spin 1s infinite linear;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Light mode contrast overrides */
:global(html:not(.dark)) .l2-badge {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.25);
}

:global(html:not(.dark)) .meta-pill.failure {
  background: rgba(220, 38, 38, 0.1);
  color: #b91c1c;
  border-color: rgba(220, 38, 38, 0.2);
}

:global(html:not(.dark)) .meta-pill.good {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
  border-color: rgba(22, 163, 74, 0.2);
}

:global(html:not(.dark)) .diff-badge.matched {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}

:global(html:not(.dark)) .diff-badge.divergent {
  background: #b45309;
}

:global(html:not(.dark)) .rtt-val {
  color: #1d4ed8;
}
</style>
