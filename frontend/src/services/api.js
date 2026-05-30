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

export function getEndpointEvents(id, startDate, endDate) {
    return api.get(`/reports/events/${id}`, {
        params: {
            start_date: startDate,
            end_date: endDate,
        },
    })
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

export function logout() {
  return api.post('/auth/logout')
}
