import { useState } from 'react'
import { Plus, Sparkles, Loader2, LayoutGrid, List } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { useProperties } from '../hooks/useProperties'
import { usePropertiesStore } from '../store/propertiesStore'
import { propertiesService } from '../services/properties.service'
import { getErrorMessage } from '@/shared/types/api'
import { PropertyFiltersBar } from './PropertyFiltersBar'
import { PropertiesTable } from './PropertiesTable'
import { PropertyGrid } from './PropertyGrid'
import { PropertyFormDialog } from './PropertyFormDialog'
import { PropertyDetail } from './PropertyDetail'
import { ReservePropertyModal } from './ReservePropertyModal'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import type { Property } from '../types'

type ViewMode = 'table' | 'grid'

export function PropertiesPage() {
  const { isAdmin, isSuperAdmin } = usePermissions()
  const { properties, total, isLoading, filters, setFilter, resetFilters, refetch } = useProperties()
  const { updateProperty, removeProperty } = usePropertiesStore()

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<Property | null>(null)
  const [viewTarget, setViewTarget] = useState<Property | null>(null)
  const [reserveTarget, setReserveTarget] = useState<Property | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('table')

  const page = Math.floor((filters.offset ?? 0) / (filters.limit ?? 20)) + 1
  const limit = filters.limit ?? 20

  const handlePageChange = (p: number) => {
    setFilter('offset', (p - 1) * limit)
  }

  const handleBrokerChange = (broker: SelectedBroker | null) => {
    setFilter('broker_id', broker?.id ?? null)
    setFilter('offset', 0)
  }

  const handleGenerate = async () => {
    const ok = window.confirm(
      '¿Generar 10 propiedades de prueba con datos chilenos aleatorios?\n\n' +
      'Se crearán en el broker actualmente seleccionado e incluirán embeddings ' +
      'para búsqueda semántica. Esta acción no se puede deshacer fácilmente.'
    )
    if (!ok) return
    setIsGenerating(true)
    const toastId = toast.loading('Generando 10 propiedades y embeddings…')
    try {
      const res = await propertiesService.generateSampleProperties(
        filters.broker_id ?? undefined,
        10,
      )
      toast.success(
        `Se generaron ${res.created} propiedades` +
          (res.embed_failures > 0 ? ` (${res.embed_failures} sin embedding)` : ''),
        { id: toastId },
      )
      refetch()
    } catch (error) {
      toast.error(getErrorMessage(error), { id: toastId })
    } finally {
      setIsGenerating(false)
    }
  }

  const selectedBroker = filters.broker_id
    ? { id: filters.broker_id as number, name: '' }
    : null

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex-1 p-4 sm:p-8 overflow-y-auto">
        <PageHeader
          title="Propiedades"
          description={`${total} propiedades`}
          actions={
            <>
              {isSuperAdmin && (
                <BrokerFilterBar
                  value={selectedBroker}
                  onChange={handleBrokerChange}
                  label="Broker"
                />
              )}
              {/* View mode toggle */}
              <div className="flex items-center border rounded-md overflow-hidden">
                <Button
                  size="sm"
                  variant={viewMode === 'table' ? 'default' : 'ghost'}
                  className="rounded-none h-8 px-2"
                  onClick={() => setViewMode('table')}
                  title="Vista tabla"
                >
                  <List className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant={viewMode === 'grid' ? 'default' : 'ghost'}
                  className="rounded-none h-8 px-2"
                  onClick={() => setViewMode('grid')}
                  title="Vista tarjetas"
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
              </div>
              {isAdmin && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    title="Generar 10 propiedades de prueba con datos aleatorios"
                  >
                    {isGenerating ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="mr-2 h-4 w-4" />
                    )}
                    Generar propiedades
                  </Button>
                  <Button size="sm" onClick={() => setShowCreate(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Nueva Propiedad
                  </Button>
                </>
              )}
            </>
          }
        />

        <div className="mb-4">
          <PropertyFiltersBar
            filters={filters}
            onFilterChange={setFilter}
            onReset={resetFilters}
          />
        </div>

        {viewMode === 'grid' ? (
          <PropertyGrid
            properties={properties}
            onView={setViewTarget}
            onEdit={setEditTarget}
            onReserve={setReserveTarget}
          />
        ) : (
          <PropertiesTable
            properties={properties}
            total={total}
            isLoading={isLoading}
            page={page}
            limit={limit}
            onPageChange={handlePageChange}
            onEdit={setEditTarget}
            onView={setViewTarget}
            onDeleted={removeProperty}
            onReserve={setReserveTarget}
          />
        )}
      </div>

      {/* Side panel */}
      {viewTarget && (
        <PropertyDetail
          property={viewTarget}
          onClose={() => setViewTarget(null)}
          onEdit={(p) => {
            setEditTarget(p)
            setViewTarget(null)
          }}
        />
      )}

      {/* Create dialog */}
      <PropertyFormDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onSuccess={() => {
          refetch()
          setShowCreate(false)
        }}
        brokerIdOverride={filters.broker_id ?? undefined}
      />

      {/* Edit dialog */}
      <PropertyFormDialog
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        property={editTarget}
        onSuccess={(prop) => {
          updateProperty(prop.id, prop)
          setEditTarget(null)
        }}
        brokerIdOverride={filters.broker_id ?? undefined}
      />

      {/* Reserve modal */}
      {reserveTarget && (
        <ReservePropertyModal
          property={reserveTarget}
          open={!!reserveTarget}
          onOpenChange={(open) => !open && setReserveTarget(null)}
          onSuccess={() => {
            refetch()
            setReserveTarget(null)
          }}
        />
      )}
    </div>
  )
}
