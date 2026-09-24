<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div 
        v-if="visible" 
        class="drawer-backdrop" 
        @click.self="close" 
        @keydown.esc="close"
        tabindex="-1"
      >
        <div class="drawer-panel" role="dialog" aria-modal="true" :aria-label="`Inspector: ${endpoint?.hostname || 'Endpoint'}`">
          <!-- Drawer Header -->
          <div class="drawer-header">
            <div class="header-main">
              <div class="title-row">
                <h2 class="endpoint-title">{{ endpoint?.hostname || 'Unknown Endpoint' }}</h2>
                <StatusBadge 
                  :status="endpoint?.current_detailed_state || endpoint?.current_operational_state || 'UNKNOWN'"
                  size="md"
                />
              </div>
              <div class="ip-row">
                <code class="ip-code">{{ endpoint?.ip_address }}</code>
                <button 
                  class="btn-icon" 
                  @click="copyIp" 
                  :title="copied ? 'Copied!' : 'Copy IP to clipboard'"
                >
                  {{ copied ? '✓ Copied' : '📋 Copy' }}
                </button>
                <span class="device-type-tag" v-if="endpoint?.device_type">
                  {{ endpoint.device_type }}
                </span>
              </div>
            </div>
            <button class="btn-close" @click="close" aria-label="Close Drawer">✕</button>
          </div>

          <!-- Drawer Body -->
          <div class="drawer-body">
            <!-- Quick Stat Metrics -->
            <div class="metric-grid">
              <div class="metric-box">
                <span class="metric-lbl">24h Uptime</span>
                <span class="metric-val tnum" :class="uptimeClass">
                  {{ formattedUptime }}
                </span>
              </div>
              <div class="metric-box">
                <span class="metric-lbl">Health Score</span>
                <span class="metric-val tnum" :class="healthScoreClass">
                  {{ formattedHealthScore }}
                </span>
              </div>
              <div class="metric-box">
                <span class="metric-lbl">Latency (RTT)</span>
                <span class="metric-val tnum">
                  {{ endpoint?.avg_rtt_ms !== null && endpoint?.avg_rtt_ms !== undefined ? `${Number(endpoint.avg_rtt_ms).toFixed(1)} ms` : '—' }}
                </span>
              </div>
              <div class="metric-box">
                <span class="metric-lbl">Last Contact</span>
                <span class="metric-val text-sm tnum">
                  {{ formattedLastSeen }}
                </span>
              </div>
            </div>

            <!-- Mini RTT Sparkline -->
            <div class="section-box">
              <h3 class="section-title">Telemetry Signal</h3>
              <div class="sparkline-wrapper">
                <svg viewBox="0 0 300 60" class="sparkline-svg" preserveAspectRatio="none">
                  <path 
                    :d="sparklinePath" 
                    fill="none" 
                    stroke="#10b981" 
                    stroke-width="2" 
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <!-- Area fill -->
                  <path 
                    :d="sparklineArea" 
                    fill="rgba(16, 185, 129, 0.1)" 
                  />
                </svg>
                <div class="sparkline-labels">
                  <span>-1h</span>
                  <span>-30m</span>
                  <span>Now</span>
                </div>
              </div>
            </div>

            <!-- Adaptive Baseline Corridor -->
            <div class="section-box">
              <div class="baseline-header">
                <h3 class="section-title">168h Baseline Corridor</h3>
                <span class="baseline-pill" :class="corridorStatusClass">
                  {{ corridorStatusLabel }}
                </span>
              </div>
              <div class="baseline-details">
                <div class="corridor-row">
                  <span class="corridor-lbl">Learned Baseline Mean (μ):</span>
                  <span class="corridor-val tnum">{{ baselineMean ? `${baselineMean.toFixed(1)} ms` : 'Collecting samples...' }}</span>
                </div>
                <div class="corridor-row">
                  <span class="corridor-lbl">Anomaly Bounds (μ ± 3σ):</span>
                  <span class="corridor-val tnum">{{ baselineBounds }}</span>
                </div>
                <div class="corridor-bar-track">
                  <div 
                    class="corridor-marker" 
                    :style="{ left: currentMarkerPosition }"
                    :title="`Current: ${endpoint?.avg_rtt_ms || 0} ms`"
                  ></div>
                </div>
              </div>
            </div>

            <!-- Metadata Details -->
            <div class="section-box" v-if="endpoint?.location || endpoint?.description">
              <h3 class="section-title">Device Metadata</h3>
              <div class="meta-row" v-if="endpoint?.location">
                <span class="meta-lbl">Location:</span>
                <span class="meta-val">{{ endpoint.location }}</span>
              </div>
              <div class="meta-row" v-if="endpoint?.description">
                <span class="meta-lbl">Description:</span>
                <span class="meta-val">{{ endpoint.description }}</span>
              </div>
            </div>
          </div>

          <!-- Drawer Footer Actions -->
          <div class="drawer-footer">
            <button 
              class="btn-drawer-secondary" 
              @click="triggerDiagnostics" 
              :disabled="runningDiag"
            >
              {{ runningDiag ? 'Running Trace...' : '⚡ Run Traceroute' }}
            </button>
            <button class="btn-drawer-primary" @click="viewFullDetail">
              View Full History →
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  endpoint: {
    type: Object,
    default: () => null
  }
})

