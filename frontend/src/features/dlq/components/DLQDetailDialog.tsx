import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import type { DLQEntry } from '../types/dlq.types'

interface Props {
  entry: DLQEntry | null
  onClose: () => void
}

export function DLQDetailDialog({ entry, onClose }: Props) {
  if (!entry) return null

  return (
    <Dialog open={!!entry} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{entry.task_name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Error</p>
            <pre className="bg-red-50 text-red-800 rounded-lg p-3 text-xs overflow-x-auto whitespace-pre-wrap">
              {entry.exception}
            </pre>
          </div>

          {entry.traceback && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Traceback</p>
              <pre className="bg-slate-50 text-slate-700 rounded-lg p-3 text-xs overflow-x-auto whitespace-pre-wrap">
                {entry.traceback}
              </pre>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Args</p>
              <pre className="bg-slate-50 text-slate-700 rounded-lg p-3 text-xs overflow-x-auto">
                {JSON.stringify(entry.args, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Kwargs</p>
              <pre className="bg-slate-50 text-slate-700 rounded-lg p-3 text-xs overflow-x-auto">
                {JSON.stringify(entry.kwargs, null, 2)}
              </pre>
            </div>
          </div>

          <div className="flex gap-4 text-xs text-slate-500">
            <span>Reintentos: <strong>{entry.retries}</strong></span>
            <span>ID: <code className="bg-slate-100 px-1 rounded">{entry.id}</code></span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
