import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { DealMetrics } from '../services/dealsApi'

type UFTrendPoint = DealMetrics['uf_trend'][number]

interface DealUFTrendChartProps {
  data: UFTrendPoint[]
  isLoading: boolean
}

function formatUF(v: number) {
  return v.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' UF'
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#D1D9E6] rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-[#111827]">{label}</p>
      <p className="text-[#059669]">{formatUF(payload[0]?.value ?? 0)}</p>
    </div>
  )
}

export function DealUFTrendChart({ data, isLoading }: DealUFTrendChartProps) {
  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">UF cerradas por semana</span>
        <span className="text-[#9CA3AF] text-[12px]">Escrituras firmadas</span>
      </div>

      <div className="p-4 flex-1">
        {isLoading ? (
          <div className="h-[220px] bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : data.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-[13px] text-[#9CA3AF]">
            Sin datos en el período
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F4F8" vertical={false} />
              <XAxis
                dataKey="week"
                tick={{ fontSize: 11, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                allowDecimals={false}
                width={40}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="uf"
                stroke="#059669"
                strokeWidth={2}
                dot={{ fill: '#059669', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
