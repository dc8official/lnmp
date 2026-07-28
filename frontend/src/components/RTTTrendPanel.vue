<template>
  <div class="rtt-trend-panel">
    <div v-if="!hasData" class="empty-state">
      No RTT data available for this period.
    </div>
    <div v-else class="chart-wrapper">
      <LineChart :key="isDark" :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { Line as LineChart } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  events: {
    type: Array,
    required: true
  }
})

const isDark = ref(true)
let observer = null

onMounted(() => {
  isDark.value = document.documentElement.classList.contains('dark')
  observer = new MutationObserver(() => {
    isDark.value = document.documentElement.classList.contains('dark')
  })
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class']
  })
})

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
  }
})

const validEvents = computed(() => {
  return props.events.filter(ev => ev.avg_rtt_ms != null)
})

const hasData = computed(() => {
  return validEvents.value.length > 0
})

const optimalPointRadius = computed(() => {
  return validEvents.value.length > 100 ? 0 : 4
})

const formatTime = (isoString) => {
  const d = new Date(isoString)
  const hours = d.getHours().toString().padStart(2, '0')
  const minutes = d.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

const chartData = computed(() => {
  if (!hasData.value) return null

  const processed = validEvents.value.map(ev => {
    const start = new Date(ev.start_time).getTime()
    const end = ev.end_time ? new Date(ev.end_time).getTime() : new Date().getTime()
    const midpoint = start + ((end - start) / 2)
    return {
      ...ev,
      midpoint
    }
  }).sort((a, b) => a.midpoint - b.midpoint)

  const labels = processed.map(ev => formatTime(ev.start_time))
  
  const measuredData = processed.map(ev => !ev.is_split_event ? ev.avg_rtt_ms : null)
  const inheritedData = processed.map(ev => ev.is_split_event ? ev.avg_rtt_ms : null)

  const measuredColor = isDark.value ? '#FFFFFF' : '#0f172a'
  const inheritedColor = isDark.value ? '#666666' : '#94a3b8'
  const inheritedPointBg = isDark.value ? '#000000' : '#ffffff'

  return {
    labels,
    datasets: [
      {
        label: 'Measured RTT',
        data: measuredData,
        borderColor: measuredColor,
        backgroundColor: measuredColor,
        borderWidth: 2,
        pointStyle: 'circle',
        pointRadius: optimalPointRadius.value,
        spanGaps: true
      },
      {
        label: 'Inherited RTT',
        data: inheritedData,
        borderColor: inheritedColor,
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [5, 5],
        pointStyle: 'circle',
        pointRadius: optimalPointRadius.value,
        pointBackgroundColor: inheritedPointBg,
        spanGaps: true
      }
    ]
  }
})

const chartOptions = computed(() => {
  const gridColor = isDark.value ? '#3a3a3a' : '#9bb5d1'
  const textColor = isDark.value ? '#D0D0D0' : '#334155'

  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: textColor,
          font: {
            family: 'monospace',
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            let label = `${context.dataset.label}: ${context.raw} ms`
            if (context.dataset.label === 'Inherited RTT') {
              return [label, 'Inherited value (RTT not measured at this boundary)']
            }
            return label
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        title: {
          display: false
        },
        grid: {
          color: gridColor,
          drawBorder: false
        },
        ticks: {
          color: textColor,
          maxTicksLimit: 10,
          font: {
            family: 'monospace',
            size: 12
          }
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: 'RTT (ms)',
          color: textColor,
          font: {
            family: 'monospace',
            size: 12
          }
        },
        grid: {
          color: gridColor,
          drawBorder: false
        },
        ticks: {
          color: textColor,
          font: {
            family: 'monospace',
            size: 12
          }
        },
        beginAtZero: true
      }
    }
  }
})
</script>

<style scoped>
.rtt-trend-panel {
  background: #000000;
  padding: 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  box-shadow: none;
  margin-bottom: 1.5rem;
  height: 350px;
  display: flex;
  flex-direction: column;
  transition: background-color 0.2s, border-color 0.2s;
}
.chart-wrapper {
  flex: 1;
  min-height: 0;
  width: 100%;
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-family: monospace;
  font-size: 1rem;
  transition: color 0.2s;
}

:global(html:not(.dark)) .rtt-trend-panel {
  background: #ffffff;
}
</style>
