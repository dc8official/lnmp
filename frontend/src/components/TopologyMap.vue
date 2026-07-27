<template>
  <div class="topology-container">
    <!-- Map Toolbar -->
    <div class="topology-toolbar">
      <div class="toolbar-left">
        <h2 class="topology-title">
          <span class="icon">🕸</span> Live Network Topology Map
        </h2>
        <span class="status-badge" :class="stabilized ? 'badge-stabilized' : 'badge-stabilizing'">
          {{ stabilized ? '● Layout Fixed (Physics Off)' : '◌ Stabilizing Layout...' }}
        </span>
      </div>
      <div class="toolbar-right">
        <button class="btn-secondary" @click="fetchTopology" :disabled="loading">
          {{ loading ? 'Updating...' : '↻ Refresh Topology' }}
        </button>
      </div>
    </div>

    <!-- Canvas Container -->
    <div class="canvas-wrapper">
      <div ref="container" class="vis-network-canvas"></div>

      <!-- Loading / Error Overlays -->
      <div v-if="loading && !networkInitialized" class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading topology map...</p>
      </div>
      <div v-if="error" class="error-overlay">
        <p class="error-msg">⚠️ {{ error }}</p>
        <button class="btn-primary" @click="fetchTopology">Retry</button>
      </div>

      <!-- Legend Overlay -->
      <div class="map-legend">
        <div class="legend-title">Topology Legend</div>
        <div class="legend-items">
          <div class="legend-item"><span class="node-icon circle state-up"></span> Monitored UP</div>
          <div class="legend-item"><span class="node-icon circle state-unstable"></span> Monitored UNSTABLE</div>
          <div class="legend-item"><span class="node-icon circle state-down"></span> Monitored DOWN</div>
          <div class="legend-item"><span class="node-icon hexagon state-transit"></span> Transit Router</div>
          <div class="legend-item"><span class="node-icon hexagon state-inferred-down"></span> Transit INFERRED DOWN</div>
        </div>
      </div>

      <!-- Node Inspector Side Drawer -->
      <div class="inspector-drawer" :class="{ open: selectedNode !== null }">
        <div class="drawer-header" v-if="selectedNode">
          <div>
            <h3 class="drawer-title">{{ selectedNode.label }}</h3>
            <p class="drawer-sub">{{ selectedNode.ip_address }}</p>
          </div>
          <button class="btn-close" @click="selectedNode = null">✕</button>
        </div>

        <div class="drawer-body" v-if="selectedNode">
          <!-- Node Meta Details -->
          <div class="meta-card">
            <div class="meta-row">
              <span class="meta-label">Node Type:</span>
              <span class="meta-value badge" :class="selectedNode.node_type">
                {{ selectedNode.node_type === 'monitored' ? 'Monitored Target' : 'Transit Router' }}
              </span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Operational Status:</span>
              <span class="status-pill" :class="getStatusClass(selectedNode.status)">
                {{ selectedNode.status }}
              </span>
            </div>
            <div class="meta-row" v-if="selectedNode.device_type">
              <span class="meta-label">Device Type:</span>
              <span class="meta-value">{{ selectedNode.device_type }}</span>
            </div>
          </div>

          <!-- Diagnostic Traceroute Section -->
          <div class="traces-section">
            <h4 class="section-title">
              <span>🩺 Diagnostic Traceroute</span>
              <button class="btn-xs" @click="fetchTraces(selectedNode.endpoint_id)" v-if="selectedNode.endpoint_id">
                Refresh Trace
              </button>
            </h4>

            <div v-if="tracesLoading" class="trace-loading">
              <div class="spinner-sm"></div>
              <span>Fetching diagnostic trace snapshot...</span>
            </div>

            <div v-else-if="latestHops.length === 0" class="empty-trace">
              <p>No diagnostic traceroutes available for this node.</p>
            </div>

            <div v-else class="trace-table-container">
              <table class="trace-table">
                <thead>
                  <tr>
                    <th>Hop</th>
                    <th>IP Address</th>
                    <th>RTT (ms)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="hop in latestHops" :key="hop.hop" :class="{ 'unresponsive': !hop.ip }">
                    <td class="hop-num">{{ hop.hop }}</td>
                    <td class="hop-ip">
                      {{ hop.ip || '* * * (Unresponsive)' }}
                    </td>
                    <td class="hop-rtt">
                      <span v-if="hop.rtt_ms !== null && hop.rtt_ms !== undefined" class="rtt-tag">
                        {{ hop.rtt_ms.toFixed(2) }} ms
                      </span>
                      <span v-else class="rtt-muted">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { getTopology, getEndpointTraces } from '../services/api.js'

