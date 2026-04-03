import { useEffect, useState } from 'react'
import {
  Search, Plus, Users, GitBranch, CheckCircle,
  MessageSquare, Clock, TrendingUp, CalendarCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { useAuthUser } from '@/features/auth'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { dashboardService, type PipelineMetrics } from '../services/dashboard.service'
import { getErrorMessage } from '@/shared/types/api'
import { KPICard } from './KPICard'
import { PipelineSummary } from './PipelineSummary'
import { HotLeadsList } from './HotLeadsList'
import { WeeklyTrendChart } from './WeeklyTrendChart'
import { StageBarChart } from './StageBarChart'
import { StageAvgDaysTable } from './StageAvgDaysTable'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import type { Lead } from '@/features/leads/types'

export function DashboardPage() {
  const user = useAuthUser()
  const { isSuperAdmin } = usePermissions()
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null)
  const [hotLeads, setHotLeads] = useState<Lead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedBroker, setSelectedBroker] = useState<SelectedBroker | null>(null)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      try {
        const brokerId = selectedBroker?.id ?? null
        const [m, h] = await Promise.all([
          dashboardService.getMetrics(brokerId),
          dashboardService.getHotLeads(brokerId),
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
  }, [selectedBroker])

  const totalLeads = metrics?.total_leads ?? 0
  const ganados = metrics?.stage_counts?.['ganado'] ?? 0
  const convRate = metrics?.conversion_rate ?? (totalLeads > 0 ? Math.round((ganados / totalLeads) * 100) : 0)
  const enProceso =
    (metrics?.stage_counts?.['perfilamiento'] ?? 0) +
    (metrics?.stage_counts?.['calificacion_financiera'] ?? 0) +
    (metrics?.stage_counts?.['agendado'] ?? 0)

  const agendados = metrics?.stage_counts?.['agendado'] ?? 0

  // Leads esta semana: last point in weekly_trend
  const weeklyTrend = metrics?.weekly_trend ?? []
  const leadsThisWeek = weeklyTrend.length > 0 ? weeklyTrend[weeklyTrend.length - 1].count : 0
  const leadsLastWeek = weeklyTrend.length > 1 ? weeklyTrend[weeklyTrend.length - 2].count : 0
  const weeklyDelta = leadsLastWeek > 0
    ? Math.round(((leadsThisWeek - leadsLastWeek) / leadsLastWeek) * 100)
    : null

  // Tiempo promedio total (excluding ganado/perdido)
  const avgDays = metrics?.stage_avg_days ?? {}
  const activeStageKeys = ['entrada', 'perfilamiento', 'calificacion_financiera', 'potencial', 'agendado']
  const activeDays = activeStageKeys.map((k) => avgDays[k] ?? 0).filter((v) => v > 0)
  const avgTotalDays = activeDays.length > 0
    ? (activeDays.reduce((a, b) => a + b, 0) / activeDays.length).toFixed(1)
    : '—'

  const today = new Date().toLocaleDateString('es-CL', {
    weekday: 'short', day: 'numeric', month: 'short',
  })

  return (
    <div className="flex flex-col gap-5 sm:gap-6 p-4 sm:p-8 h-full overflow-y-auto">
      {/* ── Header ── */}
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3 w-full mb-4">
          <div>
            <h1 className="text-xl sm:text-[1.4375rem] font-bold text-[#111827] tracking-tight leading-tight">
              {user?.name ? `Bienvenido, ${user.name}` : 'Dashboard'}
            </h1>
            <p className="text-[#9CA3AF] text-[13px] mt-0.5">
              {today} · Sofía procesando leads activos
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isSuperAdmin && (
              <BrokerFilterBar
                value={selectedBroker}
                onChange={setSelectedBroker}
                label="Broker"
              />
            )}
            <div className="hidden sm:flex items-center gap-2 bg-white border border-[#D1D9E6] rounded-lg px-3.5 py-2 shadow-sm">
              <Search size={13} className="text-[#C4CDD8] shrink-0" />
              <span className="text-[#C4CDD8] text-[13px]">Buscar lead...</span>
            </div>
            <button className="flex items-center gap-1.5 bg-[#1A56DB] hover:bg-[#1447C4] active:bg-[#1040B5] text-white rounded-lg px-3 sm:px-4 py-2 transition-colors shadow-sm">
              <Plus size={14} className="shrink-0" />
              <span className="text-[13px] font-semibold">Nuevo lead</span>
            </button>
          </div>
        </div>
        <div className="h-px bg-[#D1D9E6]" />
      </div>

      {/* ── KPI Cards — 2 cols mobile → 4 cols lg → 7 cols xl ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-3">
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
          subtitle="perfil → agendado"
          icon={GitBranch}
          variant="light"
        />
        <KPICard
          title="Agendados"
          value={isLoading ? '—' : agendados}
          subtitle="citas programadas"
          icon={CalendarCheck}
          variant="light"
        />
        <KPICard
          title="Esta Semana"
          value={isLoading ? '—' : leadsThisWeek}
          subtitle="nuevos leads"
          icon={TrendingUp}
          variant="light"
          trend={weeklyDelta !== null ? { value: weeklyDelta, label: 'vs sem. ant.' } : undefined}
        />
        <KPICard
          title="Tasa Respuesta"
          value={isLoading ? '—' : `${metrics?.response_rate ?? 0}%`}
          subtitle="leads respondidos"
          icon={MessageSquare}
          variant="light"
        />
        <KPICard
          title="Tiempo Prom."
          value={isLoading ? '—' : `${avgTotalDays}d`}
          subtitle="por etapa activa"
          icon={Clock}
          variant="light"
        />
      </div>

      {/* ── Row 2: Weekly trend + Hot Leads ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <WeeklyTrendChart data={weeklyTrend} isLoading={isLoading} />
        </div>
        <div className="lg:col-span-1">
          <HotLeadsList leads={hotLeads} isLoading={isLoading} />
        </div>
      </div>

      {/* ── Row 3: Bar chart + Avg days table ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StageBarChart stageCounts={metrics?.stage_counts ?? {}} isLoading={isLoading} />
        <StageAvgDaysTable stageAvgDays={avgDays} isLoading={isLoading} />
      </div>

      {/* ── Row 4: Pipeline summary full width ── */}
      <PipelineSummary metrics={metrics} isLoading={isLoading} />
    </div>
  )
}
