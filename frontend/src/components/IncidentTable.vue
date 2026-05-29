<template>
  <div class="incident-table-container">
    <DataTable 
      :value="incidents" 
      :loading="loading"
      :paginator="true" 
      :rows="20"
      sortField="duration_seconds" 
      :sortOrder="-1"
      emptyMessage="No incidents in this period."
      class="p-datatable-sm"
    >
      <Column field="incident_start" header="Start" :sortable="true">
        <template #body="{ data }">
          {{ formatDateTime(data.incident_start) }}
        </template>
      </Column>
      
      <Column field="incident_end" header="End" :sortable="true">
        <template #body="{ data }">
          {{ data.incident_end ? formatDateTime(data.incident_end) : 'Ongoing' }}
        </template>
      </Column>
      
      <Column field="duration_seconds" header="Duration" :sortable="true">
        <template #body="{ data }">
          {{ data.duration_seconds != null ? formatDuration(data.duration_seconds) : 'Ongoing' }}
        </template>
      </Column>
      
      <Column field="peak_detailed_state" header="Peak State">
        <template #body="{ data }">
          <span class="state-badge" :style="{ backgroundColor: getStateColor(data.peak_detailed_state) }">
            {{ data.peak_detailed_state }}
          </span>
        </template>
      </Column>
      
      <Column field="contributing_event_count" header="Events" :sortable="true"></Column>
    </DataTable>
  </div>
</template>

<script setup>
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const props = defineProps({
  incidents: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const STATE_COLORS = {
  'UP': '#22c55e',
  'UP-UNSTABLE': '#f59e0b',
  'DOWN-UNSTABLE': '#f97316',
  'DOWN': '#ef4444',
  'UNKNOWN': '#9ca3af'
}

const getStateColor = (state) => {
  return STATE_COLORS[state] || STATE_COLORS['UNKNOWN']
}

const formatDateTime = (isoString) => {
  if (!isoString) return ''
  const d = new Date(isoString)
  const yyyy = d.getUTCFullYear()
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(d.getUTCDate()).padStart(2, '0')
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mins = String(d.getUTCMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mins} UTC`
}

const formatDuration = (totalSeconds) => {
  if (totalSeconds < 0) return '0m'
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
</script>

<style scoped>
.incident-table-container {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
}
.state-badge {
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: bold;
  display: inline-block;
}
</style>
