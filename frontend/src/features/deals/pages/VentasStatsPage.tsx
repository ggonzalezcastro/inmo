import { useEffect, useState } from 'react'
import { TrendingUp, Wallet, Handshake, BadgeCheck } from 'lucide-react'
import { toast } from 'sonner'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import { KPICard } from '@/features/dashboard/components/KPICard'
import { getErrorMessage } from '@/shared/types/api'
import { dealsApi, type DealMetrics } from '../services/dealsApi'
import { DealsByStageChart } from '../components/DealsByStageChart'
import { DealUFTrendChart } from '../components/DealUFTrendChart'
import { PeriodSelector, type DateRange } from '../components/PeriodSelector'

function formatUF(v: number) {
  if (v === 0) return '0 UF'
  if (v >= 1000) {
    return v.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' UF'
  }
  return v.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + ' UF'
}

function defaultRange(): DateRange {
  const today = new Date()
  const from = new Date(today)
  from.setMonth(from.getMonth() - 1)
  return {
    date_from: from.toISOString().slice(0, 10),
    date_to: today.toISOString().slice(0, 10),
  }
}

export function VentasStatsPage() {
  const { isSuperAdmin } = usePermissions()
  const [selectedBroker, setSelectedBroker] = useState<SelectedBroker | null>(null)
  const [period, setPeriod] = useState<DateRange>(defaultRange())
  const [metrics, setMetrics] = useState<DealMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      try {
        const data = await dealsApi.getMetrics({
          broker_id: selectedBroker?.id ?? null,
          date_from: period.date_from || undefined,
          date_to: period.date_to || undefined,
        })
        setMetrics(data)
      } catch (err) {
        toast.error(getErrorMessage(err))
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [selectedBroker, period])

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
              Estadísticas de Ventas
            </h1>
            <p className="text-[#9CA3AF] text-[13px] mt-0.5">
              {today} · Resumen de deals y UF
            </p>
          </div>
          {isSuperAdmin && (
            <BrokerFilterBar
              value={selectedBroker}
              onChange={setSelectedBroker}
              label="Broker"
            />
          )}
        </div>
        <div className="h-px bg-[#D1D9E6]" />
      </div>

      {/* ── Period selector ── */}
      <PeriodSelector value={period} onChange={setPeriod} />

      {/* ── KPI Cards — 2 cols mobile → 4 cols lg ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          title="UF en Pipeline"
          value={isLoading ? '—' : formatUF(metrics?.uf_en_pipeline ?? 0)}
          subtitle="deals activos"
          icon={TrendingUp}
          variant="dark"
        />
        <KPICard
          title="UF Cerradas"
          value={isLoading ? '—' : formatUF(metrics?.uf_cerradas ?? 0)}
          subtitle="escrituras firmadas"
          icon={Wallet}
          variant="light"
        />
        <KPICard
          title="Deals Activos"
          value={isLoading ? '—' : metrics?.total_active_deals ?? 0}
          subtitle="sin cancelados"
          icon={Handshake}
          variant="light"
        />
        <KPICard
          title="Aprobación Banco"
          value={isLoading ? '—' : `${metrics?.bank_approval_rate ?? 0}%`}
          subtitle="tasa de aprobación"
          icon={BadgeCheck}
          variant="light"
        />
      </div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DealsByStageChart
          dealsByStage={metrics?.deals_by_stage ?? {}}
          isLoading={isLoading}
        />
        <DealUFTrendChart
          data={metrics?.uf_trend ?? []}
          isLoading={isLoading}
        />
      </div>
    </div>
  )
}
