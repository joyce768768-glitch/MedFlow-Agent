import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    permissions: JSON.parse(localStorage.getItem('permissions') || 'null'),
  }),
  getters: {
    role: (s) => s.user?.role || '',
    isAttending: (s) => s.user?.role === 'attending',
    isMdtExpert: (s) => s.user?.role === 'mdt_expert',
    isNurse: (s) => s.user?.role === 'nurse',
    isReadonly: (s) => s.user?.role === 'readonly',
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    async login(username, password) {
      const { data } = await api.post('/auth/login', { username, password })
      this.token = data.token
      this.user = data.user
      localStorage.setItem('token', data.token)
      localStorage.setItem('user', JSON.stringify(data.user))
      // 拉取权限视图
      const { data: perm } = await api.get('/auth/permissions')
      this.permissions = perm
      localStorage.setItem('permissions', JSON.stringify(perm))
    },
    async refreshPermissions() {
      const { data: perm } = await api.get('/auth/permissions')
      this.permissions = perm
      localStorage.setItem('permissions', JSON.stringify(perm))
    },
    logout() {
      this.token = ''
      this.user = null
      this.permissions = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('permissions')
    },
  },
})
