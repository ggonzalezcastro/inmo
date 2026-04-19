import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { useProperties } from '../hooks/useProperties'
import { usePropertiesStore } from '../store/propertiesStore'
import { PropertyFiltersBar } from './PropertyFiltersBar'
import { PropertiesTable } from './PropertiesTable'
import { PropertyFormDialog } from './PropertyFormDialog'
import { PropertyDetail } from './PropertyDetail'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import type { Property } from '../types'

export function PropertiesPage() {
  const { isAdmin, isSuperAdmin } = usePermissions()
  const { properties, total, isLoading, filters, setFilter, resetFilters, refetch } = useProperties()
  const { updateProperty, removeProperty } = usePropertiesStore()

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<Property | null>(null)
  const [viewTarget, setViewTarget] = useState<Property | null>(null)

  const page = Math.floor((filters.offset ?? 0) / (filters.limit ?? 20)) + 1
  const limit = filters.limit ?? 20

  const handlePageChange = (p: number) => {
    setFilter('offset', (p - 1) * limit)
  }

  const handleBrokerChange = (broker: SelectedBroker | null) => {
    setFilter('broker_id', broker?.id ?? null)
    setFilter('offset', 0)
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
              {isAdmin && (
                <Button size="sm" onClick={() => setShowCreate(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Nueva Propiedad
                </Button>
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
        />
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
    </div>
  )
}
