import { useEffect, useState } from 'react'
import { Search, Plus, Users, GitBranch, CheckCircle } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthUser } from '@/features/auth'
import { dashboardService, type PipelineMetrics } from '../services/dashboard.service'
import { getErrorMessage } from '@/shared/types/api'
import { KPICard } from './KPICard'
import { PipelineSummary } from './PipelineSummary'
import { HotLeadsList } from './HotLeadsList'
import type { Lead } from '@/features/leads/types'

export function DashboardPage() {
  const user = useAuthUser()
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null)
  const [hotLeads, setHotLeads] = useState<Lead[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      try {
        const [m, h] = await Promise.all([
          dashboardService.getMetrics(),
          dashboardService.getHotLeads(),
        ])
        setMetrics(m)
        setHotLeads(h)
      } catch (error) {
        toast.error(getErrorMessage(error))
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  const totalLeads = metrics?.total ?? 0
  const ganados = metrics?.stages?.['ganado']?.count ?? 0
  const convRate = totalLeads > 0 ? Math.round((ganados / totalLeads) * 100) : 0
  const enProceso =
    (metrics?.stages?.['perfilamiento']?.count ?? 0) +
    (metrics?.stages?.['calificacion_financiera']?.count ?? 0) +
    (metrics?.stages?.['agendado']?.count ?? 0)

  const today = new Date().toLocaleDateString('es-CL', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })

  return (
    <div className="flex flex-col gap-8 p-10 h-full">
      {/* ── Header ── */}
      <div className="flex items-end justify-between w-full">
        <div className="flex flex-col gap-[5px]">
          <h1 className="text-[#111827] text-[26px] font-bold leading-tight">
            {user?.name ? `Bienvenido, ${user.name}` : 'Dashboard'}
          </h1>
          <p className="text-[#9CA3AF] text-[13px]">
            {today} · Agente Sofía procesando leads activos
          </p>
        </div>

        <div className="flex items-center gap-[10px]">
          {/* Search */}
          <div className="flex items-center gap-2 bg-white border border-[#D1D9E6] rounded-lg px-4 py-[9px]">
            <Search size={14} className="text-[#9CA3AF] shrink-0" />
            <span className="text-[#9CA3AF] text-[13px]">Buscar lead...</span>
          </div>

          {/* CTA */}
          <button className="flex items-center gap-2 bg-[#1A56DB] hover:bg-[#1447C4] active:bg-[#1040B5] text-white rounded-lg px-[18px] py-[9px] transition-colors">
            <Plus size={14} className="text-white shrink-0" />
            <span className="text-white text-[13px] font-semibold">Nuevo lead</span>
          </button>
        </div>
      </div>

      {/* ── KPI Cards ── */}
      <div className="flex gap-4 w-full">
        <KPICard
          title="Total Leads"
          value={isLoading ? '—' : totalLeads}
          subtitle="en el sistema"
          icon={Users}
          variant="light"
        />
        <KPICard
          title="Tasa de Cierre"
          value={isLoading ? '—' : `${convRate}%`}
          subtitle="leads ganados"
          icon={CheckCircle}
          variant="dark"
        />
        <KPICard
          title="En Proceso"
          value={isLoading ? '—' : enProceso}
          subtitle="perfilamiento → agendado"
          icon={GitBranch}
          variant="light"
        />
      </div>

      {/* ── Bottom Grid: Pipeline + Hot Leads ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1 min-h-0">
        <PipelineSummary metrics={metrics} isLoading={isLoading} />
        <HotLeadsList leads={hotLeads} isLoading={isLoading} />
      </div>
    </div>
  )
}
