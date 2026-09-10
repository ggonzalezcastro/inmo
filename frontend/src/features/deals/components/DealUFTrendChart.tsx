import { useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DealMetrics } from '../services/dealsApi'

interface DealUFTrendChartProps {
  data: DealMetrics['uf_trend']
  monthlyData: DealMetrics['monthly_trend']
  isLoading: boolean
}

interface ChartPoint {
  label: string
  sales: number
  uf: number
  clp: number
}

function formatUF(value: number) {
  return `${value.toLocaleString('es-CL', { maximumFractionDigits: 0 })} UF`
}

function formatCLP(value: number) {
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0,
  }).format(value)
}

function SalesTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload

  return (
    <div className="bg-white border border-[#D1D9E6] rounded-lg shadow-md px-3 py-2.5 text-xs min-w-36">
      <p className="font-semibold text-[#111827] mb-1.5">{label}</p>
      <p className="text-[#1A56DB] font-medium">{point?.sales ?? 0} ventas</p>
      <p className="text-[#059669] mt-0.5">{formatUF(point?.uf ?? 0)}</p>
      {(point?.clp ?? 0) > 0 && (
        <p className="text-[#6B7280] mt-0.5">{formatCLP(point.clp)}</p>
      )}
    </div>
  )
}

export function DealUFTrendChart({ data, monthlyData, isLoading }: DealUFTrendChartProps) {
  const [mode, setMode] = useState<'weekly' | 'monthly'>('weekly')
  const chartData: ChartPoint[] = mode === 'weekly'
    ? data.map((point) => ({ label: point.week, sales: point.sales, uf: point.uf, clp: point.clp }))
    : monthlyData.map((point) => ({ label: point.month, sales: point.sales, uf: point.uf, clp: point.clp }))

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-[#E8EEF6]">
        <div>
          <h2 className="text-[#111827] text-[14px] font-bold">Evolución de ventas</h2>
          <p className="text-[#9CA3AF] text-[12px] mt-0.5">Cierres y UF escrituradas</p>
        </div>
        <div className="inline-flex p-0.5 rounded-lg bg-[#F0F4F8]" aria-label="Agrupación de ventas">
          {(['weekly', 'monthly'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={mode === option}
              onClick={() => setMode(option)}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition-colors ${
                mode === option
                  ? 'bg-white text-[#1A56DB] shadow-sm'
                  : 'text-[#6B7280] hover:text-[#374151]'
              }`}
            >
              {option === 'weekly' ? 'Semanal' : 'Mensual'}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4 flex-1">
        {isLoading ? (
          <div className="h-[240px] bg-[#F0F4F8] animate-pulse rounded-lg" />
        ) : chartData.length === 0 ? (
          <div className="h-[240px] flex items-center justify-center text-[13px] text-[#9CA3AF]">
            Sin ventas cerradas en el período
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F4F8" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="sales"
                tick={{ fontSize: 10, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
                width={25}
              />
              <YAxis
                yAxisId="uf"
                orientation="right"
                tick={{ fontSize: 10, fill: '#059669' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => value >= 1000 ? `${(value / 1000).toFixed(0)}k` : value}
                width={35}
              />
              <Tooltip content={<SalesTooltip />} />
              <Bar
                yAxisId="sales"
                dataKey="sales"
                fill="#BFD2FA"
                radius={[4, 4, 0, 0]}
                maxBarSize={30}
              />
              <Line
                yAxisId="uf"
                type="monotone"
                dataKey="uf"
                stroke="#059669"
                strokeWidth={2.5}
                dot={{ fill: '#059669', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
        {!isLoading && chartData.length > 0 && (
          <div className="flex items-center justify-center gap-5 mt-2 text-[11px] text-[#6B7280]">
            <span className="flex items-center gap-1.5"><i className="w-2.5 h-2.5 rounded-sm bg-[#BFD2FA]" />Ventas</span>
            <span className="flex items-center gap-1.5"><i className="w-4 h-0.5 rounded bg-[#059669]" />UF cerradas</span>
          </div>
        )}
      </div>
    </div>
  )
}
