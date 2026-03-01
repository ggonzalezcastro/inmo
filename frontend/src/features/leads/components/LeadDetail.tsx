import { useState } from 'react'
import { RefreshCw, X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Separator } from '@/shared/components/ui/separator'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import { formatDate, formatCurrency } from '@/shared/lib/utils'
import { DICOM_CONFIG } from '@/shared/lib/constants'
import { leadsService } from '../services/leads.service'
import { getErrorMessage } from '@/shared/types/api'
import { usePermissions } from '@/shared/hooks/usePermissions'
import type { Lead } from '../types'

interface LeadDetailProps {
  lead: Lead
  onClose: () => void
  onUpdate: (lead: Lead) => void
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right">{value ?? '—'}</span>
    </div>
  )
}

export function LeadDetail({ lead, onClose, onUpdate }: LeadDetailProps) {
  const [isRecalculating, setIsRecalculating] = useState(false)
  const { isAdmin } = usePermissions()
  const meta = lead.lead_metadata ?? {}
  const calificacion = meta.calificacion
  const dicomStatus = meta.dicom_status

  const handleRecalculate = async () => {
    setIsRecalculating(true)
    try {
      const result = await leadsService.recalculateScore(lead.id)
      toast.success(`Score actualizado: ${Math.round(result.lead_score)}`)
      onUpdate({ ...lead, lead_score: result.lead_score })
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsRecalculating(false)
    }
  }

  return (
    <div className="w-80 border-l border-border bg-white flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h3 className="font-semibold text-foreground truncate">{lead.name}</h3>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={onClose} aria-label="Cerrar detalle">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Score + Status */}
        <div className="flex items-center gap-2 flex-wrap">
          <ScoreBadge score={lead.lead_score} />
          <StatusBadge status={lead.status} />
          <PipelineStageBadge stage={lead.pipeline_stage} />
          {calificacion && <QualificationBadge calificacion={calificacion} />}
        </div>

        {/* Basic data */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">Datos básicos</p>
          <div className="divide-y divide-border">
            <DetailRow label="Teléfono" value={lead.phone} />
            <DetailRow label="Email" value={lead.email} />
            <DetailRow label="Creado" value={formatDate(lead.created_at)} />
            <DetailRow label="Último contacto" value={formatDate(lead.last_contacted)} />
          </div>
        </div>

        <Separator />

        {/* Metadata — visible solo para admin */}
        {isAdmin && (
          <>
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                Perfil inmobiliario
              </p>
              <div className="divide-y divide-border">
                <DetailRow label="Presupuesto" value={meta.budget} />
                <DetailRow label="Ubicación" value={meta.location} />
                <DetailRow label="Tipo inmueble" value={meta.property_type} />
                <DetailRow label="Habitaciones" value={meta.rooms} />
                <DetailRow label="Timeline" value={meta.timeline} />
                <DetailRow label="Propósito" value={meta.purpose} />
                <DetailRow label="Residencia" value={meta.residency_status} />
              </div>
            </div>

            <Separator />

            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                Datos financieros
              </p>
              <div className="divide-y divide-border">
                <DetailRow
                  label="Renta mensual"
                  value={
                    meta.monthly_income
                      ? formatCurrency(meta.monthly_income)
                      : null
                  }
                />
                <DetailRow
                  label="DICOM"
                  value={
                    dicomStatus ? (
                      <span className={DICOM_CONFIG[dicomStatus]?.className}>
                        {DICOM_CONFIG[dicomStatus]?.label}
                      </span>
                    ) : null
                  }
                />
                {meta.morosidad_amount && (
                  <DetailRow
                    label="Monto morosidad"
                    value={
                      <span className="text-rose-600">
                        {formatCurrency(meta.morosidad_amount)}
                      </span>
                    }
                  />
                )}
              </div>
            </div>
          </>
        )}

        {/* Tags */}
        {lead.tags?.length > 0 && (
          <>
            <Separator />
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">Tags</p>
              <div className="flex flex-wrap gap-1">
                {lead.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Actions */}
      {isAdmin && (
        <div className="p-4 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={handleRecalculate}
            disabled={isRecalculating}
          >
            {isRecalculating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Recalcular score
          </Button>
        </div>
      )}
    </div>
  )
}
