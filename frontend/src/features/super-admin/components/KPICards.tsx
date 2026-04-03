import { Building2, Users, MessageSquare, DollarSign, Activity } from 'lucide-react'
import type { DashboardKPIs } from '../types/superAdmin.types'

interface Props {
  kpis: DashboardKPIs
}

export function KPICards({ kpis }: Props) {
  const cards = [
    {
      label: 'Brokers Activos',
      value: kpis.active_brokers.toString(),
      icon: Building2,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Leads Totales',
      value: kpis.total_leads.toLocaleString(),
      icon: Users,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
    },
    {
      label: 'Mensajes Hoy',
      value: kpis.messages_today.toLocaleString(),
      icon: MessageSquare,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      label: 'Costo Mensual',
      value: `$${kpis.cost_this_month_usd.toFixed(2)}`,
      icon: DollarSign,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
    },
    {
      label: 'Sistema',
      value: kpis.health_status === 'healthy' ? 'Saludable' : 'Degradado',
      icon: Activity,
      color: kpis.health_status === 'healthy' ? 'text-green-600' : 'text-red-600',
      bg: kpis.health_status === 'healthy' ? 'bg-green-50' : 'bg-red-50',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-2">
          <div className={`w-8 h-8 rounded-lg ${card.bg} flex items-center justify-center`}>
            <card.icon size={16} className={card.color} />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{card.value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{card.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
