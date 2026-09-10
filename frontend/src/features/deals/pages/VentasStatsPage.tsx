import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { BrokerFilterBar, type SelectedBroker } from '@/shared/components/filters/BrokerFilterBar'
import { getErrorMessage } from '@/shared/types/api'
import { dealsApi, type DealMetrics } from '../services/dealsApi'
import { DealsByStageChart } from '../components/DealsByStageChart'
import { DealUFTrendChart } from '../components/DealUFTrendChart'
import { SalesInsightsPanel } from '../components/SalesInsightsPanel'
import { SalesKPIGrid } from '../components/SalesKPIGrid'
import { PeriodSelector, type DateRange } from '../components/PeriodSelector'

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

      <SalesKPIGrid metrics={metrics} isLoading={isLoading} />

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DealsByStageChart
          dealsByStage={metrics?.deals_by_stage ?? {}}
          isLoading={isLoading}
        />
        <DealUFTrendChart
          data={metrics?.uf_trend ?? []}
          monthlyData={metrics?.monthly_trend ?? []}
          isLoading={isLoading}
        />
      </div>

      <SalesInsightsPanel metrics={metrics} isLoading={isLoading} />
    </div>
  )
}