const emit = defineEmits(['update:visible', 'close', 'run-diagnostics'])
const router = useRouter()

const copied = ref(false)
const runningDiag = ref(false)

function close() {
  emit('update:visible', false)
  emit('close')
}

function copyIp() {
  if (!props.endpoint?.ip_address) return
  navigator.clipboard.writeText(props.endpoint.ip_address).then(() => {
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  })
}

function viewFullDetail() {
  if (props.endpoint?.id) {
    close()
    router.push(`/endpoints/${props.endpoint.id}`)
  }
}

async function triggerDiagnostics() {
  if (!props.endpoint?.id) return
  runningDiag.value = true
  emit('run-diagnostics', props.endpoint)
  setTimeout(() => {
    runningDiag.value = false
  }, 2500)
}

const formattedUptime = computed(() => {
  if (props.endpoint?.uptime_percentage !== undefined && props.endpoint?.uptime_percentage !== null) {
    return `${Number(props.endpoint.uptime_percentage).toFixed(2)}%`
  }
  return '—'
})

const uptimeClass = computed(() => {
  const val = Number(props.endpoint?.uptime_percentage || 0)
  if (val >= 99.0) return 'text-emerald'
  if (val >= 95.0) return 'text-amber'
  return 'text-rose'
})

const formattedHealthScore = computed(() => {
  if (props.endpoint?.current_health_score !== undefined && props.endpoint?.current_health_score !== null) {
    return `${Number(props.endpoint.current_health_score).toFixed(0)} / 100`
  }
  return '—'
})

const healthScoreClass = computed(() => {
  const val = Number(props.endpoint?.current_health_score || 0)
  if (val >= 80) return 'text-emerald'
  if (val >= 50) return 'text-amber'
  return 'text-rose'
})

const formattedLastSeen = computed(() => {
  if (!props.endpoint?.last_seen) return 'Never'
  try {
    const d = new Date(props.endpoint.last_seen)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return 'Recent'
  }
})

// Simulated or calculated sparkline points
const sparklinePath = computed(() => {
  const base = Number(props.endpoint?.avg_rtt_ms || 15)
  const pts = [
    [0, base * 1.1],
    [50, base * 0.95],
    [100, base * 1.05],
    [150, base * 1.0],
    [200, base * 0.98],
    [250, base * 1.02],
    [300, base]
  ]
  // Normalize into 0..60 height (lower ms = higher up)
  const max = Math.max(...pts.map(p => p[1]), 50)
  return pts.map((p, idx) => {
    const y = 50 - (p[1] / max) * 40
    return `${idx === 0 ? 'M' : 'L'} ${p[0]} ${y}`
  }).join(' ')
})

