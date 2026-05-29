<template>
  <div class="dashboard-container">
    <header class="dashboard-header">
      <div class="header-info">
        <h1>Network Dashboard</h1>
        <p class="subtitle" v-if="!loading && !error">
          Monitoring {{ endpoints.length }} endpoints | Last refreshed: {{ lastRefreshedTime }}
        </p>
      </div>
      <Button 
        icon="pi pi-refresh" 
        label="Refresh" 
        @click="fetchEndpoints" 
        :loading="loading"
        severity="secondary"
      />
    </header>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <div v-else-if="loading && endpoints.length === 0" class="loading-state">
      Loading endpoints...
    </div>

    <div v-else class="endpoint-grid">
      <EndpointCard 
        v-for="endpoint in endpoints" 
        :key="endpoint.id" 
        :endpoint="endpoint" 
        @select="navigateToEndpoint"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getEndpoints } from '../services/api.js'
import EndpointCard from '../components/EndpointCard.vue'
import Button from 'primevue/button'

const router = useRouter()
const endpoints = ref([])
const loading = ref(false)
const error = ref(null)
const lastRefreshed = ref(null)

const fetchEndpoints = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await getEndpoints()
    endpoints.value = response.data.data
    lastRefreshed.value = new Date()
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Failed to fetch endpoints. Ensure the backend is running.'
  } finally {
    loading.value = false
  }
}

const navigateToEndpoint = (id) => {
  router.push(`/endpoints/${id}`)
}

const lastRefreshedTime = computed(() => {
  if (!lastRefreshed.value) return 'Never'
  return lastRefreshed.value.toLocaleTimeString()
})

onMounted(() => {
  fetchEndpoints()
})
</script>

<style scoped>
.dashboard-container {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
h1 {
  font-size: 1.8rem;
  margin-bottom: 0.25rem;
}
.subtitle {
  color: #64748b;
  font-size: 0.95rem;
}
.error-message {
  background-color: #fee2e2;
  color: #b91c1c;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}
.loading-state {
  color: #64748b;
  font-size: 1.1rem;
  text-align: center;
  padding: 3rem 0;
}
.endpoint-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(1, 1fr);
}

@media (min-width: 768px) {
  .endpoint-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .endpoint-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
