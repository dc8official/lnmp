import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
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
  const userStr = localStorage.getItem('user')
  
  if (to.path !== '/login' && !userStr) {
    next('/login')
  } else if (to.path === '/login' && userStr) {
    next('/')
  } else {
    next()
  }
})

export default router