const container = ref(null)
const loading = ref(true)
const error = ref(null)
const networkInitialized = ref(false)
const stabilized = ref(false)

const selectedNode = ref(null)
const tracesLoading = ref(false)
const latestHops = ref([])

let network = null
let nodesDataSet = null
let edgesDataSet = null
let refreshInterval = null

// Color scheme mapping based on operational state
function getNodeColors(status, nodeType) {
  if (nodeType === 'transit') {
    if (status === 'INFERRED_DOWN') {
      return {
        background: '#7F1D1D',
        border: '#DC2626',
        highlight: { background: '#991B1B', border: '#EF4444' }
      }
    }
    return {
      background: '#374151',
      border: '#6B7280',
      highlight: { background: '#4B5563', border: '#9CA3AF' }
    }
  }

  // Monitored nodes
  switch (status) {
    case 'UP':
      return {
        background: '#065F46',
        border: '#10B981',
        highlight: { background: '#047857', border: '#34D399' }
      }
    case 'UP-UNSTABLE':
    case 'DOWN-UNSTABLE':
      return {
        background: '#78350F',
        border: '#F59E0B',
        highlight: { background: '#92400E', border: '#FBBF24' }
      }
    case 'DOWN':
      return {
        background: '#7F1D1D',
        border: '#EF4444',
        highlight: { background: '#991B1B', border: '#F87171' }
      }
    default:
      return {
        background: '#1F2937',
        border: '#9CA3AF',
        highlight: { background: '#374151', border: '#D1D5DB' }
      }
  }
}

function getStatusClass(status) {
  switch (status) {
    case 'UP': return 'status-up'
    case 'UP-UNSTABLE':
    case 'DOWN-UNSTABLE': return 'status-unstable'
    case 'DOWN': return 'status-down'
    case 'INFERRED_DOWN': return 'status-inferred-down'
    default: return ''
  }
}

function formatVisData(nodesData, edgesData) {
  const visNodes = nodesData.map(node => {
    const colors = getNodeColors(node.status, node.node_type)
    const isTransit = node.node_type === 'transit'
    return {
      id: node.id,
      label: `${node.label}\n(${node.ip_address})`,
      shape: isTransit ? 'hexagon' : 'dot',
      size: isTransit ? 18 : 24,
      color: colors,
      font: { color: '#F3F4F6', size: 12, face: 'Inter, sans-serif' },
      // Attach raw node data for click inspector
      rawNode: node
    }
  })

  const visEdges = edgesData.map(edge => ({
    id: `${edge.source}->${edge.target}`,
    from: edge.source,
    to: edge.target,
    color: { color: '#4B5563', highlight: '#3B82F6' },
    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
    smooth: { type: 'cubicBezier' }
  }))

  return { visNodes, visEdges }
}

async function fetchTopology() {
  loading.value = true
  error.value = null
  try {
    const res = await getTopology()
    const rawData = res.data?.data || res.data || {}
    const rawNodes = rawData.nodes || []
    const rawEdges = rawData.edges || []

    const { visNodes, visEdges } = formatVisData(rawNodes, rawEdges)

    if (!networkInitialized.value) {
      nodesDataSet = new DataSet(visNodes)
      edgesDataSet = new DataSet(visEdges)

      await nextTick()

      const options = {
        nodes: { borderWidth: 2 },
        edges: { width: 2 },
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -40,
            centralGravity: 0.01,
            springLength: 120,
            springConstant: 0.08
          },
          stabilization: {
            enabled: true,
            iterations: 150
          }
        },
        interaction: {
          hover: true,
          zoomView: true,
          dragView: true
        }
      }

      network = new Network(container.value, { nodes: nodesDataSet, edges: edgesDataSet }, options)

      // Layout Stabilization Event: Disable physics so polling doesn't shake layout
      network.on('stabilizationIterationsDone', () => {
        network.setOptions({ physics: false })
        stabilized.value = true
      })

      // Click Inspector Listener
      network.on('click', (params) => {
        if (params.nodes && params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          const clickedNodeData = nodesDataSet.get(nodeId)
          if (clickedNodeData && clickedNodeData.rawNode) {
            onNodeClick(clickedNodeData.rawNode)
          }
        }
      })

      networkInitialized.value = true
    } else {
      // Dynamic update without position reset
      nodesDataSet.update(visNodes)
      edgesDataSet.update(visEdges)
    }

  } catch (err) {
    console.error('Failed to fetch topology:', err)
    error.value = 'Failed to load live network topology.'
  } finally {
    loading.value = false
  }
}

