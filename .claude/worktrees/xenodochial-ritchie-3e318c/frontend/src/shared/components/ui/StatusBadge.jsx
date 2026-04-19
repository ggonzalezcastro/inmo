import React from 'react';

const STATUS_STYLES = {
  cold: 'bg-gray-100 text-gray-800',
  warm: 'bg-yellow-100 text-yellow-800',
  hot: 'bg-red-100 text-red-800',
  CALIFICADO: 'bg-green-100 text-green-800',
  POTENCIAL: 'bg-yellow-100 text-yellow-800',
  NO_CALIFICADO: 'bg-gray-100 text-gray-600',
  active: 'bg-green-100 text-green-800',
  paused: 'bg-yellow-100 text-yellow-800',
  draft: 'bg-gray-100 text-gray-600',
};

const STATUS_LABELS = {
  cold: 'Frío',
  warm: 'Tibio',
  hot: 'Caliente',
  CALIFICADO: 'Calificado',
  POTENCIAL: 'Potencial',
  NO_CALIFICADO: 'No calificado',
  active: 'Activa',
  paused: 'Pausada',
  draft: 'Borrador',
};

/**
 * Badge for lead/campaign status. Uses shared colors and labels.
 * @param {string} status - cold | warm | hot | CALIFICADO | POTENCIAL | NO_CALIFICADO | active | paused | draft
 * @param {string} label - Optional override label
 * @param {string} className - Additional classes
 */
export function StatusBadge({ status, label, className = '' }) {
  const style = STATUS_STYLES[status] || 'bg-gray-100 text-gray-800';
  const text = label ?? STATUS_LABELS[status] ?? status;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style} ${className}`}
    >
      {text}
    </span>
  );
}

export default StatusBadge;
export { STATUS_STYLES, STATUS_LABELS };
