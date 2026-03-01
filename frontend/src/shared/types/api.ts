export interface PaginatedResponse<T> {
  data: T[]
  total: number
  skip: number
  limit: number
}

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: ApiError } }
    const detail = axiosError.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  }
  if (error instanceof Error) return error.message
  return 'Ha ocurrido un error inesperado'
}
