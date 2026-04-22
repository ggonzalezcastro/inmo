import { useState, useEffect, useCallback, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { PIPELINE_STAGES } from '@/shared/lib/constants'
import { pipelineService } from '../services/pipeline.service'
import { settingsService, DEFAULT_SCORING_CONFIG } from '@/features/settings/services/settings.service'
import type { IncomeTier } from '@/features/settings/services/settings.service'
import { KanbanColumn } from './KanbanColumn'
import { LeadDrawer } from './LeadDrawer'
import { CloseReasonDialog } from './CloseReasonDialog'
import { PipelineFilters, type PipelineFilterValues } from './PipelineFilters'
import { FunnelMetrics } from './FunnelMetrics'
import { getErrorMessage } from '@/shared/types/api'
import type { Lead, PipelineStage } from '@/features/leads/types'

type LeadsByStage = Record<string, Lead[]>

interface PendingMove {
  lead: Lead
  targetStage: 'ganado' | 'perdido'
}

const EMPTY_FILTERS: PipelineFilterValues = {
  search: '',
  assignedTo: '',
  calificacion: '',
  created_from: '',
  created_to: '',
}

function filtersToParams(f: PipelineFilterValues): Record<string, unknown> {
  return {
    search: f.search || undefined,
    assignedTo: f.assignedTo || undefined,
    calificacion: f.calificacion || undefined,
    created_from: f.created_from || undefined,
    created_to: f.created_to || undefined,
  }
}

export function PipelinePage() {
  const [leadsByStage, setLeadsByStage] = useState<LeadsByStage>({})
  const [inactiveIds, setInactiveIds] = useState<Set<number>>(new Set())
  const [incomeTiers, setIncomeTiers] = useState<IncomeTier[]>(DEFAULT_SCORING_CONFIG.income_tiers)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [pendingClose, setPendingClose] = useState<PendingMove | null>(null)
  const [filters, setFilters] = useState<PipelineFilterValues>(EMPTY_FILTERS)
  // Debounce search input
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedFilters, setDebouncedFilters] = useState<PipelineFilterValues>(EMPTY_FILTERS)

  const handleFiltersChange = useCallback((next: PipelineFilterValues) => {
    setFilters(next)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedFilters(next), 300)
  }, [])

  const fetchAllStages = useCallback(async (f: PipelineFilterValues = debouncedFilters) => {
    setIsLoading(true)
    try {
      const params = filtersToParams(f)
      const results = await Promise.all(
        PIPELINE_STAGES.map((s) =>
          pipelineService.getLeadsByStage(s.key, params).then((leads) => [s.key, leads] as const)
        )
      )
      setLeadsByStage(Object.fromEntries(results))

      // Only fetch inactive leads when no filters active (for performance)
      const hasFilters = Object.values(f).some(Boolean)
      if (!hasFilters) {
        const inactiveResults = await Promise.all(
          ['entrada', 'perfilamiento', 'potencial'].map((s) =>
            pipelineService.getInactiveLeads(s).catch(() => [] as Lead[])
          )
        )
        const ids = new Set(inactiveResults.flat().map((l) => l.id))
        setInactiveIds(ids)
      } else {
        setInactiveIds(new Set())
      }
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }, [debouncedFilters])

  useEffect(() => {
    fetchAllStages(debouncedFilters)
  }, [debouncedFilters]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    settingsService.getConfig().then((cfg) => {
      if (cfg.scoring_config?.income_tiers?.length) {
        setIncomeTiers(cfg.scoring_config.income_tiers)
      }
    }).catch(() => { /* fallback to DEFAULT_SCORING_CONFIG already set */ })
  }, [])

  const executeMove = useCallback(async (
    lead: Lead,
    newStage: string,
    closeReason?: string,
    closeReasonDetail?: string
  ) => {
    const oldStage = lead.pipeline_stage

    setLeadsByStage((prev) => ({
      ...prev,
      [oldStage]: prev[oldStage]?.filter((l) => l.id !== lead.id) ?? [],
      [newStage]: [...(prev[newStage] ?? []), { ...lead, pipeline_stage: newStage as PipelineStage }],
    }))

    if (selectedLead?.id === lead.id) {
      setSelectedLead({ ...lead, pipeline_stage: newStage as PipelineStage })
    }

    try {
      await pipelineService.moveLeadToStage(lead.id, newStage, closeReason, closeReasonDetail)
      toast.success(`Lead movido a "${PIPELINE_STAGES.find((s) => s.key === newStage)?.label}"`)
    } catch (error) {
      toast.error(getErrorMessage(error))
      setLeadsByStage((prev) => ({
        ...prev,
        [newStage]: prev[newStage]?.filter((l) => l.id !== lead.id) ?? [],
        [oldStage]: [...(prev[oldStage] ?? []), lead],
      }))
    }
  }, [selectedLead])

  const handleMoveStage = useCallback((lead: Lead, newStage: string) => {
    if (newStage === 'ganado' || newStage === 'perdido') {
      setPendingClose({ lead, targetStage: newStage })
      return
    }
    executeMove(lead, newStage)
  }, [executeMove])

  const handleCloseConfirm = useCallback((reason: string, detail: string) => {
    if (!pendingClose) return
    executeMove(pendingClose.lead, pendingClose.targetStage, reason, detail)
    setPendingClose(null)
  }, [pendingClose, executeMove])

  const totalLeads = Object.values(leadsByStage).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 sm:px-8 pt-4 sm:pt-8 pb-0">
        <PageHeader
          title="Pipeline"
          description={`${totalLeads} leads en pipeline`}
          actions={
            <Button variant="outline" size="sm" onClick={() => fetchAllStages(filters)} disabled={isLoading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Actualizar
            </Button>
          }
        />
      </div>

      {/* Funnel metrics collapsible */}
      <FunnelMetrics />

      {/* Filters */}
      <PipelineFilters filters={filters} onChange={handleFiltersChange} />

      <div className="flex-1 min-h-0 overflow-x-auto px-4 sm:px-8">
        <div className="flex gap-3 h-full w-full min-w-0 pb-4 pt-3">
          {PIPELINE_STAGES.map((s) => (
            <KanbanColumn
              key={s.key}
              stage={s.key as PipelineStage}
              leads={leadsByStage[s.key] ?? []}
              inactiveIds={inactiveIds}
              isLoading={isLoading}
              incomeTiers={incomeTiers}
              onMoveStage={handleMoveStage}
              onSelectLead={setSelectedLead}
            />
          ))}
        </div>
      </div>

      <LeadDrawer
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
        onMoveStage={handleMoveStage}
        onLeadUpdated={(updated) => {
          setSelectedLead(updated)
          setLeadsByStage((prev) => ({
            ...prev,
            [updated.pipeline_stage]: prev[updated.pipeline_stage]?.map((l) =>
              l.id === updated.id ? updated : l
            ) ?? [],
          }))
        }}
      />

      {pendingClose && (
        <CloseReasonDialog
          lead={pendingClose.lead}
          targetStage={pendingClose.targetStage}
          onConfirm={handleCloseConfirm}
          onCancel={() => setPendingClose(null)}
        />
      )}
    </div>
  )
}
