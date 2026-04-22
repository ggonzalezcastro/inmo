import { ChevronRight } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { PIPELINE_STAGE_CONFIG, PIPELINE_STAGES } from '@/shared/lib/constants'
import { KanbanCard } from './KanbanCard'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu'
import { Button } from '@/shared/components/ui/button'
import type { Lead, PipelineStage } from '@/features/leads/types'
import type { IncomeTier } from '@/features/settings/services/settings.service'

interface KanbanColumnProps {
  stage: PipelineStage
  leads: Lead[]
  inactiveIds: Set<number>
  isLoading: boolean
  incomeTiers?: IncomeTier[]
  onMoveStage: (lead: Lead, stage: string) => void
  onSelectLead: (lead: Lead) => void
}

export function KanbanColumn({
  stage,
  leads,
  inactiveIds,
  isLoading,
  incomeTiers,
  onMoveStage,
  onSelectLead,
}: KanbanColumnProps) {
  const config = PIPELINE_STAGE_CONFIG[stage]
  const otherStages = PIPELINE_STAGES.filter((s) => s.key !== stage)

  return (
    <div className="flex flex-col flex-1 min-w-[100px] bg-[#F8FAFC] rounded-xl border border-[#D1D9E6] shadow-sm min-h-0">
      {/* Column header */}
      <div className={cn('px-3 py-2.5 rounded-t-xl border-b border-[#D1D9E6]', config.color)}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider">{config.label}</span>
          <span className="text-[11px] font-bold bg-white/70 rounded-full px-2 py-0.5 tabular-nums">
            {leads.length}
          </span>
        </div>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 max-h-[calc(100vh-220px)]">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-lg bg-border animate-pulse" />
            ))}
          </div>
        ) : leads.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted-foreground">Sin leads</div>
        ) : (
          leads.map((lead) => (
            <div key={lead.id} className="group relative">
              <KanbanCard
                lead={lead}
                isInactive={inactiveIds.has(lead.id)}
                incomeTiers={incomeTiers}
                onClick={() => onSelectLead(lead)}
              />
              {/* Move stage button — visible on hover, doesn't trigger card click */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label="Mover lead"
                    className="absolute top-2 right-2 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {otherStages.map((s) => (
                    <DropdownMenuItem
                      key={s.key}
                      onClick={(e) => {
                        e.stopPropagation()
                        onMoveStage(lead, s.key)
                      }}
                    >
                      {s.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
