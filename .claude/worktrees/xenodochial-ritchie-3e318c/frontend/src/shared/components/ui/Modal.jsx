import React, { useEffect } from 'react';

/**
 * Base modal component. Use for dialogs and overlays.
 * @param {boolean} isOpen - Whether the modal is visible
 * @param {function} onClose - Callback when modal should close (e.g. backdrop click)
 * @param {React.ReactNode} children - Modal content
 * @param {string} title - Optional title
 * @param {string} className - Additional classes for the modal panel
 */
export function Modal({ isOpen, onClose, children, title, className = '' }) {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      <div
        className={`bg-white rounded-lg shadow-xl max-h-[90vh] overflow-auto ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between p-4 border-b">
            <h2 id="modal-title" className="text-lg font-semibold">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 p-1"
              aria-label="Cerrar"
            >
              <span className="text-xl">&times;</span>
            </button>
          </div>
        )}
        <div className={title ? 'p-4' : 'p-4'}>{children}</div>
      </div>
    </div>
  );
}

export default Modal;
