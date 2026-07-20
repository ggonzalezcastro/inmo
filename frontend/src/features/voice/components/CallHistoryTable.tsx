/**
 * CallHistoryTable — paginated broker-scoped call history for the Llamadas page.
 * Data from GET /api/v1/calls. Row click opens a transcript dialog.
 */
import { useState } from 'react'
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { pipecatService } from '../services/pipecat.service'
import type { CallListItem, CallDetails } from '../services/pipecat.service'
import { CALL_PURPOSE_LABELS } from '../types'
import type { CallPurpose } from '../types'

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  completed: { label: 'Completada', className: 'bg-green-100 text-green-800' },
  answered: { label: 'Contestada', className: 'bg-green-100 text-green-800' },
  initiated: { label: 'Iniciada', className: 'bg-blue-100 text-blue-800' },
  ringing: { label: 'Llamando', className: 'bg-blue-100 text-blue-800' },
  failed: { label: 'Fallida', className: 'bg-red-100 text-red-800' },
  no_answer: { label: 'Sin respuesta', className: 'bg-amber-100 text-amber-800' },
  busy: { label: 'Ocupado', className: 'bg-amber-100 text-amber-800' },
  cancelled: { label: 'Cancelada', className: 'bg-slate-100 text-slate-600' },
}

const MODE_LABELS: Record<string, string> = {
  autonomous: 'Autónomo',
  copilot: 'Copilot',
  handoff: 'Handoff',
  coaching: 'Coaching',
  ai_agent: 'Agente IA',
  transcriptor: 'Transcriptor',
}

const SPEAKER_LABEL: Record<string, string> = {
  customer: 'Lead',
  bot: 'IA',
  agent: 'Agente',
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function CallHistoryTable({
  items,
  total,
  page,
  pageSize,
  loading,
  onPageChange,
}: {
  items: CallListItem[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  onPageChange: (page: number) => void
}) {
  const [details, setDetails] = useState<CallDetails | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [loadingDetails, setLoadingDetails] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const openDetails = async (callId: number) => {
    setDetailsOpen(true)
    setLoadingDetails(true)
    setDetails(null)
    try {
      const data = await pipecatService.getCallDetails(callId)
      setDetails(data)
    } catch {
      // dialog shows fallback text
    } finally {
      setLoadingDetails(false)
    }
  }

  return (
    <div className="rounded-xl border bg-card">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
          Historial de llamadas
        </p>
        <span className="text-xs text-muted-foreground">{total} llamadas</span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Cargando…
        </div>
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-8">Sin llamadas todavía</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="text-left font-medium px-4 py-2">Lead</th>
                <th className="text-left font-medium px-4 py-2">Motivo</th>
                <th className="text-left font-medium px-4 py-2">Modo</th>
                <th className="text-left font-medium px-4 py-2">Estado</th>
                <th className="text-left font-medium px-4 py-2">Duración</th>
                <th className="text-left font-medium px-4 py-2">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {items.map((call) => {
                const status = STATUS_LABELS[call.status] ?? {
                  label: call.status,
                  className: 'bg-slate-100 text-slate-600',
                }
                const mode = call.pipecat_mode ?? call.call_mode
                return (
                  <tr
                    key={call.id}
                    className="border-b last:border-0 hover:bg-muted/40 cursor-pointer"
                    onClick={() => openDetails(call.id)}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-medium">{call.lead_name ?? `Lead #${call.lead_id}`}</span>
                      {(call.lead_phone ?? call.phone_number) && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {call.lead_phone ?? call.phone_number}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {call.call_purpose
                        ? CALL_PURPOSE_LABELS[call.call_purpose as CallPurpose] ?? call.call_purpose
                        : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-xs">{mode ? MODE_LABELS[mode] ?? mode : '—'}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant="outline" className={`text-xs border-0 ${status.className}`}>
                        {status.label}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-xs">{formatDuration(call.duration)}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {new Date(call.created_at).toLocaleString('es-CL', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 px-4 py-2.5 border-t">
          <span className="text-xs text-muted-foreground">
            Página {page} de {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-7 p-0"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-7 p-0"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Details dialog */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm">
              Detalle de llamada{details ? ` #${details.call.id}` : ''}
            </DialogTitle>
          </DialogHeader>
          {loadingDetails ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Cargando…
            </div>
          ) : !details ? (
            <p className="text-xs text-muted-foreground py-4">No se pudo cargar el detalle.</p>
          ) : (
            <div className="space-y-3">
              {details.call.summary && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Resumen</p>
                  <p className="text-sm">{String(details.call.summary)}</p>
                </div>
              )}
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">
                  Transcripción ({details.transcript_lines.length} líneas)
                </p>
                <div className="max-h-64 overflow-y-auto rounded-lg border bg-muted/30 px-3 py-2 space-y-1.5">
                  {details.transcript_lines.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Sin transcripción</p>
                  ) : (
                    details.transcript_lines.map((line, i) => (
                      <div key={i} className="text-xs">
                        <span className="font-semibold">
                          {SPEAKER_LABEL[line.speaker] ?? line.speaker}:
                        </span>{' '}
                        {line.text}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
