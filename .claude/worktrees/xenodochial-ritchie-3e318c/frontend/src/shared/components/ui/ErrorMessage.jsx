import React from 'react';

/**
 * Consistent error message block (e.g. API or validation errors).
 * @param {string} message - Error text
 * @param {string} className - Wrapper div classes
 */
export function ErrorMessage({ message, className = '' }) {
  if (!message) return null;

  return (
    <div
      className={`bg-red-50 border-l-4 border-red-400 p-4 text-sm text-red-700 ${className}`}
      role="alert"
    >
      {message}
    </div>
  );
}

export default ErrorMessage;
