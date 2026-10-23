import { defineStore } from 'pinia'
import { api, unwrap } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, ready: false }),
  getters: { authenticated: (state) => Boolean(state.user) },
  actions: {
    async restore() {
      try { this.user = unwrap(await api.get('/auth/session')) } catch { this.user = null }
      finally { this.ready = true }
    },
    async login() {
      this.user = unwrap(await api.post('/auth/session'))
      this.ready = true
    },
    async logout() {
      await api.delete('/auth/session')
      this.user = null
    },
  },
})
