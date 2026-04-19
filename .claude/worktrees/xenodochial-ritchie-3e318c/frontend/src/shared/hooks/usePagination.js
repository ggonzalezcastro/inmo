import { useState, useCallback } from 'react';

/**
 * Hook for pagination state (page, pageSize).
 * @param {number} initialPage - Default 1
 * @param {number} initialPageSize - Default 10
 * @returns {[number, number, function, function, number]} [page, pageSize, setPage, setPageSize, offset]
 */
export function usePagination(initialPage = 1, initialPageSize = 10) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const offset = (page - 1) * pageSize;

  const goToPage = useCallback((p) => setPage(Math.max(1, p)), []);
  const nextPage = useCallback(() => setPage((p) => p + 1), []);
  const prevPage = useCallback(() => setPage((p) => Math.max(1, p - 1)), []);

  return {
    page,
    pageSize,
    setPage: goToPage,
    setPageSize,
    offset,
    nextPage,
    prevPage,
  };
}

export default usePagination;
