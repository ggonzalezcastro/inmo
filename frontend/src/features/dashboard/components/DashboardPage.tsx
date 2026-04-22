import { useEffect, useState } from 'react'
import {
  Search, Plus, Users, GitBranch, CheckCircle,
  MessageSquare, Clock, TrendingUp, CalendarCheck,
  TrendingUp as TrendUp, Wallet, Handshake, BadgeCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { useAuthUser } from '@/features/auth'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { dashboardService, type PipelineMetrics } from '../services/dashboard.service'
import { dealsApi, type DealMetrics } from '@/features/deals/services/dealsApi'
import { getErrorMessage } from '@/shared/types/api'
import { KPICard } from './KPICard'
import { PipelineSummary } from './PipelineSummary'
import { HotLeadsList } from './HotLeadsList'
import { WeeklyTrendChart } from './WeeklyTrendChart'
import { StageBarChart } from './StageBarChart'
import { StageAvgDaysTable } from './StageAvgDaysTable'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import { DealsByStageChart } from '@/features/deals/components/DealsByStageChart'
import { DealUFTrendChart } from '@/features/deals/components/DealUFTrendChart'
import { PeriodSelector, type DateRange } from '@/features/deals/components/PeriodSelector'
import { cn } from '@/shared/lib/utils'
import type { Lead } from '@/features/leads/types'

type Tab = 'leads' | 'ventas'

function formatUF(v: number) {
  if (v === 0) return '0 UF'
  return v.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' UF'
}

function defaultPeriod(): DateRange {
  const today = new Date()
  const from = new Date(today)
  from.setMonth(from.getMonth() - 1)
  return { date_from: from.toISOString().slice(0, 10), date_to: today.toISOString().slice(0, 10) }
}

export function DashboardPage() {
  const user = useAuthUser()
  const { isSuperAdmin } = usePermissions()
  const [activeTab, setActiveTab] = useState<Tab>('leads')
  const [selectedBroker, setSelectedBroker] = useState<SelectedBroker | null>(null)

  // ── Leads tab state ───────────────────────────────────────────────────────
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null)
  const [hotLeads, setHotLeads] = useState<Lead[]>([])
  const [isLeadsLoading, setIsLeadsLoading] = useState(true)

  // ── Ventas tab state ──────────────────────────────────────────────────────
  const [dealMetrics, setDealMetrics] = useState<DealMetrics | null>(null)
  const [isDealLoading, setIsDealLoading] = useState(false)
  const [period, setPeriod] = useState<DateRange>(defaultPeriod())
  const [dealLoaded, setDealLoaded] = useState(false)

  const brokerId = selectedBroker?.id ?? null

  useEffect(() => {
    const load = async () => {
      setIsLeadsLoading(true)
      try {
        const [m, h] = await Promise.all([
          dashboardService.getMetrics(brokerId),
          dashboardService.getHotLeads(brokerId),
        ])
        setMetrics(m)
        setHotLeads(h)
      } catch (error) {
        toast.error(getErrorMessage(error))
      } finally {
        setIsLeadsLoading(false)
      }
    }
    load()
  }, [brokerId])

  // Load deal metrics when ventas tab first opened or period/broker changes
  useEffect(() => {
    if (activeTab !== 'ventas') return
    const load = async () => {
      setIsDealLoading(true)
      try {
        const data = await dealsApi.getMetrics({
          broker_id: brokerId,
          date_from: period.date_from || undefined,
          date_to: period.date_to || undefined,
        })
        setDealMetrics(data)
        setDealLoaded(true)
      } catch (err) {
        toast.error(getErrorMessage(err))
      } finally {
        setIsDealLoading(false)
      }
    }
    load()
  }, [activeTab, brokerId, period])

  // ── Leads computed values ─────────────────────────────────────────────────
  const totalLeads = metrics?.total_leads ?? 0
  const ganados = metrics?.stage_counts?.['ganado'] ?? 0
  const convRate = metrics?.conversion_rate ?? (totalLeads > 0 ? Math.round((ganados / totalLeads) * 100) : 0)
  const enProceso =
    (metrics?.stage_counts?.['perfilamiento'] ?? 0) +
    (metrics?.stage_counts?.['calificacion_financiera'] ?? 0) +
    (metrics?.stage_counts?.['agendado'] ?? 0)
  const agendados = metrics?.stage_counts?.['agendado'] ?? 0
  const weeklyTrend = metrics?.weekly_trend ?? []
  const leadsThisWeek = weeklyTrend.length > 0 ? weeklyTrend[weeklyTrend.length - 1].count : 0
  const leadsLastWeek = weeklyTrend.length > 1 ? weeklyTrend[weeklyTrend.length - 2].count : 0
  const weeklyDelta = leadsLastWeek > 0
    ? Math.round(((leadsThisWeek - leadsLastWeek) / leadsLastWeek) * 100)
    : null
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
            {activeTab === 'leads' && (
              <>
                <div className="hidden sm:flex items-center gap-2 bg-white border border-[#D1D9E6] rounded-lg px-3.5 py-2 shadow-sm">
                  <Search size={13} className="text-[#C4CDD8] shrink-0" />
                  <span className="text-[#C4CDD8] text-[13px]">Buscar lead...</span>
                </div>
                <button className="flex items-center gap-1.5 bg-[#1A56DB] hover:bg-[#1447C4] active:bg-[#1040B5] text-white rounded-lg px-3 sm:px-4 py-2 transition-colors shadow-sm">
                  <Plus size={14} className="shrink-0" />
                  <span className="text-[13px] font-semibold">Nuevo lead</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="flex items-end gap-0 border-b border-[#D1D9E6]">
          {(['leads', 'ventas'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-5 py-2.5 text-[13px] font-semibold capitalize transition-colors border-b-2 -mb-px',
                activeTab === tab
                  ? 'border-[#1A56DB] text-[#1A56DB]'
                  : 'border-transparent text-[#6B7280] hover:text-[#374151]'
              )}
            >
              {tab === 'leads' ? 'Leads' : 'Ventas'}
            </button>
          ))}
        </div>
      </div>

      {/* ── TAB: Leads ── */}
      {activeTab === 'leads' && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-3">
            <KPICard title="Total Leads" value={isLeadsLoading ? '—' : totalLeads} subtitle="en el sistema" icon={Users} variant="light" />
            <KPICard title="Tasa de Cierre" value={isLeadsLoading ? '—' : `${convRate}%`} subtitle="leads ganados" icon={CheckCircle} variant="dark" />
            <KPICard title="En Proceso" value={isLeadsLoading ? '—' : enProceso} subtitle="perfil → agendado" icon={GitBranch} variant="light" />
            <KPICard title="Agendados" value={isLeadsLoading ? '—' : agendados} subtitle="citas programadas" icon={CalendarCheck} variant="light" />
            <KPICard
              title="Esta Semana"
              value={isLeadsLoading ? '—' : leadsThisWeek}
              subtitle="nuevos leads"
              icon={TrendingUp}
              variant="light"
              trend={weeklyDelta !== null ? { value: weeklyDelta, label: 'vs sem. ant.' } : undefined}
            />
            <KPICard title="Tasa Respuesta" value={isLeadsLoading ? '—' : `${metrics?.response_rate ?? 0}%`} subtitle="leads respondidos" icon={MessageSquare} variant="light" />
            <KPICard title="Tiempo Prom." value={isLeadsLoading ? '—' : `${avgTotalDays}d`} subtitle="por etapa activa" icon={Clock} variant="light" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <WeeklyTrendChart data={weeklyTrend} isLoading={isLeadsLoading} />
            </div>
            <div className="lg:col-span-1">
              <HotLeadsList leads={hotLeads} isLoading={isLeadsLoading} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <StageBarChart stageCounts={metrics?.stage_counts ?? {}} isLoading={isLeadsLoading} />
            <StageAvgDaysTable stageAvgDays={avgDays} isLoading={isLeadsLoading} />
          </div>

          <PipelineSummary metrics={metrics} isLoading={isLeadsLoading} />
        </>
      )}

      {/* ── TAB: Ventas ── */}
      {activeTab === 'ventas' && (
        <>
          <PeriodSelector value={period} onChange={setPeriod} />

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KPICard title="UF en Pipeline" value={isDealLoading ? '—' : formatUF(dealMetrics?.uf_en_pipeline ?? 0)} subtitle="deals activos" icon={TrendUp} variant="dark" />
            <KPICard title="UF Cerradas" value={isDealLoading ? '—' : formatUF(dealMetrics?.uf_cerradas ?? 0)} subtitle="escrituras firmadas" icon={Wallet} variant="light" />
            <KPICard title="Deals Activos" value={isDealLoading ? '—' : dealMetrics?.total_active_deals ?? 0} subtitle="sin cancelados" icon={Handshake} variant="light" />
            <KPICard title="Aprobación Banco" value={isDealLoading ? '—' : `${dealMetrics?.bank_approval_rate ?? 0}%`} subtitle="tasa de aprobación" icon={BadgeCheck} variant="light" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DealsByStageChart dealsByStage={dealMetrics?.deals_by_stage ?? {}} isLoading={isDealLoading} />
            <DealUFTrendChart data={dealMetrics?.uf_trend ?? []} isLoading={isDealLoading} />
          </div>
        </>
      )}
    </div>
  )
}
