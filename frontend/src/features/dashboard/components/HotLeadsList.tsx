import { useNavigate } from 'react-router-dom'
import { Flame, ChevronRight } from 'lucide-react'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import { EmptyState } from '@/shared/components/common/EmptyState'
import type { Lead } from '@/features/leads/types'

interface HotLeadsListProps {
  leads: Lead[]
  isLoading: boolean
}

export function HotLeadsList({ leads, isLoading }: HotLeadsListProps) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <div className="flex items-center gap-2">
          <Flame size={14} className="text-rose-500" />
          <span className="text-[#111827] text-[14px] font-bold">Leads Calientes</span>
        </div>
        <div className="flex items-center gap-1.5 bg-[#EBF2FF] rounded-full px-2 py-1">
          <div className="w-[6px] h-[6px] bg-[#1A56DB] rounded-full animate-pulse shrink-0" />
          <span className="text-[#1A56DB] text-[11px] font-semibold">
            {leads.length} activos
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-col gap-0">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 mx-5 my-3 rounded-lg bg-[#F0F4F8] animate-pulse"
              />
            ))}
          </div>
        ) : leads.length === 0 ? (
          <div className="flex items-center justify-center flex-1 p-10">
            <EmptyState
              icon={Flame}
              title="Sin leads calientes"
              description="Los leads con score alto aparecerán aquí"
            />
          </div>
        ) : (
          leads.map((lead) => (
            <div
              key={lead.id}
              onClick={() => navigate('/leads')}
              className="flex items-center justify-between px-5 py-3 border-b border-[#F0F4F8] last:border-0 hover:bg-[#FAFBFD] cursor-pointer transition-colors group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-[6px] h-[6px] rounded-full bg-rose-400 shrink-0" />
                <div className="min-w-0">
                  <p className="text-[#111827] text-[13px] font-semibold truncate">
                    {lead.name}
                  </p>
                  <p className="text-[#9CA3AF] text-[11px] truncate">{lead.phone}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <PipelineStageBadge stage={lead.pipeline_stage} size="sm" />
                <ScoreBadge score={lead.lead_score} size="sm" />
                <ChevronRight
                  size={12}
                  className="text-[#C4CDD8] opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