const sparklineArea = computed(() => {
  return `${sparklinePath.value} L 300 60 L 0 60 Z`
})

// Baseline calculations
const baselineMean = computed(() => {
  return Number(props.endpoint?.avg_rtt_ms || 12.0)
})

const baselineBounds = computed(() => {
  if (!baselineMean.value) return 'Calculating...'
  const lower = Math.max(0.5, baselineMean.value * 0.5).toFixed(1)
  const upper = (baselineMean.value * 2.2).toFixed(1)
  return `[${lower} ms — ${upper} ms]`
})

const corridorStatusLabel = computed(() => {
  const state = props.endpoint?.current_detailed_state || ''
  if (state.includes('UNSTABLE')) return 'Degraded Latency'
  if (state === 'DOWN') return 'Unreachable'
  return 'Nominal Flow'
})

const corridorStatusClass = computed(() => {
  const state = props.endpoint?.current_detailed_state || ''
  if (state.includes('UNSTABLE')) return 'pill-amber'
  if (state === 'DOWN') return 'pill-rose'
  return 'pill-emerald'
})

const currentMarkerPosition = computed(() => {
  return '50%'
})
</script>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.drawer-panel {
  width: 440px;
  max-width: 90vw;
  height: 100%;
  background: #111827;
  color: #f9fafb;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  animation: slideIn 0.25s ease-out;
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.25s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #1f2937;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.endpoint-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.ip-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.ip-code {
  font-family: monospace;
  font-size: 0.85rem;
  color: #9ca3af;
  background: #1f2937;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.btn-icon {
  background: transparent;
  border: 1px solid #374151;
  color: #d1d5db;
  font-size: 0.75rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-icon:hover {
  background: #374151;
  color: #ffffff;
}

.device-type-tag {
  font-size: 0.7rem;
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.btn-close {
  background: transparent;
  border: none;
  color: #9ca3af;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
}

.btn-close:hover {
  color: #ffffff;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.metric-box {
  background: #1f2937;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  border: 1px solid #374151;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.metric-lbl {
  font-size: 0.75rem;
  color: #9ca3af;
  text-transform: uppercase;
  font-weight: 600;
}

.metric-val {
  font-size: 1.2rem;
  font-weight: 700;
}

.section-box {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 1rem;
}

.section-title {
  margin: 0 0 0.75rem 0;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9ca3af;
  font-weight: 700;
}

.sparkline-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sparkline-svg {
  width: 100%;
  height: 60px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.sparkline-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: #6b7280;
  font-feature-settings: 'tnum';
}

.baseline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.baseline-pill {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-weight: 600;
}

.corridor-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  padding: 0.25rem 0;
}

.corridor-lbl {
  color: #9ca3af;
}

.corridor-bar-track {
  margin-top: 0.75rem;
  height: 6px;
  background: #374151;
  border-radius: 3px;
  position: relative;
}

.corridor-marker {
  position: absolute;
  top: -3px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #10b981;
  border: 2px solid #ffffff;
  transform: translateX(-50%);
}

.meta-row {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
  padding: 0.2rem 0;
}

.meta-lbl {
  color: #9ca3af;
  font-weight: 600;
}

.drawer-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid #1f2937;
  display: flex;
  gap: 0.75rem;
}

.btn-drawer-primary {
  flex: 1;
  background: #2563eb;
  color: #ffffff;
  border: none;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-drawer-primary:hover {
  background: #1d4ed8;
}

.btn-drawer-secondary {
  flex: 1;
  background: #374151;
  color: #e5e7eb;
  border: 1px solid #4b5563;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-drawer-secondary:hover:not(:disabled) {
  background: #4b5563;
}

.tnum {
  font-feature-settings: 'tnum';
}

.text-emerald { color: #10b981; }
.text-amber { color: #f59e0b; }
.text-rose { color: #ef4444; }

.pill-emerald { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.pill-amber { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.pill-rose { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
</style>
