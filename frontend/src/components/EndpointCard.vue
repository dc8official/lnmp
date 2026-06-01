<template>
  <Card class="endpoint-card" @click="handleClick">
    <template #title>
      <div class="card-header-row">
        <div class="hostname" :title="endpoint.hostname">
          {{ endpoint.hostname }}
        </div>
        <div v-if="isAdmin" class="admin-actions" @click.stop>
          <Button 
            icon="pi pi-pencil" 
            severity="secondary" 
            text 
            size="small" 
            @click="handleEdit" 
            v-tooltip="'Edit'"
            class="action-btn"
          />
          <Button 
            icon="pi pi-trash" 
            severity="danger" 
            text 
            size="small" 
            @click="handleDelete" 
            v-tooltip="'Delete'"
            class="action-btn delete"
          />
        </div>
      </div>
    </template>
    <template #subtitle>
      <div class="ip-address font-mono">{{ endpoint.ip_address }}</div>
    </template>
    <template #content>
      <div class="status-row">
        <span class="state-text" :class="stateClass" :style="{ color: stateTextColor }">
          <span v-if="endpoint.current_detailed_state === 'UP'" class="state-dot"></span>
          {{ endpoint.current_detailed_state }}
        </span>
      </div>
      <div class="metrics-row font-mono">
        <div class="uptime-metric">
          <span class="metric-label">Availability:</span> 
          <span class="metric-value">{{ formattedUptime }} SLA</span>
        </div>
        <div class="last-seen">
          Last seen: {{ timeAgo }}
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'

const props = defineProps({
  endpoint: {
    type: Object,
    required: true
  },
  isAdmin: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select', 'edit', 'delete'])

const handleClick = () => {
  emit('select', props.endpoint.id)
}

const handleEdit = () => {
  emit('edit', props.endpoint)
}

const handleDelete = () => {
  emit('delete', props.endpoint.id)
}

const stateClass = computed(() => {
  const state = props.endpoint.current_detailed_state
  if (state === 'UP') return 'up'
  if (state === 'UP-UNSTABLE' || state === 'DOWN-UNSTABLE') return 'unstable'
  if (state === 'DOWN') return 'down'
  return 'unknown'
})

const stateTextColor = computed(() => {
  const state = props.endpoint.current_detailed_state
  if (state === 'UP') return '#FFFFFF' // Monochrome flat white for healthy
  if (state === 'UP-UNSTABLE' || state === 'DOWN-UNSTABLE') return '#F59E0B' // Solid un-softened amber
  if (state === 'DOWN') return '#FF0000' // Piercing high-saturation solid red
  return '#A3A3A3'
})

const formattedUptime = computed(() => {
  if (props.endpoint.uptime_percentage_24h == null) return '0.00%'
  return `${props.endpoint.uptime_percentage_24h}%`
})

const timeAgo = computed(() => {
  if (!props.endpoint.last_seen) return 'Never'
  
  const now = new Date()
  const past = new Date(props.endpoint.last_seen)
  const diffMs = now - past
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
})
</script>

<style scoped>
.endpoint-card {
  cursor: pointer;
  height: 100%;
  background-color: var(--card-bg) !important;
  border: 1px solid var(--card-border) !important;
  border-radius: 4px !important;
  box-shadow: none !important;
  transition: border-color 0.15s ease;
}
.endpoint-card:hover {
  border-color: var(--text-secondary) !important;
}
:deep(.p-card-body) {
  padding: 1.25rem !important;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.hostname {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 1.05rem;
  flex: 1;
  color: #FFFFFF;
}
.admin-actions {
  display: flex;
  gap: 0.15rem;
}
.action-btn {
  color: #A3A3A3 !important;
  padding: 0.25rem !important;
  border-radius: 4px !important;
}
.action-btn:hover {
  color: #FFFFFF !important;
  background-color: rgba(255,255,255,0.08) !important;
}
.action-btn.delete:hover {
  color: #FF0000 !important;
  background-color: rgba(255, 0, 0, 0.08) !important;
}
.ip-address {
  color: #A3A3A3;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
  font-weight: 500;
}
.status-row {
  margin-bottom: 1.25rem;
}
.state-text {
  font-size: 0.8rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.state-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #588157; /* compact un-glowing gray-green dot */
  display: inline-block;
}
.metrics-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.8rem;
  border-top: 1px solid #262626;
  padding-top: 0.75rem;
}
.font-mono {
  font-family: monospace;
}
.metric-label {
  color: #A3A3A3;
}
.metric-value {
  color: #FFFFFF;
  font-weight: 700;
}
.last-seen {
  color: #A3A3A3;
}

/* Light Mode Overrides */
:global(body.light-mode) .endpoint-card {
  background-color: #fafafa !important;
  border: 1px solid #cbd5e1 !important;
}
:global(body.light-mode) .endpoint-card:hover {
  border-color: #94a3b8 !important;
}
:global(body.light-mode) .hostname {
  color: #0f172a;
}
:global(body.light-mode) .ip-address {
  color: #475569;
}
:global(body.light-mode) .action-btn {
  color: #475569 !important;
}
:global(body.light-mode) .action-btn:hover {
  color: #0f172a !important;
  background-color: rgba(0,0,0,0.05) !important;
}
:global(body.light-mode) .action-btn.delete:hover {
  color: #FF0000 !important;
  background-color: rgba(255,0,0,0.05) !important;
}
:global(body.light-mode) .state-text.up {
  color: #334155 !important;
}
:global(body.light-mode) .metrics-row {
  border-top: 1px solid #e2e8f0;
}
:global(body.light-mode) .metric-label {
  color: #475569;
}
:global(body.light-mode) .metric-value {
  color: #0f172a;
}
:global(body.light-mode) .last-seen {
  color: #64748b;
}
</style>
