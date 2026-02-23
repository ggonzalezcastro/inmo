import React from 'react';
import { Modal } from './Modal';

/**
 * Modal with form layout: title, form content, and footer with cancel/submit.
 * @param {boolean} isOpen
 * @param {function} onClose
 * @param {string} title
 * @param {React.ReactNode} children - Form fields
 * @param {function} onSubmit - Form submit handler
 * @param {string} submitLabel - Submit button label
 * @param {string} cancelLabel - Cancel button label
 * @param {boolean} loading - Disable submit and show loading state
 * @param {string} className
 */
export function FormModal({
  isOpen,
  onClose,
  title,
  children,
  onSubmit,
  submitLabel = 'Guardar',
  cancelLabel = 'Cancelar',
  loading = false,
  className = '',
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit?.(e);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} className={className}>
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">{children}</div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
          >
            {cancelLabel}
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Guardando...' : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default FormModal;
