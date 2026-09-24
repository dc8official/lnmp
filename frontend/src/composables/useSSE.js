import { ref } from 'vue'

const sseConnected = ref(false)
let eventSource = null
let wasDisconnected = false
const listeners = new Set()
const reconnectCallbacks = new Set()

function ensureConnection() {
  if (typeof window === 'undefined') return
  if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
    try {
      eventSource = new EventSource('/api/v1/events/stream', { withCredentials: true })
      eventSource.onopen = () => {
        sseConnected.value = true
        if (wasDisconnected) {
          wasDisconnected = false
          // Trigger all registered resync hooks
          reconnectCallbacks.forEach((cb) => {
            try {
              cb()
            } catch (err) {
              console.error('Error in SSE reconnect callback:', err)
            }
          })
        }
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
        wasDisconnected = true
      }
    } catch (err) {
      sseConnected.value = false
      wasDisconnected = true
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

  function onReconnect(callback) {
    reconnectCallbacks.add(callback)
    return () => {
      reconnectCallbacks.delete(callback)
    }
  }

  return {
    sseConnected,
    subscribe,
    onReconnect,
  }
}
