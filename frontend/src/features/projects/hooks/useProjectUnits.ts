import { useCallback } from 'react'
import { toast } from 'sonner'
import { useProjectsStore } from '../store/projectsStore'
import { projectsService } from '../services/projects.service'
import { getErrorMessage } from '@/shared/types/api'

const ORPHAN_GROUP_ID = 0

/**
 * Hook for lazy-loading the units of a project when its accordion row expands.
 * Caches results in the store; re-expanding doesn't refetch unless invalidated.
 */
export function useProjectUnits(projectId: number, brokerIdOverride?: number) {
  const units = useProjectsStore((s) => s.unitsByProject.get(projectId))
  const isLoading = useProjectsStore((s) => s.loadingUnits.has(projectId))
  const setUnits = useProjectsStore((s) => s.setUnits)
  const setUnitsLoading = useProjectsStore((s) => s.setUnitsLoading)
  const invalidateUnits = useProjectsStore((s) => s.invalidateUnits)

  const load = useCallback(async () => {
    if (units || isLoading) return
    setUnitsLoading(projectId, true)
    try {
      if (projectId === ORPHAN_GROUP_ID) {
        // Sin proyecto: usa /properties con no_project=true. Importado dinámicamente
        // para evitar ciclos de imports entre features.
        const { propertiesService } = await import(
          '@/features/properties/services/properties.service'
        )
        const res = await propertiesService.getProperties({
          no_project: true,
          broker_id: brokerIdOverride ?? null,
          limit: 200,
        })
        setUnits(
          projectId,
          res.data.map((p) => ({
            id: p.id,
            codigo: p.codigo,
            tipologia: p.tipologia,
            name: p.name,
            property_type: p.property_type,
            status: p.status,
            bedrooms: p.bedrooms,
            bathrooms: p.bathrooms,
            square_meters_useful: p.square_meters_useful,
            price_uf: p.price_uf,
            has_offer: p.has_offer,
            offer_price_uf: p.offer_price_uf,
            floor_number: p.floor_number,
            orientation: p.orientation,
          }))
        )
      } else {
        const res = await projectsService.getProjectUnits(projectId, {
          brokerIdOverride,
          limit: 500,
        })
        setUnits(projectId, res.items)
      }
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setUnitsLoading(projectId, false)
    }
  }, [projectId, units, isLoading, setUnits, setUnitsLoading, brokerIdOverride])

  return { units, isLoading, load, invalidate: () => invalidateUnits(projectId) }
}

export const ORPHAN_PROJECT_ID = ORPHAN_GROUP_ID
