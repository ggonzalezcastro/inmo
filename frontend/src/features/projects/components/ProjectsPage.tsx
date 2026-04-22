import { useState } from 'react'
import { Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import { useProjects } from '../hooks/useProjects'
import { useProjectsStore } from '../store/projectsStore'
import { projectsService } from '../services/projects.service'
import { propertiesService } from '@/features/properties/services/properties.service'
import { getErrorMessage } from '@/shared/types/api'
import { ProjectFiltersBar } from './ProjectFiltersBar'
import {
  ProjectAccordionRow,
  OrphanUnitsAccordionRow,
} from './ProjectAccordionRow'
import { ProjectFormDialog } from './ProjectFormDialog'
import { PropertyFormDialog } from '@/features/properties/components/PropertyFormDialog'
import { ReservePropertyModal } from '@/features/properties/components/ReservePropertyModal'
import { ORPHAN_PROJECT_ID } from '../hooks/useProjectUnits'
import type { Project, ProjectUnitSummary } from '../types'
import type { Property } from '@/features/properties/types'

export function ProjectsPage() {
  const { isAdmin, isSuperAdmin } = usePermissions()
  const { projects, total, orphanUnits, isLoading, filters, setFilter, resetFilters, refetch } =
    useProjects()
  const {
    expandedIds,
    toggleExpand,
    invalidateUnits,
    removeProject,
    updateProject: updateProjectInStore,
  } = useProjectsStore()

  const [showCreateProject, setShowCreateProject] = useState(false)
  const [editProject, setEditProject] = useState<Project | null>(null)

  const [propertyDialogOpen, setPropertyDialogOpen] = useState(false)
  const [editProperty, setEditProperty] = useState<Property | null>(null)
  const [pendingProjectId, setPendingProjectId] = useState<number | null>(null)

  const [reserveUnit, setReserveUnit] = useState<ProjectUnitSummary | null>(null)

  const [isGenerating, setIsGenerating] = useState(false)

  const handleBrokerChange = (broker: SelectedBroker | null) => {
    setFilter('broker_id', broker?.id ?? null)
  }

  const handleAddUnit = (projectId: number | null) => {
    setEditProperty(null)
    setPendingProjectId(projectId === 0 ? null : projectId)
    setPropertyDialogOpen(true)
  }

  const handleEditUnit = async (unitId: number) => {
    try {
      const prop = await propertiesService.getProperty(unitId)
      setEditProperty(prop)
      setPendingProjectId(prop.project_id ?? null)
      setPropertyDialogOpen(true)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleDeleteProject = async (project: Project) => {
    const ok = window.confirm(
      `¿Eliminar el proyecto "${project.name}"?\n\n` +
        'Las unidades asociadas no se borran: pasan a "Sin proyecto".'
    )
    if (!ok) return
    try {
      await projectsService.deleteProject(project.id, filters.broker_id ?? undefined)
      toast.success('Proyecto eliminado')
      removeProject(project.id)
      // Forzar recarga porque las unidades huérfanas cambiaron
      refetch()
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleGenerateDemo = async () => {
    const ok = window.confirm(
      '¿Generar 3 proyectos demo con propiedades aleatorias?\n\n' +
        'Se crearán proyectos chilenos con ~10 unidades distribuidas y embeddings.'
    )
    if (!ok) return
    setIsGenerating(true)
    const toastId = toast.loading('Generando proyectos y propiedades…')
    try {
      const res = await propertiesService.generateSampleProperties(
        filters.broker_id ?? undefined,
        12,
        3,
      )
      toast.success(
        `Generados ${res.created} unidades` +
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

  const totalUnitsAcrossProjects = projects.reduce((s, p) => s + (p.units_count ?? 0), 0)
  const totalUnitsAll = totalUnitsAcrossProjects + (orphanUnits?.units_count ?? 0)

  return (
    <div className="flex h-full">
      <div className="flex-1 p-4 sm:p-8 overflow-y-auto">
        <PageHeader
          title="Inventario"
          description={`${total} proyectos · ${totalUnitsAll} unidades`}
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
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleGenerateDemo}
                    disabled={isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="mr-2 h-4 w-4" />
                    )}
                    Generar demo
                  </Button>
                  <Button size="sm" onClick={() => setShowCreateProject(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Nuevo proyecto
                  </Button>
                </>
              )}
            </>
          }
        />

        <div className="mb-4">
          <ProjectFiltersBar
            filters={filters}
            onFilterChange={setFilter}
            onReset={resetFilters}
          />
        </div>

        {isLoading && projects.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="h-5 w-5 mr-2 animate-spin" />
            Cargando proyectos…
          </div>
        ) : projects.length === 0 && !orphanUnits?.units_count ? (
          <div className="border border-dashed rounded-lg p-12 text-center text-sm text-muted-foreground">
            No hay proyectos ni propiedades. Crea tu primer proyecto para comenzar.
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((project) => (
              <ProjectAccordionRow
                key={project.id}
                project={project}
                expanded={expandedIds.has(project.id)}
                onToggle={() => toggleExpand(project.id)}
                brokerIdOverride={filters.broker_id ?? undefined}
                onAddUnit={handleAddUnit}
                onEditProject={setEditProject}
                onDeleteProject={handleDeleteProject}
                onEditUnit={handleEditUnit}
                onReserveUnit={setReserveUnit}
              />
            ))}
            {orphanUnits && orphanUnits.units_count > 0 && (
              <OrphanUnitsAccordionRow
                aggregate={orphanUnits}
                expanded={expandedIds.has(ORPHAN_PROJECT_ID)}
                onToggle={() => toggleExpand(ORPHAN_PROJECT_ID)}
                brokerIdOverride={filters.broker_id ?? undefined}
                onAddUnit={handleAddUnit}
                onEditUnit={handleEditUnit}
                onReserveUnit={setReserveUnit}
              />
            )}
          </div>
        )}
      </div>

      {/* Project create/edit dialogs */}
      <ProjectFormDialog
        open={showCreateProject}
        onOpenChange={setShowCreateProject}
        onSuccess={() => {
          refetch()
          setShowCreateProject(false)
        }}
        brokerIdOverride={filters.broker_id ?? undefined}
      />
      <ProjectFormDialog
        open={!!editProject}
        onOpenChange={(open) => !open && setEditProject(null)}
        project={editProject}
        onSuccess={(p) => {
          updateProjectInStore(p.id, p)
          setEditProject(null)
        }}
        brokerIdOverride={filters.broker_id ?? undefined}
      />

      {/* Property create/edit dialog (shared with the per-project + button) */}
      <PropertyFormDialog
        open={propertyDialogOpen}
        onOpenChange={(open) => {
          setPropertyDialogOpen(open)
          if (!open) {
            setEditProperty(null)
            setPendingProjectId(null)
          }
        }}
        property={editProperty}
        initialProjectId={pendingProjectId}
        brokerIdOverride={filters.broker_id ?? undefined}
        onSuccess={(prop) => {
          // Invalidate cache so the accordion reloads its units next expand
          if (prop.project_id) invalidateUnits(prop.project_id)
          else invalidateUnits(ORPHAN_PROJECT_ID)
          // Also invalidate the previous project if a unit moved
          if (editProperty?.project_id && editProperty.project_id !== prop.project_id) {
            invalidateUnits(editProperty.project_id)
          }
          setPropertyDialogOpen(false)
          setEditProperty(null)
          setPendingProjectId(null)
          refetch()
        }}
      />
      {/* Reserve unit modal */}
      {reserveUnit && (
        <ReservePropertyModal
          property={{ ...reserveUnit, status: reserveUnit.status as 'available' } as unknown as Property}
          open={!!reserveUnit}
          onOpenChange={(open) => !open && setReserveUnit(null)}
          onSuccess={() => {
            // Invalidate units cache so status badge updates
            refetch()
            setReserveUnit(null)
          }}
        />
      )}
    </div>
  )
}
