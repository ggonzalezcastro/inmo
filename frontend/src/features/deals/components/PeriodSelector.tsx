import { useState } from 'react'
import { cn } from '@/shared/lib/utils'

export interface DateRange {
  date_from: string
  date_to: string
}

type Preset = 'month' | 'quarter' | 'year' | 'custom'

interface PeriodSelectorProps {
  value: DateRange
  onChange: (range: DateRange) => void
}

function toISO(d: Date) {
  return d.toISOString().slice(0, 10)
}

function presetToRange(preset: Preset): DateRange {
  const today = new Date()
  const to = toISO(today)
  if (preset === 'month') {
    const from = new Date(today)
    from.setMonth(from.getMonth() - 1)
    return { date_from: toISO(from), date_to: to }
  }
  if (preset === 'quarter') {
    const from = new Date(today)
    from.setMonth(from.getMonth() - 3)
    return { date_from: toISO(from), date_to: to }
  }
  if (preset === 'year') {
    const from = new Date(today)
    from.setFullYear(from.getFullYear() - 1)
    return { date_from: toISO(from), date_to: to }
  }
  return { date_from: '', date_to: '' }
}

const PRESETS: { key: Preset; label: string }[] = [
  { key: 'month', label: 'Último mes' },
  { key: 'quarter', label: 'Trimestre' },
  { key: 'year', label: 'Año' },
  { key: 'custom', label: 'Personalizado' },
]

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  const [active, setActive] = useState<Preset>('month')

  function handlePreset(preset: Preset) {
    setActive(preset)
    if (preset !== 'custom') {
      onChange(presetToRange(preset))
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1 bg-white border border-[#D1D9E6] rounded-lg p-1">
        {PRESETS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handlePreset(key)}
            className={cn(
              'px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors',
              active === key
                ? 'bg-[#1A56DB] text-white shadow-sm'
                : 'text-[#6B7280] hover:text-[#374151] hover:bg-[#F5F8FF]'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {active === 'custom' && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={value.date_from}
            onChange={(e) => onChange({ ...value, date_from: e.target.value })}
            className="text-[12px] border border-[#D1D9E6] rounded-lg px-3 py-2 text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1A56DB]/30"
          />
          <span className="text-[#9CA3AF] text-[12px]">—</span>
          <input
            type="date"
            value={value.date_to}
            onChange={(e) => onChange({ ...value, date_to: e.target.value })}
            className="text-[12px] border border-[#D1D9E6] rounded-lg px-3 py-2 text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1A56DB]/30"
          />
        </div>
      )}
    </div>
  )
}
