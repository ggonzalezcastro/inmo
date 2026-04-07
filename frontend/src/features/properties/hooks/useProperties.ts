import { useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { usePropertiesStore } from '../store/propertiesStore'
import { propertiesService } from '../services/properties.service'
import { getErrorMessage } from '@/shared/types/api'

export function useProperties() {
  const {
    properties,
    total,
    isLoading,
    filters,
    setProperties,
    setLoading,
    setFilter,
    resetFilters,
  } = usePropertiesStore()

  const fetchProperties = useCallback(async () => {
    setLoading(true)
    try {
      const result = await propertiesService.getProperties(filters)
      setProperties(result.data, result.total)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [filters, setProperties, setLoading])

  useEffect(() => {
    fetchProperties()
  }, [fetchProperties])

  return {
    properties,
    total,
    isLoading,
    filters,
    setFilter,
    resetFilters,
    refetch: fetchProperties,
  }
}
