import { ref } from 'vue'

const sseConnected = ref(false)
let eventSource = null
const listeners = new Set()

function ensureConnection() {
  if (typeof window === 'undefined') return
  if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
    try {
      eventSource = new EventSource('/api/v1/events/stream')
      eventSource.onopen = () => {
        sseConnected.value = true
      }
      eventSource.onmessage = (event) => {
        if (!event.data) return
        listeners.forEach((callback) => {
          try {
            callback(event)
          } catch (err) {
            console.error('Error in SSE listener:', err)
          }
        })
      }
      eventSource.onerror = () => {
        sseConnected.value = false
      }
    } catch (err) {
      sseConnected.value = false
    }
  }
}

export function useSSE() {
  ensureConnection()

  function subscribe(callback) {
    ensureConnection()
    listeners.add(callback)
    return () => {
      listeners.delete(callback)
    }
  }

  return {
    sseConnected,
    subscribe,
  }
}
