import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { WeeklyTrendPoint } from '../services/dashboard.service'

interface WeeklyTrendChartProps {
  data: WeeklyTrendPoint[]
  isLoading: boolean
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#D1D9E6] rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-[#111827]">{label}</p>
      <p className="text-[#1A56DB]">{payload[0]?.value} leads</p>
    </div>
  )
}

export function WeeklyTrendChart({ data, isLoading }: WeeklyTrendChartProps) {
  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">Leads por semana</span>
        <span className="text-[#9CA3AF] text-[12px]">Últimas 8 semanas</span>
      </div>

      <div className="p-4 flex-1">
        {isLoading ? (
          <div className="h-[200px] flex items-center justify-center">
            <div className="h-full w-full bg-[#F0F4F8] animate-pulse rounded-lg" />
          </div>
        ) : data.length === 0 ? (
          <div className="h-[200px] flex items-center justify-center text-[13px] text-[#9CA3AF]">
            Sin datos disponibles
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F4F8" vertical={false} />
              <XAxis
                dataKey="week"
                tick={{ fontSize: 11, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#1A56DB"
                strokeWidth={2}
                dot={{ fill: '#1A56DB', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
