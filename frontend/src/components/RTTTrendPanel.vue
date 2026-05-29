<template>
  <div class="rtt-trend-panel">
    <div v-if="!hasData" class="empty-state">
      No RTT data available for this period.
    </div>
    <div v-else class="chart-wrapper">
      <LineChart :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
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

const validEvents = computed(() => {
  return props.events.filter(ev => ev.avg_rtt_ms != null)
})

const hasData = computed(() => {
  return validEvents.value.length > 0
})

const formatTime = (isoString) => {
  const d = new Date(isoString)
  return `${d.getUTCHours().toString().padStart(2, '0')}:${d.getUTCMinutes().toString().padStart(2, '0')} UTC`
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

  return {
    labels,
    datasets: [
      {
        label: 'Measured RTT',
        data: measuredData,
        borderColor: '#3b82f6',
        backgroundColor: '#3b82f6',
        borderWidth: 2,
        pointStyle: 'circle',
        pointRadius: 4,
        spanGaps: true
      },
      {
        label: 'Inherited RTT',
        data: inheritedData,
        borderColor: 'rgba(59, 130, 246, 0.4)',
        backgroundColor: 'transparent',
        borderWidth: 2,
        borderDash: [5, 5],
        pointStyle: 'circle',
        pointRadius: 4,
        pointBackgroundColor: 'white',
        spanGaps: true
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top'
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
      ticks: {
        maxTicksLimit: 10
      }
    },
    y: {
      display: true,
      title: {
        display: true,
        text: 'RTT (ms)'
      },
      beginAtZero: true
    }
  }
}
</script>

<style scoped>
.rtt-trend-panel {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
  height: 350px;
  display: flex;
  flex-direction: column;
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
  color: #64748b;
  font-size: 1.1rem;
}
</style>
