import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

export function getEndpoints(status = null) {
  const params = {}
  if (status) params.status = status
  return api.get('/endpoints/', { params })
}

export function getEndpoint(id) {
  return api.get(`/endpoints/${id}`)
}

export function getUptimeReport(id, startDate, endDate) {
  return api.get(`/reports/uptime/${id}`, {
    params: {
      start_date: startDate,
      end_date: endDate,
    },
  })
}

export function getIncidents(
  id,
  startDate,
  endDate,
  page = 1,
  pageSize = 50
) {
  return api.get(`/reports/incidents/${id}`, {
    params: {
      start_date: startDate,
      end_date: endDate,
      page,
      page_size: pageSize,
    },
  })
}

export function getEndpointEvents(id, startDate, endDate, page = 1, size = 100) {
    return api.get(`/reports/events/${id}`, {
        params: {
            start_date: startDate,
            end_date: endDate,
            page,
            size,
        },
    })
}

export function exportBatchTelemetry(endpointIds, startTime, endTime) {
    return api.post('/telemetry/export/batch', {
        endpoint_ids: endpointIds,
        start_time: startTime,
        end_time: endTime,
    }, {
        responseType: 'blob',
    })
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

export function logout() {
  return api.post('/auth/logout')
}

export function createEndpoint(dataOrIp, hostname, device_type, location) {
  if (typeof dataOrIp === 'object' && dataOrIp !== null) {
    return api.post('/endpoints/', dataOrIp)
  }
  return api.post('/endpoints/', {
    ip_address: dataOrIp,
    hostname,
    device_type,
    location,
  })
}

export function updateEndpoint(id, data) {
  return api.patch(`/endpoints/${id}`, data)
}

export function deleteEndpoint(id) {
  return api.delete(`/endpoints/${id}`)
}

export function changePassword(data) {
  return api.post('/auth/change-password', data)
}

export function getUsers() {
  return api.get('/users/')
}

export function createUser(data) {
  return api.post('/users/', data)
}

export function resetUserPassword(userId, data) {
  return api.post(`/users/${userId}/reset-password`, data)
}

export function updateUser(userId, data) {
  return api.patch(`/users/${userId}`, data)
}

export function deleteUser(userId) {
  return api.delete(`/users/${userId}`)
}
