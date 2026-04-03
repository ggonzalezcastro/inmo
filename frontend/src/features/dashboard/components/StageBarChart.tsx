import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { PIPELINE_STAGES } from '@/shared/lib/constants'

const STAGE_COLORS: Record<string, string> = {
  entrada: '#9CA3AF',
  perfilamiento: '#1A56DB',
  calificacion_financiera: '#F59E0B',
  potencial: '#F97316',
  agendado: '#8B5CF6',
  ganado: '#059669',
  perdido: '#F87171',
}

const STAGE_LABELS: Record<string, string> = {
  entrada: 'Entrada',
  perfilamiento: 'Perfil',
  calificacion_financiera: 'Cal. Fin.',
  potencial: 'Potencial',
  agendado: 'Agendado',
  ganado: 'Ganado',
  perdido: 'Perdido',
}

interface StageBarChartProps {
  stageCounts: Record<string, number>
  isLoading: boolean
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#D1D9E6] rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-[#111827]">{payload[0]?.payload?.fullName}</p>
      <p style={{ color: payload[0]?.fill }}>{payload[0]?.value} leads</p>
    </div>
  )
}

export function StageBarChart({ stageCounts, isLoading }: StageBarChartProps) {
  const data = PIPELINE_STAGES.map((s) => ({
    name: STAGE_LABELS[s.key] ?? s.key,
    fullName: s.label,
    count: stageCounts[s.key] ?? 0,
    color: STAGE_COLORS[s.key] ?? '#C4CDD8',
  }))

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">Leads por etapa</span>
        <span className="text-[#9CA3AF] text-[12px]">Distribución actual</span>
      </div>

      <div className="p-4 flex-1">
        {isLoading ? (
          <div className="h-[200px] bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F4F8" horizontal={true} vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 10, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F8FF' }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={32}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
