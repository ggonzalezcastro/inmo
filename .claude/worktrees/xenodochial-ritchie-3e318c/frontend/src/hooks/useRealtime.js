import { useEffect, useRef } from 'react';
import api from '../services/api';

/**
 * useRealtime - Custom hook for real-time updates via polling
 *
 * Features:
 * - Polls API endpoints for updates
 * - Updates stores automatically
 * - Configurable interval
 */
export function useRealtime(config) {
  const {
    endpoint,
    interval = 5000,
    onUpdate,
    enabled = true,
  } = config;

  const intervalRef = useRef(null);
  const lastUpdateRef = useRef(null);
  // Keep a stable ref to the latest onUpdate so the effect never goes stale
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => { onUpdateRef.current = onUpdate; });

  useEffect(() => {
    if (!enabled || !endpoint) return;

    const poll = async () => {
      try {
        const response = await api.get(endpoint, {
          params: lastUpdateRef.current ? { since: lastUpdateRef.current } : {},
        });
        lastUpdateRef.current = new Date().toISOString();
        onUpdateRef.current?.(response.data);
      } catch (error) {
        if (error.response?.status !== 404) {
          console.error('Error polling for updates:', error);
        }
      }
    };

    poll();
    intervalRef.current = setInterval(poll, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [endpoint, interval, enabled]); // onUpdate intentionally omitted — use ref above

  return {
    stop: () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    },
    start: () => {
      if (!intervalRef.current && enabled && endpoint) {
        const poll = async () => {
          try {
            const response = await api.get(endpoint);
            onUpdate?.(response.data);
          } catch (error) {
            if (error.response?.status !== 404) {
              console.error('Error polling for updates:', error);
            }
          }
        };
        poll();
        intervalRef.current = setInterval(poll, interval);
      }
    },
  };
}

/**
 * useTicketRealtime - Hook specifically for ticket updates
 */
export function useTicketRealtime(leadId, onUpdate) {
  return useRealtime({
    endpoint: leadId ? `/api/v1/tickets/${leadId}/updates` : null,
    interval: 5000,
    onUpdate,
    enabled: !!leadId,
  });
}

/**
 * usePipelineRealtime - Hook specifically for pipeline updates
 */
export function usePipelineRealtime(onUpdate) {
  return useRealtime({
    endpoint: '/api/v1/pipeline/updates',
    interval: 10000, // 10 seconds for pipeline
    onUpdate,
    enabled: true,
  });
}

