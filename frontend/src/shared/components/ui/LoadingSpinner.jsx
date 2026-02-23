import React from 'react';

/**
 * Simple loading spinner. Optional message.
 * @param {string} message - Text below spinner (e.g. "Cargando...")
 * @param {string} className - Wrapper div classes
 */
export function LoadingSpinner({ message = 'Cargando...', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 p-4 ${className}`}>
      <div
        className="w-8 h-8 border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin"
        role="status"
        aria-label="Cargando"
      />
      {message && <p className="text-sm text-gray-500">{message}</p>}
    </div>
  );
}

export default LoadingSpinner;
