/**
 * Centralized API error handling.
 * @param {Error} error - Axios or fetch error
 * @returns {string} User-friendly error message
 */
export function handleApiError(error) {
  if (!error) return 'Error desconocido';
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (first?.msg) return first.msg;
    if (typeof first === 'string') return first;
  }
  if (detail?.message) return detail.message;
  if (error.message) return error.message;
  return 'Error desconocido. Intenta de nuevo.';
}

export default handleApiError;
