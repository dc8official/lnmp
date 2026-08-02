<template>
  <div class="topology-container">
    <!-- Map Toolbar -->
    <div class="topology-toolbar">
      <div class="toolbar-left">
        <h2 class="topology-title">
          <span class="icon">🕸</span> Live Network Topology Map
        </h2>
        <span class="status-badge" :class="stabilized ? 'badge-stabilized' : 'badge-stabilizing'">
          {{ stabilized ? '● Layout Fixed (Physics Off)' : '◌ Stabilizing Hierarchical Layout...' }}
        </span>
      </div>
      <div class="toolbar-right">
        <button class="btn-secondary" @click="resetView" title="Center and zoom map to fit all nodes">
          🔍 Reset View
        </button>
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
        <p>Loading multi-endpoint merged topology map...</p>
      </div>
      <div v-if="error" class="error-overlay">
        <p class="error-msg">⚠️ {{ error }}</p>
        <button class="btn-primary" @click="fetchTopology">Retry</button>
      </div>

      <!-- Legend Overlay -->
      <div class="map-legend">
        <div class="legend-title">Topology Legend</div>
        <div class="legend-items">
          <div class="legend-item"><span class="node-icon square state-root"></span> LNMP Engine (Root)</div>
          <div class="legend-item"><span class="node-icon circle state-up"></span> Monitored UP</div>
          <div class="legend-item"><span class="node-icon circle state-unstable"></span> Monitored UNSTABLE</div>
          <div class="legend-item"><span class="node-icon circle state-down"></span> Monitored DOWN</div>
          <div class="legend-item"><span class="node-icon hexagon state-transit"></span> Transit Router</div>
          <div class="legend-item"><span class="node-icon hexagon state-failure-point"></span> Failure Point (RCA)</div>
          <div class="legend-item"><span class="node-icon hexagon state-inferred-down"></span> Transit INFERRED DOWN</div>
          <div class="legend-item"><span class="l2-pill">L2</span> Layer 2 Segment</div>
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
          <!-- Node Meta Details Card -->
          <div class="meta-card">
            <div class="meta-row">
              <span class="meta-label">Node Category:</span>
              <span class="meta-value badge" :class="selectedNode.node_type || selectedNode.type">
                {{ formatNodeType(selectedNode.node_type || selectedNode.type) }}
              </span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Operational Status:</span>
              <span class="status-pill" :class="getStatusClass(selectedNode.status || selectedNode.state)">
                {{ selectedNode.status || selectedNode.state }}
              </span>
            </div>
            <div class="meta-row" v-if="selectedNode.is_l2_segment || selectedNode.device_type === 'L2_SEGMENT'">
              <span class="meta-label">Segment Type:</span>
              <span class="meta-value text-blue">Layer 2 Broadcast Segment</span>
            </div>
            <div class="meta-row" v-if="selectedNode.device_type">
              <span class="meta-label">Device Type:</span>
              <span class="meta-value">{{ selectedNode.device_type }}</span>
            </div>
          </div>

          <!-- Embedded RCA Diagnostics Component for Monitored Nodes with Endpoint ID -->
          <div v-if="selectedNode.endpoint_id" class="drawer-rca-section">
            <EndpointRcaDetail :endpointId="selectedNode.endpoint_id" />
          </div>

          <!-- Diagnostic Traceroute for Transit or unlinked Nodes -->
          <div v-else class="traces-section">
            <h4 class="section-title">
              <span>🩺 Transit Node Diagnostics</span>
            </h4>
            <div class="empty-trace">
              <p>Transit router node automatically inferred from traceroute discovery paths.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { getTopology } from '../services/api.js'
import EndpointRcaDetail from './EndpointRcaDetail.vue'

const container = ref(null)
const loading = ref(true)
const error = ref(null)
const networkInitialized = ref(false)
const stabilized = ref(false)

const selectedNode = ref(null)

let network = null
let nodesDataSet = null
let edgesDataSet = null
let refreshInterval = null

// Dark theme monitoring
const isDark = ref(true)
let themeObserver = null

watch(isDark, (newVal) => {
  if (nodesDataSet) {
    const updated = nodesDataSet.get().map(node => ({
      ...node,
      font: { ...node.font, color: newVal ? '#F3F4F6' : '#111111' }
    }))
    nodesDataSet.update(updated)
  }
})

function formatNodeType(type) {
  if (type === 'root') return 'LNMP Engine (Root)'
  if (type === 'monitored') return 'Monitored Target'
  return 'Transit Router'
}

// Visual Node Styling & Categorization
function getNodeColors(status, nodeType) {
  if (nodeType === 'root') {
    return {
      background: '#1D4ED8',
      border: '#3B82F6',
      highlight: { background: '#2563EB', border: '#60A5FA' }
    }
  }

  if (nodeType === 'transit') {
    if (status === 'FAILURE_POINT') {
      return {
        background: '#991B1B',
        border: '#F97316',
        highlight: { background: '#7F1D1D', border: '#FB923C' }
      }
    }
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
    case 'FAILURE_POINT': return 'status-failure-point'
    case 'INFERRED_DOWN': return 'status-inferred-down'
    default: return ''
  }
}

