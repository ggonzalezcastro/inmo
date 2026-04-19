import React from 'react';

/**
 * Previous/Next pagination controls.
 * @param {number} page - Current page (1-based)
 * @param {number} totalPages - Total pages
 * @param {function} onPageChange - (newPage) => void
 * @param {string} className - Wrapper div classes
 */
export function Pagination({ page, totalPages, onPageChange, className = '' }) {
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={!hasPrev}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Anterior
      </button>
      <span className="text-sm text-gray-600">
        Página {page} de {totalPages || 1}
      </span>
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={!hasNext}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Siguiente
      </button>
    </div>
  );
}

export default Pagination;
