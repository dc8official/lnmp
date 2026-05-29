<template>
  <div class="uptime-summary-panel">
    <div class="summary-grid">
      <div class="metric-tile" :class="uptimeColorClass">
        <span class="metric-label">Uptime</span>
        <span class="metric-value">{{ report.uptime_percentage }}%</span>
      </div>
      <div class="metric-tile downtime">
        <span class="metric-label">Downtime</span>
        <span class="metric-value">{{ formatSeconds(report.downtime_seconds) }}</span>
      </div>
      <div class="metric-tile" :class="unknownColorClass">
        <span class="metric-label">Unknown (gaps)</span>
        <span class="metric-value">{{ formatSeconds(report.unknown_seconds) }}</span>
      </div>
      <div class="metric-tile incidents">
        <span class="metric-label">Incidents</span>
        <span class="metric-value">{{ report.incident_count }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  report: {
    type: Object,
    required: true
  }
})

const uptimeColorClass = computed(() => {
  const pct = props.report.uptime_percentage
  if (pct >= 99) return 'status-green'
  if (pct >= 95) return 'status-amber'
  return 'status-red'
})

const unknownColorClass = computed(() => {
  return props.report.unknown_seconds > 0 ? 'status-grey' : 'status-normal'
})

const formatSeconds = (totalSeconds) => {
  if (!totalSeconds || totalSeconds === 0) return '0h 00m'
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  return `${h}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`
}
</script>

<style scoped>
.uptime-summary-panel {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
@media (min-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
.metric-tile {
  display: flex;
  flex-direction: column;
  padding: 1rem;
  border-radius: 6px;
  background-color: #f8fafc;
  border-left: 4px solid #cbd5e1;
}
.metric-label {
  font-size: 0.9rem;
  color: #64748b;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.metric-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #0f172a;
}
.status-green { border-left-color: #22c55e; }
.status-amber { border-left-color: #f59e0b; }
.status-red { border-left-color: #ef4444; }
.status-grey { border-left-color: #9ca3af; }
.status-normal { border-left-color: #cbd5e1; }
</style>
