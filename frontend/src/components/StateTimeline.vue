<template>
  <div class="state-timeline">
    <Bar v-if="chartData" :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

const props = defineProps({
  events: {
    type: Array,
    required: true
  },
  gaps: {
    type: Array,
    required: true
  },
  periodStart: {
    type: String,
    required: true
  },
  periodEnd: {
    type: String,
    required: true
  }
})

const STATE_COLORS = {
  'UP': '#22c55e',
  'UP-UNSTABLE': '#f59e0b',
  'DOWN-UNSTABLE': '#f97316',
  'DOWN': '#ef4444',
  'UNKNOWN': '#9ca3af'
}

const formatDuration = (ms) => {
  if (ms < 0) return '0m'
  const totalMins = Math.floor(ms / 60000)
  const hours = Math.floor(totalMins / 60)
  const mins = totalMins % 60
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

const chartData = computed(() => {
  const pStart = new Date(props.periodStart).getTime()
  const pEnd = new Date(props.periodEnd).getTime()
  const totalDuration = pEnd - pStart

  if (totalDuration <= 0) return null

  const allSegments = []

  props.events.forEach(ev => {
    const start = Math.max(new Date(ev.start_time).getTime(), pStart)
    const end = ev.end_time ? Math.min(new Date(ev.end_time).getTime(), pEnd) : pEnd
    if (end > start) {
      allSegments.push({
        state: ev.detailed_state,
        startTime: ev.start_time,
        endTime: ev.end_time,
        startMs: start,
        endMs: end,
        isSplit: ev.is_split_event || false
      })
    }
  })

  props.gaps.forEach(gap => {
    const start = Math.max(new Date(gap.start_time).getTime(), pStart)
    const end = gap.end_time ? Math.min(new Date(gap.end_time).getTime(), pEnd) : pEnd
    if (end > start) {
      allSegments.push({
        state: 'UNKNOWN',
        startTime: gap.start_time,
        endTime: gap.end_time,
        startMs: start,
        endMs: end,
        isSplit: false
      })
    }
  })

  allSegments.sort((a, b) => a.startMs - b.startMs)

  const datasetsMap = {
    'UP': [],
    'UP-UNSTABLE': [],
    'DOWN-UNSTABLE': [],
    'DOWN': [],
    'UNKNOWN': []
  }

  allSegments.forEach(seg => {
    const startPx = (seg.startMs - pStart) / totalDuration
    const endPx = (seg.endMs - pStart) / totalDuration
    
    if (datasetsMap[seg.state]) {
      datasetsMap[seg.state].push({
        x: [startPx, endPx],
        y: 'Timeline',
        segmentData: seg
      })
    }
  })

  const datasets = Object.keys(datasetsMap).map(key => ({
    label: key,
    data: datasetsMap[key],
    backgroundColor: STATE_COLORS[key],
    grouped: false,
    borderWidth: key === 'UNKNOWN' ? 1 : 0,
    borderColor: key === 'UNKNOWN' ? '#6b7280' : 'transparent',
    borderSkipped: false
  }))

  return {
    labels: ['Timeline'],
    datasets: datasets.filter(ds => ds.data.length > 0)
  }
})

const chartOptions = {
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom'
    },
    tooltip: {
      callbacks: {
        title: () => '',
        label: (context) => {
          const seg = context.raw.segmentData
          const startStr = new Date(seg.startTime).toLocaleString()
          const endStr = seg.endTime ? new Date(seg.endTime).toLocaleString() : 'Ongoing'
          const duration = formatDuration(seg.endMs - seg.startMs)
          
          let lines = [
            `State: ${seg.state}`,
            `Start: ${startStr}`,
            `End: ${endStr}`,
            `Duration: ${duration}`
          ]
          
          if (seg.isSplit) {
            lines.push('(RTT inherited from previous day)')
          }
          
          return lines
        }
      }
    }
  },
  scales: {
    x: {
      type: 'linear',
      min: 0,
      max: 1,
      ticks: {
        callback: function(value) {
          return (value * 100) + '%'
        }
      },
      title: {
        display: false
      }
    },
    y: {
      display: false
    }
  }
}
</script>

<style scoped>
.state-timeline {
  height: 200px;
  width: 100%;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
}
</style>
