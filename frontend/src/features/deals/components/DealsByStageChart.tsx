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

const DEAL_STAGE_COLORS: Record<string, string> = {
  draft: '#9CA3AF',
  reserva: '#1A56DB',
  docs_pendientes: '#F59E0B',
  en_aprobacion_bancaria: '#F97316',
  promesa_redaccion: '#8B5CF6',
  promesa_firmada: '#3B82F6',
  escritura_firmada: '#059669',
  cancelado: '#F87171',
}

const DEAL_STAGE_LABELS: Record<string, string> = {
  draft: 'Borrador',
  reserva: 'Reserva',
  docs_pendientes: 'Docs.',
  en_aprobacion_bancaria: 'Banco',
  promesa_redaccion: 'Promesa',
  promesa_firmada: 'P. Firmada',
  escritura_firmada: 'Escritura',
  cancelado: 'Cancelado',
}

const DEAL_STAGE_FULL: Record<string, string> = {
  draft: 'Borrador',
  reserva: 'Reserva',
  docs_pendientes: 'Docs. Pendientes',
  en_aprobacion_bancaria: 'En Aprobación Bancaria',
  promesa_redaccion: 'Promesa en Redacción',
  promesa_firmada: 'Promesa Firmada',
  escritura_firmada: 'Escritura Firmada',
  cancelado: 'Cancelado',
}

const STAGE_ORDER = [
  'draft',
  'reserva',
  'docs_pendientes',
  'en_aprobacion_bancaria',
  'promesa_redaccion',
  'promesa_firmada',
  'escritura_firmada',
  'cancelado',
]

interface DealsByStageChartProps {
  dealsByStage: Record<string, number>
  isLoading: boolean
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#D1D9E6] rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-[#111827]">{payload[0]?.payload?.fullName}</p>
      <p style={{ color: payload[0]?.fill }}>{payload[0]?.value} deal{payload[0]?.value !== 1 ? 's' : ''}</p>
    </div>
  )
}

export function DealsByStageChart({ dealsByStage, isLoading }: DealsByStageChartProps) {
  const data = STAGE_ORDER.map((s) => ({
    name: DEAL_STAGE_LABELS[s] ?? s,
    fullName: DEAL_STAGE_FULL[s] ?? s,
    count: dealsByStage[s] ?? 0,
    color: DEAL_STAGE_COLORS[s] ?? '#C4CDD8',
  }))

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">Deals por etapa</span>
        <span className="text-[#9CA3AF] text-[12px]">Distribución actual</span>
      </div>

      <div className="p-4 flex-1">
        {isLoading ? (
          <div className="h-[220px] bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F4F8" horizontal={true} vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 9, fill: '#9CA3AF' }}
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