function formatVisData(nodesData, edgesData) {
  const visNodes = nodesData.map(node => {
    const nodeType = node.node_type || node.type
    const nodeStatus = node.status || node.state
    const colors = getNodeColors(nodeStatus, nodeType)
    const isL2 = node.is_l2_segment || node.device_type === 'L2_SEGMENT'

    let shape = 'dot'
    let size = 24

    if (nodeType === 'root') {
      shape = 'square'
      size = 28
    } else if (nodeType === 'transit') {
      shape = 'hexagon'
      size = 18
    }

    let labelText = `${node.label}\n(${node.ip_address || ''})`
    if (isL2) {
      labelText += '\n[L2 Segment]'
    }
    if (nodeStatus === 'FAILURE_POINT') {
      labelText += '\n⚠️ FAILURE POINT'
    }

    return {
      id: node.id,
      label: labelText.trim(),
      shape: shape,
      size: size,
      color: colors,
      font: { color: isDark.value ? '#F3F4F6' : '#111111', size: 12, face: 'Inter, sans-serif' },
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
        layout: {
          hierarchical: {
            enabled: true,
            direction: 'UD',
            sortMethod: 'directed',
            nodeSpacing: 150,
            levelSeparation: 120
          }
        },
        physics: {
          enabled: true,
          hierarchicalRepulsion: {
            centralGravity: 0.0,
            springLength: 100,
            springConstant: 0.01,
            nodeDistance: 120,
            damping: 0.09
          },
          stabilization: {
            enabled: true,
            iterations: 200
          }
        },
        interaction: {
          hover: true,
          zoomView: true,
          dragView: true
        }
      }

      network = new Network(container.value, { nodes: nodesDataSet, edges: edgesDataSet }, options)

      // Listen to stabilizationIterationsDone and immediately execute physics: false
      // to freeze node positions and prevent canvas shaking during live polling updates.
      network.on('stabilizationIterationsDone', () => {
        network.setOptions({ physics: { enabled: false } })
        stabilized.value = true
      })

      // Click Inspector Listener
      network.on('click', (params) => {
        if (params.nodes && params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          const clickedNodeData = nodesDataSet.get(nodeId)
          if (clickedNodeData && clickedNodeData.rawNode) {
            selectedNode.value = clickedNodeData.rawNode
          }
        }
      })

      networkInitialized.value = true
    } else {
      // Dynamic update without moving node positions
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

function resetView() {
  if (network) {
    network.fit({ animation: true })
  }
}

onMounted(() => {
  isDark.value = document.documentElement.classList.contains('dark')
  themeObserver = new MutationObserver(() => {
    isDark.value = document.documentElement.classList.contains('dark')
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class']
  })

  fetchTopology()
  // 15-second auto-refresh
  refreshInterval = setInterval(() => {
    fetchTopology()
  }, 15000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (network) network.destroy()
  if (themeObserver) themeObserver.disconnect()
})
</script>

<style scoped>
.topology-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

.topology-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--bg-surface-selected);
  border-bottom: 1px solid var(--border-color);
  backdrop-filter: blur(8px);
  z-index: 10;
}

.topology-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
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

.toolbar-right {
  display: flex;
  gap: 10px;
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
  background: var(--bg-surface);
  opacity: 0.95;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 20;
  color: var(--text-primary);
}

.map-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 12px 16px;
  border-radius: 8px;
  z-index: 10;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.legend-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
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

.node-icon.square { border-radius: 2px; }
.node-icon.circle { border-radius: 50%; }
.node-icon.hexagon { clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%); }

.state-root { background: #3B82F6; }
.state-up { background: #10B981; }
.state-unstable { background: #F59E0B; }
.state-down { background: #EF4444; }
.state-transit { background: #6B7280; }
.state-failure-point { background: #F97316; border: 1px solid #EF4444; }
.state-inferred-down { background: #7F1D1D; }

.l2-pill {
  background: rgba(59, 130, 246, 0.2);
  color: #60A5FA;
  font-size: var(--text-xs);
  font-weight: 700;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
}

/* Inspector Side Drawer */
.inspector-drawer {
  position: absolute;
  top: 0;
  right: 0;
  width: 520px;
  max-width: 90vw;
  height: 100%;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-color);
  box-shadow: -6px 0 24px rgba(0, 0, 0, 0.15);
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
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: var(--bg-surface-selected);
}

.drawer-title {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.drawer-sub {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}



.drawer-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.meta-card {
  background: var(--bg-surface-selected);
  border: 1px solid var(--border-color);
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

.meta-label { color: var(--text-muted); }
.meta-value { color: var(--text-primary); font-weight: 500; }
.meta-value.text-blue { color: #60A5FA; }

.status-pill {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-up { background: rgba(16, 185, 129, 0.2); color: #34D399; }
.status-unstable { background: rgba(245, 158, 11, 0.2); color: #FBBF24; }
.status-down { background: rgba(239, 68, 68, 0.2); color: #F87171; }
.status-failure-point { background: #EF4444; color: #FFFFFF; }
.status-inferred-down { background: rgba(153, 27, 27, 0.4); color: #FCA5A5; border: 1px solid #EF4444; }

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: #3B82F6;
  border-radius: 50%;
  animation: spin 1s infinite linear;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Light mode contrast overrides */
</style>

<style>
html:not(.dark) .badge-stabilized {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
  border-color: rgba(22, 163, 74, 0.2);
}
html:not(.dark) .badge-stabilizing {
  background: rgba(180, 83, 9, 0.1);
  color: #b45309;
  border-color: rgba(180, 83, 9, 0.2);
}
html:not(.dark) .status-up {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}
html:not(.dark) .status-unstable {
  background: rgba(180, 83, 9, 0.1);
  color: #b45309;
}
html:not(.dark) .status-down {
  background: rgba(220, 38, 38, 0.1);
  color: #b91c1c;
}
html:not(.dark) .status-inferred-down {
  background: rgba(220, 38, 38, 0.15);
  color: #b91c1c;
  border-color: rgba(220, 38, 38, 0.3);
}
html:not(.dark) .l2-pill {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
}
html:not(.dark) .meta-value.text-blue {
  color: #1d4ed8;
}
</style>
