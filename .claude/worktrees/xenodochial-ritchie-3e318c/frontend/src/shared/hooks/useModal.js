import { useState, useCallback } from 'react';

/**
 * Hook for modal open/close state.
 * @returns {[boolean, function, function]} [isOpen, open, close]
 */
export function useModal(initialOpen = false) {
  const [isOpen, setIsOpen] = useState(initialOpen);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  return { isOpen, open, close, toggle, setIsOpen };
}

export default useModal;
