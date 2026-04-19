/**
 * Shared constants for leads, campaigns, etc.
 */

export const LEAD_STATUS = {
  COLD: 'cold',
  WARM: 'warm',
  HOT: 'hot',
};

export const LEAD_QUALIFICATION = {
  CALIFICADO: 'CALIFICADO',
  POTENCIAL: 'POTENCIAL',
  NO_CALIFICADO: 'NO_CALIFICADO',
};

export const STATUS_COLORS = {
  cold: 'bg-gray-100 text-gray-800',
  warm: 'bg-yellow-100 text-yellow-800',
  hot: 'bg-red-100 text-red-800',
  CALIFICADO: 'bg-green-100 text-green-800',
  POTENCIAL: 'bg-yellow-100 text-yellow-800',
  NO_CALIFICADO: 'bg-gray-100 text-gray-600',
};

export const CAMPAIGN_STATUS = {
  ACTIVE: 'active',
  PAUSED: 'paused',
  DRAFT: 'draft',
};
