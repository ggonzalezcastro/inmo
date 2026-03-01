import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { PIPELINE_STAGES } from '@/shared/lib/constants'
import { pipelineService } from '../services/pipeline.service'
import { KanbanColumn } from './KanbanColumn'
import { LeadDrawer } from './LeadDrawer'
import { getErrorMessage } from '@/shared/types/api'
import type { Lead, PipelineStage } from '@/features/leads/types'

type LeadsByStage = Record<string, Lead[]>

export function PipelinePage() {
  const [leadsByStage, setLeadsByStage] = useState<LeadsByStage>({})
  const [inactiveIds, setInactiveIds] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)

  const fetchAllStages = useCallback(async () => {
    setIsLoading(true)
    try {
      const results = await Promise.all(
        PIPELINE_STAGES.map((s) =>
          pipelineService.getLeadsByStage(s.key).then((leads) => [s.key, leads] as const)
        )
      )
      setLeadsByStage(Object.fromEntries(results))

      // Fetch inactive leads
      const inactiveResults = await Promise.all(
        ['entrada', 'perfilamiento', 'seguimiento'].map((s) =>
          pipelineService.getInactiveLeads(s).catch(() => [] as Lead[])
        )
      )
      const ids = new Set(inactiveResults.flat().map((l) => l.id))
      setInactiveIds(ids)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAllStages()
  }, [fetchAllStages])

  const handleMoveStage = async (lead: Lead, newStage: string) => {
    const oldStage = lead.pipeline_stage

    // Optimistic update
    setLeadsByStage((prev) => ({
      ...prev,
      [oldStage]: prev[oldStage]?.filter((l) => l.id !== lead.id) ?? [],
      [newStage]: [...(prev[newStage] ?? []), { ...lead, pipeline_stage: newStage as PipelineStage }],
    }))

    // Update selected lead's stage if it's the one being moved
    if (selectedLead?.id === lead.id) {
      setSelectedLead({ ...lead, pipeline_stage: newStage as PipelineStage })
    }

    try {
      await pipelineService.moveLeadToStage(lead.id, newStage)
      toast.success(`Lead movido a "${PIPELINE_STAGES.find((s) => s.key === newStage)?.label}"`)
    } catch (error) {
      toast.error(getErrorMessage(error))
      // Revert on error
      setLeadsByStage((prev) => ({
        ...prev,
        [newStage]: prev[newStage]?.filter((l) => l.id !== lead.id) ?? [],
        [oldStage]: [...(prev[oldStage] ?? []), lead],
      }))
    }
  }

  const totalLeads = Object.values(leadsByStage).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div className="p-8 h-full flex flex-col">
      <PageHeader
        title="Pipeline"
        description={`${totalLeads} leads en pipeline`}
        actions={
          <Button variant="outline" size="sm" onClick={fetchAllStages} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
        }
      />

      {/* Kanban board */}
      <div className="flex-1 min-h-0 overflow-x-auto">
        <div className="flex gap-3 h-full w-full min-w-0 pb-4">
          {PIPELINE_STAGES.map((s) => (
            <KanbanColumn
              key={s.key}
              stage={s.key as PipelineStage}
              leads={leadsByStage[s.key] ?? []}
              inactiveIds={inactiveIds}
              isLoading={isLoading}
              onMoveStage={handleMoveStage}
              onSelectLead={setSelectedLead}
            />
          ))}
        </div>
      </div>

      {/* Lead detail drawer */}
      <LeadDrawer
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
        onMoveStage={handleMoveStage}
      />
    </div>
  )
}
