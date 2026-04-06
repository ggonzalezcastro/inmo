import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

// Token getter — updated by auth store after login
let getToken: () => string | null = () => localStorage.getItem('token')

export function setTokenGetter(fn: () => string | null) {
  getToken = fn
}

const instance = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

instance.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (res) => res,
  (error) => {
    const requestUrl = error.config?.url ?? ''
    const isAuthEndpoint = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/register')
    if (error.response?.status === 401 && !isAuthEndpoint) {
      // Clear token and redirect to login
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

function extractData<T>(res: AxiosResponse<T>): T {
  return res.data
}

export const apiClient = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get<T>(url, config).then(extractData)
  },
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.post<T>(url, data, config).then(extractData)
  },
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.put<T>(url, data, config).then(extractData)
  },
  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.patch<T>(url, data, config).then(extractData)
  },
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete<T>(url, config).then(extractData)
  },
  postForm<T>(url: string, formData: FormData): Promise<T> {
    return instance
      .post<T>(url, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then(extractData)
  },
}
