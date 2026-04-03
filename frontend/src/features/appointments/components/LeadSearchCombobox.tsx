import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, User } from 'lucide-react'
import { apiClient } from '@/shared/lib/api-client'

interface LeadOption {
  id: number
  name: string
  phone: string
  email?: string
}

interface PaginatedLeads {
  data: LeadOption[]
  total: number
}

interface LeadSearchComboboxProps {
  value: LeadOption | null
  onChange: (lead: LeadOption | null) => void
  placeholder?: string
}

export function LeadSearchCombobox({
  value,
  onChange,
  placeholder = 'Buscar lead por nombre o teléfono…',
}: LeadSearchComboboxProps) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<LeadOption[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setOptions([])
      return
    }
    setLoading(true)
    try {
      const response = await apiClient.get<PaginatedLeads | LeadOption[]>(
        '/api/v1/leads',
        { params: { search: q, limit: 10, skip: 0 } }
      )
      const list = Array.isArray(response) ? response : response.data
      setOptions(list)
    } catch {
      setOptions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      void search(query)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, search])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = (lead: LeadOption) => {
    onChange(lead)
    setQuery('')
    setIsOpen(false)
  }

  const handleClear = () => {
    onChange(null)
    setQuery('')
  }

  // If a lead is selected, show it as a chip
  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
        <User className="h-4 w-4 text-slate-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="font-medium text-slate-800 text-sm">{value.name}</span>
          <span className="text-xs text-slate-400 ml-2">#{value.id}</span>
          {value.phone && (
            <span className="text-xs text-slate-500 ml-2">{value.phone}</span>
          )}
        </div>
        <button
          type="button"
          onClick={handleClear}
          className="text-slate-400 hover:text-slate-600 shrink-0"
          aria-label="Quitar lead seleccionado"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center rounded-md border border-slate-200 bg-white px-3 py-2 focus-within:ring-2 focus-within:ring-slate-400 focus-within:ring-offset-0">
        <Search className="h-4 w-4 text-slate-400 mr-2 shrink-0" />
        <input
          type="text"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          onFocus={() => {
            if (query) setIsOpen(true)
          }}
        />
        {loading && (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600 shrink-0" />
        )}
      </div>

      {isOpen && (query.length > 0) && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg max-h-56 overflow-y-auto">
          {options.length === 0 && !loading && (
            <div className="px-3 py-2 text-sm text-slate-500">
              {query.length < 2 ? 'Escribe al menos 2 caracteres…' : 'Sin resultados'}
            </div>
          )}
          {options.map((lead) => (
            <button
              key={lead.id}
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 transition-colors"
              onMouseDown={(e) => e.preventDefault()} // prevent blur before click
              onClick={() => handleSelect(lead)}
            >
              <User className="h-4 w-4 text-slate-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-slate-800">{lead.name}</span>
                <span className="text-xs text-slate-400 ml-1.5">#{lead.id}</span>
              </div>
              {lead.phone && (
                <span className="text-xs text-slate-500 shrink-0">{lead.phone}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
