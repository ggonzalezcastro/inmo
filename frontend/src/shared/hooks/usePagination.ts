import { useState, useCallback } from 'react'

interface PaginationState {
  page: number
  limit: number
  skip: number
}

interface PaginationActions {
  setPage: (page: number) => void
  setLimit: (limit: number) => void
  nextPage: () => void
  prevPage: () => void
  reset: () => void
}

export function usePagination(initialLimit = 20): PaginationState & PaginationActions {
  const [page, setPageState] = useState(1)
  const [limit, setLimitState] = useState(initialLimit)

  const setPage = useCallback((p: number) => setPageState(p), [])
  const setLimit = useCallback((l: number) => { setLimitState(l); setPageState(1) }, [])
  const nextPage = useCallback(() => setPageState((p) => p + 1), [])
  const prevPage = useCallback(() => setPageState((p) => Math.max(1, p - 1)), [])
  const reset = useCallback(() => setPageState(1), [])

  return {
    page,
    limit,
    skip: (page - 1) * limit,
    setPage,
    setLimit,
    nextPage,
    prevPage,
    reset,
  }
}
