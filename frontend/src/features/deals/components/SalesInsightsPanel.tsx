import {
  CalendarCheck2,
  CircleX,
  Clock3,
  FileSignature,
  Landmark,
} from 'lucide-react'
import type { DealMetrics } from '../services/dealsApi'

interface SalesInsightsPanelProps {
  metrics: DealMetrics | null
  isLoading: boolean
}

function formatUF(value: number) {
  return `${value.toLocaleString('es-CL', { maximumFractionDigits: 0 })} UF`
}

function formatCLP(value: number) {
  if (!value) return '$0'
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0,
  }).format(value)
}

const insightItems = [
  { key: 'reservations_period', label: 'Reservas', icon: CalendarCheck2, tone: 'text-[#1A56DB] bg-[#EBF2FF]' },
  { key: 'promises_signed_period', label: 'Promesas firmadas', icon: FileSignature, tone: 'text-[#7C3AED] bg-[#F3E8FF]' },
  { key: 'cancellations_period', label: 'Cancelaciones', icon: CircleX, tone: 'text-[#DC2626] bg-[#FEF2F2]' },
] as const

export function SalesInsightsPanel({ metrics, isLoading }: SalesInsightsPanelProps) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <section className="xl:col-span-2 bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E8EEF6]">
          <h2 className="text-[14px] font-bold text-[#111827]">Avance comercial del período</h2>
          <p className="text-[12px] text-[#9CA3AF] mt-0.5">Hitos registrados en los negocios</p>
        </div>

        {isLoading ? (
          <div className="m-5 h-36 bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-px bg-[#E8EEF6]">
            {insightItems.map(({ key, label, icon: Icon, tone }) => (
              <div key={key} className="bg-white p-5 min-h-28">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tone}`}>
                  <Icon size={16} />
                </div>
                <div className="text-2xl font-bold text-[#111827] mt-3 tabular-nums">
                  {metrics?.[key] ?? 0}
                </div>
                <div className="text-[12px] text-[#6B7280] mt-1">{label}</div>
              </div>
            ))}

            <div className="bg-white p-5 min-h-28">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[#D97706] bg-[#FFFBEB]">
                <CircleX size={16} />
              </div>
              <div className="text-2xl font-bold text-[#111827] mt-3 tabular-nums">
                {metrics?.cancellation_rate ?? 0}%
              </div>
              <div className="text-[12px] text-[#6B7280] mt-1">Tasa de cancelación</div>
              <div className="text-[10px] text-[#9CA3AF] mt-0.5">De cierres y cancelaciones</div>
            </div>

            <div className="bg-white p-5 min-h-28">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[#059669] bg-[#ECFDF5]">
                <Clock3 size={16} />
              </div>
              <div className="text-2xl font-bold text-[#111827] mt-3 tabular-nums">
                {metrics?.avg_sales_cycle_days == null ? '—' : `${metrics.avg_sales_cycle_days} d`}
              </div>
              <div className="text-[12px] text-[#6B7280] mt-1">Ingreso a escritura</div>
            </div>

            <div className="bg-white p-5 min-h-28">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[#0891B2] bg-[#ECFEFF]">
                <Landmark size={16} />
              </div>
              <div className="text-[17px] font-bold text-[#111827] mt-3 tabular-nums truncate" title={formatCLP(metrics?.clp_cerradas ?? 0)}>
                {formatCLP(metrics?.clp_cerradas ?? 0)}
              </div>
              <div className="text-[12px] text-[#6B7280] mt-1">Ventas cerradas en pesos</div>
            </div>
          </div>
        )}
      </section>

      <section className="bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E8EEF6]">
          <h2 className="text-[14px] font-bold text-[#111827]">Ventas por proyecto</h2>
          <p className="text-[12px] text-[#9CA3AF] mt-0.5">Proyectos con más cierres</p>
        </div>

        {isLoading ? (
          <div className="m-5 h-36 bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : !metrics?.sales_by_project.length ? (
          <div className="h-44 flex items-center justify-center px-5 text-center text-[13px] text-[#9CA3AF]">
            Sin ventas por proyecto en el período
          </div>
        ) : (
          <div className="divide-y divide-[#E8EEF6]">
            {metrics.sales_by_project.map((project, index) => (
              <div key={project.project_id ?? 'none'} className="px-5 py-3.5 flex items-center gap-3">
                <span className="w-6 h-6 shrink-0 rounded-md bg-[#F0F4F8] text-[#6B7280] text-[11px] font-bold flex items-center justify-center">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-[#111827] truncate">{project.project_name}</p>
                  <p className="text-[11px] text-[#9CA3AF] mt-0.5">{formatUF(project.uf)}</p>
                </div>
                <span className="text-[12px] font-bold text-[#1A56DB] tabular-nums">
                  {project.sales} {project.sales === 1 ? 'venta' : 'ventas'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
