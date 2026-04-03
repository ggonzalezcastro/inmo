import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import type { AuditLogEntry } from '../types/auditLog.types'

interface Props {
  entry: AuditLogEntry | null
  onClose: () => void
}

export function AuditLogDetailDialog({ entry, onClose }: Props) {
  if (!entry) return null

  return (
    <Dialog open={!!entry} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl max-h-[70vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {entry.action} · {entry.resource_type}:{entry.resource_id}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="flex gap-6 text-xs text-slate-500">
            {entry.user_email && <span>Usuario: <strong>{entry.user_email}</strong></span>}
            {entry.broker_id && <span>Broker ID: <strong>{entry.broker_id}</strong></span>}
            {entry.ip_address && <span>IP: <code>{entry.ip_address}</code></span>}
          </div>
          {entry.changes && Object.keys(entry.changes).length > 0 ? (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Cambios</p>
              <pre className="bg-slate-50 text-slate-700 rounded-lg p-3 text-xs overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(entry.changes, null, 2)}
              </pre>
            </div>
          ) : (
            <p className="text-xs text-slate-400">Sin cambios registrados</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
