import { useState, useCallback } from 'react';

/**
 * Hook for filter state (e.g. search, status, date range).
 * @param {Object} initialFilters - { filterKey: value }
 * @returns {[Object, function, function]} [filters, setFilter, resetFilters]
 */
export function useFilters(initialFilters = {}) {
  const [filters, setFilters] = useState(initialFilters);

  const setFilter = useCallback((key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  return { filters, setFilters, setFilter, resetFilters };
}

export default useFilters;
