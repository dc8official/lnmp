<template>
  <Card class="endpoint-card" @click="handleClick">
    <template #title>
      <div class="hostname" :title="endpoint.hostname">
        {{ endpoint.hostname }}
      </div>
    </template>
    <template #subtitle>
      <div class="ip-address">{{ endpoint.ip_address }}</div>
    </template>
    <template #content>
      <div class="status-row">
        <span class="state-badge" :style="{ backgroundColor: stateColor }">
          {{ endpoint.current_detailed_state }}
        </span>
      </div>
      <div class="metrics-row">
        <div class="uptime-metric">
          <strong>{{ formattedUptime }}</strong> uptime
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

const props = defineProps({
  endpoint: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['select'])

const handleClick = () => {
  emit('select', props.endpoint.id)
}

const stateColor = computed(() => {
  const state = props.endpoint.current_detailed_state
  if (state === 'UP') return '#22c55e'
  if (state === 'UP-UNSTABLE') return '#f59e0b'
  if (state === 'DOWN-UNSTABLE') return '#f97316'
  if (state === 'DOWN') return '#ef4444'
  return '#9ca3af'
})

const formattedUptime = computed(() => {
  if (props.endpoint.uptime_percentage_24h == null) return '0%'
  return `${props.endpoint.uptime_percentage_24h}%`
})

const timeAgo = computed(() => {
  if (!props.endpoint.last_seen) return 'Never'
  
  const now = new Date()
  const past = new Date(props.endpoint.last_seen)
  const diffMs = now - past
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
})
</script>

<style scoped>
.endpoint-card {
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  height: 100%;
}
.endpoint-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.hostname {
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 1.1rem;
}
.ip-address {
  color: #64748b;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
.status-row {
  margin-bottom: 1rem;
}
.state-badge {
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: bold;
  display: inline-block;
}
.metrics-row {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
  color: #334155;
}
.last-seen {
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
