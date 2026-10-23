import axios from 'axios'
import { notify } from '../utils/notify'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v2',
  withCredentials: true,
  timeout: 30000,
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('[CareerFit API] request failed', {
      method: error.config?.method?.toUpperCase(),
      url: error.config?.url,
      status: error.response?.status,
      code: error.response?.data?.code || error.code,
      detail: error.response?.data?.detail || error.message,
      stack: error.stack,
    })
    const unauthorized = error.response?.status === 401
    const onLoginPage = typeof window !== 'undefined' && window.location.pathname === '/login'
    if (unauthorized) {
      if (!onLoginPage && typeof window !== 'undefined') window.location.assign('/login')
    } else {
      const message = error.response?.data?.detail || error.response?.data?.code || '요청을 처리하지 못했습니다.'
      notify(message, 'error')
    }
    return Promise.reject(error)
  },
)

export const unwrap = (response) => response?.data ?? response