async function onNodeClick(node) {
  selectedNode.value = node
  latestHops.value = []

  if (node.endpoint_id) {
    await fetchTraces(node.endpoint_id)
  }
}

async function fetchTraces(endpointId) {
  if (!endpointId) return
  tracesLoading.value = true
  try {
    const res = await getEndpointTraces(endpointId)
    const traceList = res.data?.data || []
    if (traceList.length > 0 && traceList[0].trace_data) {
      const traceData = traceList[0].trace_data
      latestHops.value = traceData.hops || []
    } else {
      latestHops.value = []
    }
  } catch (err) {
    console.error('Failed to fetch endpoint traces:', err)
    latestHops.value = []
  } finally {
    tracesLoading.value = false
  }
}

onMounted(() => {
  fetchTopology()
  // 15-second auto-refresh
  refreshInterval = setInterval(() => {
    fetchTopology()
  }, 15000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (network) network.destroy()
})
</script>

<style scoped>
.topology-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  background: var(--bg-card, #111827);
  border: 1px solid var(--border-color, #1F2937);
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

.topology-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(17, 24, 39, 0.8);
  border-bottom: 1px solid var(--border-color, #1F2937);
  backdrop-filter: blur(8px);
  z-index: 10;
}

.topology-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: #F9FAFB;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge {
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 9999px;
  margin-left: 12px;
}

.badge-stabilized {
  background: rgba(16, 185, 129, 0.15);
  color: #34D399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge-stabilizing {
  background: rgba(245, 158, 11, 0.15);
  color: #FBBF24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.canvas-wrapper {
  flex: 1;
  position: relative;
  width: 100%;
  height: 100%;
}

.vis-network-canvas {
  width: 100%;
  height: 100%;
}

.loading-overlay, .error-overlay {
  position: absolute;
  inset: 0;
  background: rgba(17, 24, 39, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 20;
  color: #F9FAFB;
}

.map-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid #374151;
  padding: 12px 16px;
  border-radius: 8px;
  z-index: 10;
  font-size: 0.85rem;
  color: #D1D5DB;
}

.legend-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #F9FAFB;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  width: 12px;
  height: 12px;
  display: inline-block;
}

.node-icon.circle { border-radius: 50%; }
.node-icon.hexagon { clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%); }

.state-up { background: #10B981; }
.state-unstable { background: #F59E0B; }
.state-down { background: #EF4444; }
.state-transit { background: #6B7280; }
.state-inferred-down { background: #991B1B; }

/* Inspector Side Drawer */
.inspector-drawer {
  position: absolute;
  top: 0;
  right: 0;
  width: 400px;
  height: 100%;
  background: #111827;
  border-left: 1px solid #1F2937;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.5);
  z-index: 30;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
}

.inspector-drawer.open {
  transform: translateX(0);
}

.drawer-header {
  padding: 20px;
  border-bottom: 1px solid #1F2937;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: #1F2937;
}

.drawer-title {
  margin: 0;
  font-size: 1.1rem;
  color: #F9FAFB;
}

.drawer-sub {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: #9CA3AF;
}

.btn-close {
  color: #9CA3AF;
  font-size: 1.2rem;
  padding: 4px;
}

.drawer-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.meta-card {
  background: #1F2937;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.meta-label { color: #9CA3AF; }
.meta-value { color: #F3F4F6; font-weight: 500; }

.status-pill {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-up { background: rgba(16, 185, 129, 0.2); color: #34D399; }
.status-unstable { background: rgba(245, 158, 11, 0.2); color: #FBBF24; }
.status-down { background: rgba(239, 68, 68, 0.2); color: #F87171; }
.status-inferred-down { background: rgba(153, 27, 27, 0.4); color: #FCA5A5; border: 1px solid #EF4444; }

.section-title {
  font-size: 1rem;
  color: #F9FAFB;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trace-table-container {
  border: 1px solid #374151;
  border-radius: 8px;
  overflow: hidden;
}

.trace-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.trace-table th, .trace-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid #1F2937;
}

.trace-table th {
  background: #1F2937;
  color: #9CA3AF;
  font-weight: 600;
}

.trace-table tr.unresponsive td {
  color: #6B7280;
  font-style: italic;
}

.rtt-tag {
  color: #60A5FA;
  font-weight: 500;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #3B82F6;
  border-radius: 50%;
  animation: spin 1s infinite linear;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
