import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/shared/lib/api-client';

interface DocumentPreviewModalProps {
  /** Authenticated URL — e.g. /api/deals/:id/documents/:docId/download */
  url: string;
  filename?: string;
  onClose: () => void;
}

export function DocumentPreviewModal({ url, filename, onClose }: DocumentPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    apiClient
      .fetchBlob(url)
      .then(({ blob, contentType: ct }) => {
        objectUrl = URL.createObjectURL(blob);
        setContentType(ct);
        setBlobUrl(objectUrl);
      })
      .catch(() => setError('No se pudo cargar el documento.'));

    // Lock body scroll while modal is open
    document.body.style.overflow = 'hidden';

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      document.body.style.overflow = '';
    };
  }, [url]);

  const handleKey = useCallback(
    (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); },
    [onClose],
  );
  useEffect(() => {
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  const isImage = contentType.startsWith('image/');
  const isPdf = contentType.includes('pdf');

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex flex-col bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-slate-50 shrink-0">
          <span className="text-sm font-medium text-slate-700 truncate max-w-[85%]">
            {filename ?? 'Documento'}
          </span>
          <div className="flex items-center gap-2">
            {blobUrl && (
              <a
                href={blobUrl}
                download={filename ?? 'documento'}
                className="inline-flex items-center gap-1 text-xs text-[#1A56DB] hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Descargar
              </a>
            )}
            <button
              onClick={onClose}
              className="rounded-md p-1 text-slate-500 hover:bg-slate-200"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto min-h-0 flex items-center justify-center bg-slate-100">
          {error && (
            <p className="text-sm text-red-600 p-8">{error}</p>
          )}
          {!blobUrl && !error && (
            <div className="flex flex-col items-center gap-3 p-8">
              <svg className="h-8 w-8 animate-spin text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span className="text-sm text-slate-500">Cargando...</span>
            </div>
          )}
          {blobUrl && isImage && (
            <img
              src={blobUrl}
              alt={filename}
              className="max-w-full max-h-full object-contain p-4"
            />
          )}
          {blobUrl && isPdf && (
            <embed
              src={blobUrl}
              type="application/pdf"
              className="w-full min-h-[75vh]"
              style={{ height: '75vh' }}
            />
          )}
          {blobUrl && !isImage && !isPdf && (
            <div className="flex flex-col items-center gap-4 p-8">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <p className="text-sm text-slate-600">No se puede previsualizar este tipo de archivo.</p>
              <a
                href={blobUrl}
                download={filename ?? 'documento'}
                className="text-sm text-[#1A56DB] hover:underline font-medium"
              >
                Descargar archivo
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
