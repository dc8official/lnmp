import { ref } from 'vue'

export const user = ref(null)
export const currentUser = ref(null)
export const isAdmin = ref(false)
export const mustChangePassword = ref(false)

export function loadUserFromStorage() {
  const storedUser = localStorage.getItem('user')
  if (storedUser) {
    try {
      const parsed = JSON.parse(storedUser)
      user.value = parsed
      currentUser.value = parsed.username || null
      isAdmin.value = parsed.role === 'ADMIN'
      mustChangePassword.value = !!parsed.must_change_password
      return parsed
    } catch (e) {
      console.error('Failed to parse user state:', e)
    }
  }
  user.value = null
  currentUser.value = null
  isAdmin.value = false
  mustChangePassword.value = false
  return null
}

export function setUserState(userData) {
  localStorage.setItem('user', JSON.stringify(userData))
  user.value = userData
  currentUser.value = userData.username || null
  isAdmin.value = userData.role === 'ADMIN'
  mustChangePassword.value = !!userData.must_change_password
}

export function clearUserState() {
  localStorage.removeItem('user')
  user.value = null
  currentUser.value = null
  isAdmin.value = false
  mustChangePassword.value = false
}
