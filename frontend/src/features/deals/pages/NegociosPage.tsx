import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { dealsApi } from '../services/dealsApi'
import { getErrorMessage } from '@/shared/types/api'
import type { Deal, DealStage } from '../types'

const STAGE_LABELS: Record<DealStage, string> = {
  draft: 'Borrador',
  reserva: 'Reserva',
  docs_pendientes: 'Docs. pendientes',
  en_aprobacion_bancaria: 'Aprobación bancaria',
  promesa_redaccion: 'Promesa (redacción)',
  promesa_firmada: 'Promesa firmada',
  escritura_firmada: 'Escritura firmada',
  cancelado: 'Cancelado',
}

const STAGE_BADGE: Record<DealStage, string> = {
  draft: 'bg-gray-100 text-gray-600 border-gray-200',
  reserva: 'bg-blue-100 text-blue-700 border-blue-200',
  docs_pendientes: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  en_aprobacion_bancaria: 'bg-orange-100 text-orange-700 border-orange-200',
  promesa_redaccion: 'bg-purple-100 text-purple-700 border-purple-200',
  promesa_firmada: 'bg-purple-100 text-purple-700 border-purple-200',
  escritura_firmada: 'bg-green-100 text-green-700 border-green-200',
  cancelado: 'bg-red-100 text-red-600 border-red-200',
}

const STAGE_ORDER: DealStage[] = [
  'draft', 'reserva', 'docs_pendientes', 'en_aprobacion_bancaria',
  'promesa_redaccion', 'promesa_firmada', 'escritura_firmada', 'cancelado',
]

const ACTIVE_STAGES: DealStage[] = STAGE_ORDER.filter(
  (s) => s !== 'cancelado' && s !== 'escritura_firmada',
)

export function NegociosPage() {
  const navigate = useNavigate()
  const [deals, setDeals] = useState<Deal[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [stageFilter, setStageFilter] = useState<DealStage | 'all'>('all')

  useEffect(() => {
    setIsLoading(true)
    dealsApi
      .list({ limit: 200 })
      .then(setDeals)
      .catch((e) => toast.error(getErrorMessage(e)))
      .finally(() => setIsLoading(false))
  }, [])

  const filtered = stageFilter === 'all' ? deals : deals.filter((d) => d.stage === stageFilter)
  const activeCount = deals.filter((d) => ACTIVE_STAGES.includes(d.stage)).length

  return (
    <div className="p-4 sm:p-8 overflow-y-auto h-full">
      <PageHeader
        title="Negocios"
        description={`${activeCount} activos · ${deals.length} en total`}
      />

      {/* Stage filter pills */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          onClick={() => setStageFilter('all')}
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
            stageFilter === 'all'
              ? 'bg-slate-800 text-white border-slate-800'
              : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
          }`}
        >
          Todos ({deals.length})
        </button>
        {STAGE_ORDER.map((s) => {
          const count = deals.filter((d) => d.stage === s).length
          if (count === 0) return null
          return (
            <button
              key={s}
              onClick={() => setStageFilter(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                stageFilter === s
                  ? 'bg-slate-800 text-white border-slate-800'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              {STAGE_LABELS[s]} ({count})
            </button>
          )
        })}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 mr-2 animate-spin" /> Cargando negocios…
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-dashed rounded-lg p-12 text-center text-sm text-muted-foreground">
          No hay negocios{stageFilter !== 'all' ? ` en etapa "${STAGE_LABELS[stageFilter as DealStage]}"` : ''}.
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground bg-slate-50 border-b">
              <tr>
                <th className="text-left font-medium px-4 py-3">#</th>
                <th className="text-left font-medium px-4 py-3">Etapa</th>
                <th className="text-left font-medium px-4 py-3">Negocio</th>
                <th className="text-left font-medium px-4 py-3">Entrega</th>
                <th className="text-left font-medium px-4 py-3">Creado</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((deal) => (
                <tr
                  key={deal.id}
                  className="border-b last:border-b-0 hover:bg-slate-50 cursor-pointer"
                  onClick={() => navigate(`/negocios/${deal.id}`)}
                >
                  <td className="px-4 py-3 font-medium text-slate-400 text-xs">#{deal.id}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className={`text-[11px] font-semibold ${STAGE_BADGE[deal.stage]}`}>
                      {STAGE_LABELS[deal.stage]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-700 font-medium">
                    {deal.lead_name && deal.property_label
                      ? `${deal.lead_name} — ${deal.property_label}`
                      : deal.lead_name
                      ? `${deal.lead_name} — Prop. #${deal.property_id}`
                      : `Lead #${deal.lead_id}`}
                  </td>
                  <td className="px-4 py-3 text-slate-500 capitalize text-xs">{deal.delivery_type}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">
                    {new Date(deal.created_at).toLocaleDateString('es-CL')}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={(e) => { e.stopPropagation(); navigate(`/negocios/${deal.id}`) }}
                      title="Ver lead"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
