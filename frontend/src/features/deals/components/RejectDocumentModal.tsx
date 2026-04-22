import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';

export interface RejectDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (notes: string) => void;
  docLabel: string;
}

export function RejectDocumentModal({
  isOpen,
  onClose,
  onConfirm,
  docLabel,
}: RejectDocumentModalProps) {
  const [notes, setNotes] = useState('');

  const handleConfirm = () => {
    if (!notes.trim()) return;
    onConfirm(notes.trim());
    setNotes('');
  };

  const handleClose = () => {
    setNotes('');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="text-rose-600">Rechazar documento</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <p className="text-sm text-muted-foreground">
            Indica el motivo del rechazo para{' '}
            <strong className="text-foreground">{docLabel}</strong>.
          </p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Describe el motivo del rechazo..."
            rows={4}
            className="w-full text-sm rounded-lg border border-border px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-rose-500 focus:border-rose-500 placeholder:text-muted-foreground"
          />
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={handleClose}>
            Cancelar
          </Button>
          <Button
            size="sm"
            disabled={!notes.trim()}
            onClick={handleConfirm}
            className="bg-rose-600 hover:bg-rose-700 text-white"
          >
            Rechazar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
