import { useState } from 'react'
import { Plus, Upload } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { useLeads } from '../hooks/useLeads'
import { useLeadsStore } from '../store/leadsStore'
import { LeadFiltersBar } from './LeadFiltersBar'
import { LeadsTable } from './LeadsTable'
import { LeadFormDialog } from './LeadFormDialog'
import { LeadDetail } from './LeadDetail'
import { ImportCSVDialog } from './ImportCSVDialog'
import type { Lead } from '../types'

export function LeadsPage() {
  const { isAdmin } = usePermissions()
  const { leads, total, isLoading, filters, setFilter, resetFilters, refetch } = useLeads()
  const { updateLead, removeLead } = useLeadsStore()

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<Lead | null>(null)
  const [viewTarget, setViewTarget] = useState<Lead | null>(null)
  const [showImport, setShowImport] = useState(false)

  const page = Math.floor((filters.skip ?? 0) / (filters.limit ?? 20)) + 1
  const limit = filters.limit ?? 20

  const handlePageChange = (p: number) => {
    setFilter('skip', (p - 1) * limit)
  }

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex-1 p-8 overflow-y-auto">
        <PageHeader
          title="Leads"
          description={`${total} leads en total`}
          actions={
            isAdmin ? (
              <>
                <Button variant="outline" size="sm" onClick={() => setShowImport(true)}>
                  <Upload className="mr-2 h-4 w-4" />
                  Importar CSV
                </Button>
                <Button size="sm" onClick={() => setShowCreate(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Nuevo Lead
                </Button>
              </>
            ) : null
          }
        />

        <div className="mb-4">
          <LeadFiltersBar
            filters={filters}
            onFilterChange={setFilter}
            onReset={resetFilters}
          />
        </div>

        <LeadsTable
          leads={leads}
          total={total}
          isLoading={isLoading}
          page={page}
          limit={limit}
          onPageChange={handlePageChange}
          onEdit={setEditTarget}
          onView={setViewTarget}
          onDeleted={removeLead}
        />
      </div>

      {/* Side panel — Lead detail */}
      {viewTarget && (
        <LeadDetail
          lead={viewTarget}
          onClose={() => setViewTarget(null)}
          onUpdate={(updated) => {
            updateLead(updated.id, updated)
            setViewTarget(updated)
          }}
        />
      )}

      {/* Dialogs */}
      <LeadFormDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onSuccess={() => {
          refetch()
          setShowCreate(false)
        }}
      />
      <LeadFormDialog
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        lead={editTarget}
        onSuccess={(lead) => {
          updateLead(lead.id, lead)
          setEditTarget(null)
        }}
      />
      <ImportCSVDialog
        open={showImport}
        onOpenChange={setShowImport}
        onSuccess={refetch}
      />
    </div>
  )
}
