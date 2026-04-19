import { useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { useProjectsStore } from '../store/projectsStore'
import { projectsService } from '../services/projects.service'
import { getErrorMessage } from '@/shared/types/api'

export function useProjects() {
  const {
    projects,
    total,
    orphanUnits,
    isLoading,
    filters,
    setProjects,
    setLoading,
    setFilter,
    resetFilters,
  } = useProjectsStore()

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try {
      const result = await projectsService.getProjects(filters)
      setProjects(result.items, result.total, result.orphan_units)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [filters, setProjects, setLoading])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  return {
    projects,
    total,
    orphanUnits,
    isLoading,
    filters,
    setFilter,
    resetFilters,
    refetch: fetchProjects,
  }
}
