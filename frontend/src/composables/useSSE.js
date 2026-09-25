import { ref } from 'vue'

const sseConnected = ref(false)
let eventSource = null
let wasDisconnected = false
const listeners = new Set()
const reconnectCallbacks = new Set()
let reconnectTimer = null

function isUserLoggedIn() {
  if (typeof window === 'undefined') return false
  try {
    return !!sessionStorage.getItem('user') || !!localStorage.getItem('user')
  } catch (e) {
    return false
  }
}

function triggerReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    reconnectCallbacks.forEach((cb) => {
      try {
        cb()
      } catch (err) {
        console.error('Error in SSE reconnect callback:', err)
      }
    })
  }, 300)
}

export function closeConnection() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  sseConnected.value = false
  wasDisconnected = false
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

export function resetConnection() {
  closeConnection()
  ensureConnection()
}

function ensureConnection() {
  if (typeof window === 'undefined') return
  if (!isUserLoggedIn()) return

  if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
    try {
      eventSource = new EventSource('/api/v1/events/stream', { withCredentials: true })
      eventSource.onopen = () => {
        sseConnected.value = true
        if (wasDisconnected) {
          wasDisconnected = false
          triggerReconnect()
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
    closeConnection,
    resetConnection,
  }
}

