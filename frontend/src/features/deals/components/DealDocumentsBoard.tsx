import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import type { DealDetail, DealDocument, SlotRequirement } from '../types';
import { useDealsStore } from '../store/dealsStore';
import { RejectDocumentModal } from './RejectDocumentModal';
import { DocumentPreviewModal } from './DocumentPreviewModal';

const MAX_SIZE_BYTES = 15 * 1024 * 1024; // 15 MB
const ACCEPTED_MIME = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/webp': ['.webp'],
};

export interface DealDocumentsBoardProps {
  deal: DealDetail;
  canEdit: boolean;
}

// ── Slot Drop Zone ──────────────────────────────────────────────────────────

interface SlotDropZoneProps {
  dealId: number;
  slotKey: string;
  disabled?: boolean;
}

function SlotDropZone({ dealId, slotKey, disabled }: SlotDropZoneProps) {
  const uploadDocument = useDealsStore((s) => s.uploadDocument);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (accepted: File[], rejected: { file: File; errors: { message: string }[] }[]) => {
      if (rejected.length > 0) {
        const msg = rejected[0].errors[0]?.message ?? 'Archivo no válido';
        setError(msg);
        return;
      }
      if (accepted.length === 0) return;
      setError(null);
      setUploading(true);
      try {
        await uploadDocument(dealId, slotKey, accepted[0]);
      } catch {
        setError('Error al subir el archivo. Intenta de nuevo.');
      } finally {
        setUploading(false);
      }
    },
    [dealId, slotKey, uploadDocument],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_MIME,
    maxSize: MAX_SIZE_BYTES,
    maxFiles: 1,
    disabled: disabled || uploading,
  });

  return (
    <div className="mt-2">
      <div
        {...getRootProps()}
        className={`flex items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-3 text-sm transition-colors cursor-pointer
          ${disabled || uploading ? 'cursor-not-allowed opacity-50 border-border' : ''}
          ${isDragActive ? 'border-[#1A56DB] bg-[#EBF2FF] text-[#1A56DB]' : 'border-border hover:border-[#1A56DB]/50 hover:bg-[#F8FAFC] text-muted-foreground'}
        `}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#1A56DB] border-t-transparent" />
            <span>Subiendo…</span>
          </>
        ) : isDragActive ? (
          <span>Suelta el archivo aquí</span>
        ) : (
          <span>PDF, PNG, JPG, WEBP · máx 15 MB — arrastra o haz clic</span>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

// ── Document Row ────────────────────────────────────────────────────────────

interface DocumentRowProps {
  doc: DealDocument;
  slotLabel: string;
  dealId: number;
  slotKey: string;
  canEdit: boolean;
}

function DocumentRow({ doc, slotLabel, dealId, slotKey, canEdit }: DocumentRowProps) {
  const approveDocument = useDealsStore((s) => s.approveDocument);
  const rejectDocument = useDealsStore((s) => s.rejectDocument);
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [actioning, setActioning] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  const handleApprove = async () => {
    setActioning(true);
    try {
      await approveDocument(dealId, doc.id);
    } finally {
      setActioning(false);
      setConfirmApprove(false);
    }
  };

  const handleReject = async (notes: string) => {
    setActioning(true);
    try {
      await rejectDocument(dealId, doc.id, notes);
    } finally {
      setActioning(false);
      setRejectOpen(false);
    }
  };

  const statusBadge = () => {
    switch (doc.status) {
      case 'aprobado':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            ✓ Aprobado
          </span>
        );
      case 'rechazado':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">
            ✗ Rechazado
          </span>
        );
      case 'recibido':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
            Recibido — pendiente revisión
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="mt-2 rounded-lg border border-border bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {statusBadge()}
          {doc.uploaded_by_ai && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              🤖 Subido por IA — requiere revisión
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {doc.download_url && (
            <button
              onClick={() => setPreviewOpen(true)}
              className="inline-flex items-center justify-center rounded p-1 text-slate-500 hover:text-[#1A56DB] hover:bg-slate-100"
              title="Ver documento"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          )}
          {canEdit && doc.status === 'recibido' && (
            <>
              {confirmApprove ? (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground">¿Confirmar?</span>
                  <button
                    disabled={actioning}
                    onClick={handleApprove}
                    className="text-xs font-medium text-emerald-700 hover:underline disabled:opacity-50"
                  >
                    Sí
                  </button>
                  <button
                    onClick={() => setConfirmApprove(false)}
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    No
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmApprove(true)}
                  className="text-xs font-medium text-emerald-700 hover:underline"
                >
                  Aprobar
                </button>
              )}
              <button
                onClick={() => setRejectOpen(true)}
                className="text-xs font-medium text-rose-600 hover:underline"
              >
                Rechazar
              </button>
            </>
          )}
        </div>
      </div>

      {doc.original_filename && (
        <p className="text-xs text-muted-foreground truncate">{doc.original_filename}</p>
      )}

      {doc.status === 'rechazado' && doc.review_notes && (
        <p className="text-xs text-rose-600 italic">Motivo: {doc.review_notes}</p>
      )}

      {doc.status === 'rechazado' && canEdit && (
        <SlotDropZone dealId={dealId} slotKey={slotKey} />
      )}

      <RejectDocumentModal
        isOpen={rejectOpen}
        onClose={() => setRejectOpen(false)}
        onConfirm={handleReject}
        docLabel={slotLabel}
      />

      {previewOpen && (
        <DocumentPreviewModal
          url={`/api/deals/${dealId}/documents/${doc.id}/download`}
          filename={doc.original_filename ?? slotLabel}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </div>
  );
}

// ── Slot Card ───────────────────────────────────────────────────────────────

interface SlotCardProps {
  slot: SlotRequirement;
  docs: DealDocument[];
  dealId: number;
  canEdit: boolean;
}

function SlotCard({ slot, docs, dealId, canEdit }: SlotCardProps) {
  const slotDocs = docs.filter((d) => d.slot === slot.slot_key);
  const hasUploadedDocs = slotDocs.length > 0;
  const allApproved = slotDocs.length > 0 && slotDocs.every((d) => d.status === 'aprobado');

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 bg-white shadow-sm transition-colors
        ${allApproved ? 'border-emerald-300' : 'border-border'}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground leading-tight">{slot.label}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Requerido para etapa: <span className="font-medium">{slot.required_for_stage}</span>
          </p>
        </div>
        <span
          className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
            slot.required
              ? 'bg-rose-100 text-rose-700'
              : 'bg-slate-100 text-slate-600'
          }`}
        >
          {slot.required ? 'Requerido' : 'Opcional'}
        </span>
      </div>

      {/* Documents or placeholder */}
      {!hasUploadedDocs ? (
        <div className="rounded-lg bg-slate-50 border border-dashed border-slate-200 px-3 py-2">
          <p className="text-xs text-muted-foreground">Sin documento</p>
        </div>
      ) : (
        slotDocs.map((doc) => (
          <DocumentRow
            key={doc.id}
            doc={doc}
            slotLabel={slot.label}
            dealId={dealId}
            slotKey={slot.slot_key}
            canEdit={canEdit}
          />
        ))
      )}

      {/* Drop zone for new uploads (when canEdit and slot not fully approved) */}
      {canEdit && !allApproved && (
        <SlotDropZone dealId={dealId} slotKey={slot.slot_key} />
      )}
    </div>
  );
}

// ── Board ───────────────────────────────────────────────────────────────────

export function DealDocumentsBoard({ deal, canEdit }: DealDocumentsBoardProps) {
  if (!deal.required_slots || deal.required_slots.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center">
        <p className="text-sm text-muted-foreground">No hay documentos requeridos para este deal.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {deal.required_slots.map((slot) => (
        <SlotCard
          key={slot.slot_key}
          slot={slot}
          docs={deal.documents}
          dealId={deal.id}
          canEdit={canEdit}
        />
      ))}
    </div>
  );
}
