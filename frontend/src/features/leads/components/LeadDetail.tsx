import { useState, useRef } from 'react'
import { RefreshCw, X, Loader2, MessageSquare, Plus, Tag, Phone } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Separator } from '@/shared/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
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
import { useVapiCall, StartCallDialog, ActiveCallOverlay } from '@/features/voice'
import type { CallMode, CallPurpose } from '@/features/voice'

interface LeadDetailProps {
  lead: Lead
  onClose: () => void
  onUpdate: (lead: Lead) => void
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start py-2 gap-4">
      <span className="text-sm text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium text-right break-words">{value ?? '—'}</span>
    </div>
  )
}

function DicomBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    clean: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    has_debt: 'bg-rose-50 text-rose-600 border-rose-200',
    unknown: 'bg-slate-100 text-slate-600 border-slate-200',
  }
  const cfg = DICOM_CONFIG[status as keyof typeof DICOM_CONFIG]
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${styles[status] ?? styles.unknown}`}>
      {cfg?.label ?? status}
    </span>
  )
}

export function LeadDetail({ lead, onClose, onUpdate }: LeadDetailProps) {
  const navigate = useNavigate()
  const [isRecalculating, setIsRecalculating] = useState(false)
  const [tags, setTags] = useState<string[]>(lead.tags ?? [])
  const [tagInput, setTagInput] = useState('')
  const [isSavingTags, setIsSavingTags] = useState(false)
  const [showStartCall, setShowStartCall] = useState(false)
  const tagInputRef = useRef<HTMLInputElement>(null)
  const { isAdmin } = usePermissions()
  const meta = lead.lead_metadata ?? {}
  const calificacion = meta.calificacion
  const dicomStatus = meta.dicom_status

  const { callState, transcript, isMuted, startCall, endCall, toggleMute } =
    useVapiCall({ leadId: lead.id })

  const handleStartCall = async (mode: CallMode, purpose: CallPurpose) => {
    setShowStartCall(false)
    await startCall(mode, purpose)
  }

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

  const addTag = async () => {
    const newTag = tagInput.trim().toLowerCase()
    if (!newTag || tags.includes(newTag)) {
      setTagInput('')
      return
    }
    const nextTags = [...tags, newTag]
    setTags(nextTags)
    setTagInput('')
    setIsSavingTags(true)
    try {
      const updated = await leadsService.updateLead(lead.id, { tags: nextTags })
      onUpdate({ ...lead, ...updated, tags: nextTags })
    } catch (error) {
      setTags(tags) // revert
      toast.error(getErrorMessage(error))
    } finally {
      setIsSavingTags(false)
    }
  }

  const removeTag = async (tag: string) => {
    const nextTags = tags.filter((t) => t !== tag)
    setTags(nextTags)
    setIsSavingTags(true)
    try {
      const updated = await leadsService.updateLead(lead.id, { tags: nextTags })
      onUpdate({ ...lead, ...updated, tags: nextTags })
    } catch (error) {
      setTags(tags) // revert
      toast.error(getErrorMessage(error))
    } finally {
      setIsSavingTags(false)
    }
  }

  return (
    <div className="w-80 border-l border-border bg-white flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground truncate">{lead.name}</h3>
          <p className="text-xs text-muted-foreground">{lead.phone}</p>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={onClose} aria-label="Cerrar detalle">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Badges */}
      <div className="px-4 pt-3 pb-1 flex items-center gap-1.5 flex-wrap">
        <ScoreBadge score={lead.lead_score} />
        <StatusBadge status={lead.status} />
        <PipelineStageBadge stage={lead.pipeline_stage} />
        {calificacion && <QualificationBadge calificacion={calificacion} />}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="datos" className="flex-1 flex flex-col overflow-hidden">
        <TabsList className="mx-4 mt-2 h-8 text-xs grid grid-cols-3">
          <TabsTrigger value="datos" className="text-xs">Datos</TabsTrigger>
          <TabsTrigger value="perfil" className="text-xs">Perfil</TabsTrigger>
          {isAdmin && <TabsTrigger value="financiero" className="text-xs">Financiero</TabsTrigger>}
          {!isAdmin && <TabsTrigger value="tags" className="text-xs">Tags</TabsTrigger>}
        </TabsList>

        {/* Tab: Datos personales */}
        <TabsContent value="datos" className="flex-1 overflow-y-auto px-4 pb-4 mt-0">
          <div className="divide-y divide-border">
            <DetailRow label="Teléfono" value={<a href={`tel:${lead.phone}`} className="text-blue-600 hover:underline">{lead.phone}</a>} />
            <DetailRow label="Email" value={lead.email ? <a href={`mailto:${lead.email}`} className="text-blue-600 hover:underline truncate block max-w-[140px]">{lead.email}</a> : null} />
            <DetailRow label="Creado" value={formatDate(lead.created_at)} />
            <DetailRow label="Último contacto" value={formatDate(lead.last_contacted)} />
            {lead.response_metrics && lead.response_metrics.reply_count > 0 && (
              <DetailRow
                label="Velocidad de respuesta"
                value={
                  <span className={lead.response_metrics.is_fast_responder ? 'text-amber-600 font-medium' : ''}>
                    {lead.response_metrics.avg_response_seconds != null
                      ? `${Math.round(lead.response_metrics.avg_response_seconds)}s prom.`
                      : '—'}
                    {' '}
                    <span className="text-muted-foreground">
                      ({lead.response_metrics.reply_count} resp.)
                    </span>
                    {lead.response_metrics.is_fast_responder && ' ⚡'}
                  </span>
                }
              />
            )}
          </div>

          {/* Tags section */}
          <Separator className="my-3" />
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase mb-2 flex items-center gap-1">
              <Tag className="h-3 w-3" /> Tags
            </p>
            <div className="flex flex-wrap gap-1 mb-2">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground"
                >
                  {tag}
                  {isAdmin && (
                    <button
                      onClick={() => removeTag(tag)}
                      disabled={isSavingTags}
                      className="hover:text-destructive transition-colors"
                      aria-label={`Eliminar tag ${tag}`}
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  )}
                </span>
              ))}
              {tags.length === 0 && <span className="text-xs text-muted-foreground">Sin tags</span>}
            </div>
            {isAdmin && (
              <div className="flex gap-1">
                <Input
                  ref={tagInputRef}
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder="Nuevo tag…"
                  className="h-7 text-xs flex-1"
                  onKeyDown={(e) => e.key === 'Enter' && addTag()}
                />
                <Button
                  size="icon"
                  variant="outline"
                  className="h-7 w-7 shrink-0"
                  onClick={addTag}
                  disabled={isSavingTags || !tagInput.trim()}
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Tab: Perfil inmobiliario */}
        <TabsContent value="perfil" className="flex-1 overflow-y-auto px-4 pb-4 mt-0">
          <div className="divide-y divide-border">
            <DetailRow label="Presupuesto" value={meta.budget} />
            <DetailRow label="Ubicación" value={meta.location} />
            <DetailRow label="Tipo inmueble" value={meta.property_type} />
            <DetailRow label="Habitaciones" value={meta.rooms} />
            <DetailRow label="Plazo" value={meta.timeline} />
            <DetailRow label="Propósito" value={
              meta.purpose === 'vivienda' ? 'Vivienda propia' :
              meta.purpose === 'inversion' ? 'Inversión' : meta.purpose
            } />
            <DetailRow label="Residencia" value={
              meta.residency_status === 'residente' ? 'Residente' :
              meta.residency_status === 'extranjero' ? 'Extranjero' : meta.residency_status
            } />
          </div>
        </TabsContent>

        {/* Tab: Financiero (admin only) */}
        {isAdmin && (
          <TabsContent value="financiero" className="flex-1 overflow-y-auto px-4 pb-4 mt-0">
            <div className="divide-y divide-border">
              <DetailRow
                label="Renta mensual"
                value={meta.monthly_income ? formatCurrency(Number(meta.monthly_income)) : null}
              />
              <DetailRow
                label="DICOM"
                value={dicomStatus ? <DicomBadge status={dicomStatus} /> : null}
              />
              {meta.morosidad_amount && (
                <DetailRow
                  label="Monto morosidad"
                  value={<span className="text-rose-600">{formatCurrency(Number(meta.morosidad_amount))}</span>}
                />
              )}
            </div>
          </TabsContent>
        )}

        {/* Tab: Tags (agents — since they don't have financiero tab) */}
        {!isAdmin && (
          <TabsContent value="tags" className="flex-1 overflow-y-auto px-4 pb-4 mt-0">
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground">
                  {tag}
                </span>
              ))}
              {tags.length === 0 && <span className="text-xs text-muted-foreground">Sin tags</span>}
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* Footer actions */}
      <div className="p-4 border-t border-border space-y-2">
        {lead.phone && (
          <Button
            size="sm"
            className="w-full bg-green-600 hover:bg-green-700 text-white"
            onClick={() => setShowStartCall(true)}
            disabled={callState === 'starting' || callState === 'active' || callState === 'ending'}
          >
            {callState === 'starting' ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Phone className="mr-2 h-4 w-4" />
            )}
            {callState === 'active' ? 'En llamada' : callState === 'starting' ? 'Conectando…' : 'Llamar'}
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => navigate('/chat')}
        >
          <MessageSquare className="mr-2 h-4 w-4" />
          Ver chat
        </Button>
        {isAdmin && (
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
        )}
      </div>

      {/* Start call dialog */}
      <StartCallDialog
        open={showStartCall}
        leadName={lead.name}
        leadPhone={lead.phone ?? ''}
        loading={callState === 'starting'}
        onCancel={() => setShowStartCall(false)}
        onConfirm={handleStartCall}
      />

      {/* Active call overlay (floating) */}
      <ActiveCallOverlay
        callState={callState}
        leadName={lead.name}
        leadPhone={lead.phone ?? ''}
        transcript={transcript}
        isMuted={isMuted}
        onMuteToggle={toggleMute}
        onEndCall={endCall}
      />
    </div>
  )
}
