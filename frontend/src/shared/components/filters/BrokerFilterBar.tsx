/**
 * BrokerFilterBar — shown only to SUPERADMIN.
 * Renders a compact broker dropdown to filter page data.
 */
import { useEffect, useState } from 'react'
import { Building2, ChevronDown, Globe } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { brokersService, type Broker } from '@/features/brokers/services/brokers.service'

export interface SelectedBroker {
  id: number
  name: string
}

interface BrokerFilterBarProps {
  value: SelectedBroker | null
  onChange: (broker: SelectedBroker | null) => void
  label?: string
}

export function BrokerFilterBar({ value, onChange, label = 'Broker' }: BrokerFilterBarProps) {
  const [brokers, setBrokers] = useState<Broker[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    brokersService.getAll().then(setBrokers).catch(() => setBrokers([]))
  }, [])

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[#D1D9E6] bg-white hover:border-[#1A56DB]/40 transition-colors text-sm"
      >
        <Building2 size={14} className="text-[#1A56DB] shrink-0" />
        <span className="font-medium text-[#374151]">
          {value ? value.name : `Todos los ${label.toLowerCase()}s`}
        </span>
        <ChevronDown size={13} className={cn('text-[#9CA3AF] transition-transform ml-1', open && 'rotate-180')} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full mt-1 z-50 bg-white rounded-xl border border-[#D1D9E6] shadow-lg py-1 min-w-[200px] max-h-64 overflow-y-auto">
            <button
              onClick={() => { onChange(null); setOpen(false) }}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[#F5F8FF] transition-colors',
                !value ? 'text-[#1A56DB] font-semibold' : 'text-[#374151]'
              )}
            >
              <Globe size={13} className="shrink-0" />
              Todos los {label.toLowerCase()}s
            </button>
            <div className="h-px bg-[#E2EAF4] my-1" />
            {brokers.map((b) => (
              <button
                key={b.id}
                onClick={() => { onChange({ id: b.id, name: b.name }); setOpen(false) }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[#F5F8FF] transition-colors text-left',
                  value?.id === b.id ? 'text-[#1A56DB] font-semibold bg-[#EBF2FF]' : 'text-[#374151]'
                )}
              >
                <span className="w-6 h-6 rounded-md bg-[#EBF2FF] flex items-center justify-center shrink-0 text-[10px] font-bold text-[#1A56DB]">
                  {b.name.slice(0, 2).toUpperCase()}
                </span>
                <span className="truncate flex-1">{b.name}</span>
                {!b.is_active && <span className="text-[10px] text-[#9CA3AF]">inactivo</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
