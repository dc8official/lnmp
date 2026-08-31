import { createRouter, createWebHistory } from 'vue-router'
import { loadUserFromStorage, isValidUserObject } from '../services/auth'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
  },
  {
    path: '/topology',
    name: 'Topology',
    component: () => import('../components/TopologyMap.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: () => import('../views/SettingsView.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/endpoints/:id',
    name: 'EndpointDetail',
    component: () => import('../views/EndpointDetailView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const currentUserState = loadUserFromStorage()
  const isAuthenticated = isValidUserObject(currentUserState)

  if (to.path !== '/login' && !isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
