import axios from 'axios'

const api = axios.create({
  // 通过 vite proxy 转发到后端 http://localhost:8000
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截：注入 JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：401 跳登录
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const user = JSON.parse(localStorage.getItem('user') || 'null')
      const isPatient = user?.role === 'patient'
      if (isPatient) {
        localStorage.removeItem('patient_token')
        localStorage.removeItem('patient_user')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('permissions')
        if (location.pathname !== '/patient/login') location.href = '/patient/login'
      } else {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('permissions')
        if (location.pathname !== '/login') location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api
