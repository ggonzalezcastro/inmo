import {
  BadgeCheck,
  CalendarDays,
  CircleDollarSign,
  Handshake,
  ReceiptText,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { KPICard } from '@/features/dashboard/components/KPICard'
import type { DealMetrics } from '../services/dealsApi'

interface SalesKPIGridProps {
  metrics: DealMetrics | null
  isLoading: boolean
}

function formatUF(value: number) {
  return `${value.toLocaleString('es-CL', {
    minimumFractionDigits: 0,
    maximumFractionDigits: value < 1000 ? 1 : 0,
  })} UF`
}

function comparisonSubtitle(
  delta: number | null | undefined,
  previous: number | undefined,
) {
  if (delta == null) {
    return previous === 0 ? 'sin ventas en período anterior' : 'sin base de comparación'
  }
  const direction = delta > 0 ? 'más' : delta < 0 ? 'menos' : 'igual'
  return `${Math.abs(delta).toLocaleString('es-CL')}% ${direction} que antes`
}

export function SalesKPIGrid({ metrics, isLoading }: SalesKPIGridProps) {
  const value = (content: string | number) => (isLoading ? '—' : content)

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 2xl:grid-cols-8 gap-3">
      <KPICard
        title="UF en pipeline"
        value={value(formatUF(metrics?.uf_en_pipeline ?? 0))}
        subtitle="negocios aún abiertos"
        icon={TrendingUp}
        variant="dark"
      />
      <KPICard
        title="UF cerradas"
        value={value(formatUF(metrics?.uf_cerradas ?? 0))}
        subtitle="en el período elegido"
        icon={Wallet}
        variant="light"
      />
      <KPICard
        title="Ventas cerradas"
        value={value(metrics?.deals_closed ?? 0)}
        subtitle="escrituras firmadas"
        icon={CircleDollarSign}
        variant="light"
      />
      <KPICard
        title="Negocios activos"
        value={value(metrics?.total_active_deals ?? 0)}
        subtitle="sin cerrados ni cancelados"
        icon={Handshake}
        variant="light"
      />
      <KPICard
        title="Ventas semanales"
        value={value(metrics?.sales_this_week.sales ?? 0)}
        subtitle={comparisonSubtitle(
          metrics?.sales_this_week.sales_delta_percent,
          metrics?.sales_this_week.previous_sales,
        )}
        icon={CalendarDays}
        variant="light"
      />
      <KPICard
        title="Ventas mensuales"
        value={value(metrics?.sales_this_month.sales ?? 0)}
        subtitle={comparisonSubtitle(
          metrics?.sales_this_month.sales_delta_percent,
          metrics?.sales_this_month.previous_sales,
        )}
        icon={CalendarDays}
        variant="light"
      />
      <KPICard
        title="Ticket promedio"
        value={value(formatUF(metrics?.avg_ticket_uf ?? 0))}
        subtitle="promedio por cierre"
        icon={ReceiptText}
        variant="light"
      />
      <KPICard
        title="Aprobación banco"
        value={value(`${metrics?.bank_approval_rate ?? 0}%`)}
        subtitle="revisiones aprobadas"
        icon={BadgeCheck}
        variant="light"
      />
    </div>
  )
}
