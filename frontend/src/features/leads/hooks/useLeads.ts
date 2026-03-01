import { useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { useLeadsStore } from '../store/leadsStore'
import { leadsService } from '../services/leads.service'
import { getErrorMessage } from '@/shared/types/api'

export function useLeads() {
  const { leads, total, isLoading, filters, setLeads, setLoading, setFilter, resetFilters } =
    useLeadsStore()

  const fetchLeads = useCallback(async () => {
    setLoading(true)
    try {
      const result = await leadsService.getLeads(filters)
      setLeads(result.data, result.total)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [filters, setLeads, setLoading])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads])

  return {
    leads,
    total,
    isLoading,
    filters,
    setFilter,
    resetFilters,
    refetch: fetchLeads,
  }
}
