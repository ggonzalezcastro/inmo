import { create } from 'zustand';
import type {
  CostPeriod,
  CostSummary,
  CostDailyResponse,
  CostOutliersResponse,
} from '../types/costs.types';
import * as costsApi from '../services/costsApi';

const PERIOD_KEY = 'llm-costs-period';
const BROKER_KEY = 'llm-costs-broker-id';

function getStoredPeriod(): CostPeriod {
  try {
    const s = localStorage.getItem(PERIOD_KEY);
    if (s === 'today' || s === 'week' || s === 'month' || s === 'quarter') return s;
  } catch {
    // ignore
  }
  return 'month';
}

function getStoredBrokerId(): number | null {
  try {
    const s = localStorage.getItem(BROKER_KEY);
    if (s === null || s === '') return null;
    const n = parseInt(s, 10);
    return Number.isNaN(n) ? null : n;
  } catch {
    return null;
  }
}

export interface CostsState {
  period: CostPeriod;
  selectedBrokerId: number | null;
  summary: CostSummary | null;
  daily: CostDailyResponse | null;
  outliers: CostOutliersResponse | null;
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: number | null;

  setPeriod: (period: CostPeriod) => void;
  setBrokerId: (id: number | null) => void;
  fetchSummary: () => Promise<void>;
  fetchDaily: () => Promise<void>;
  fetchOutliers: () => Promise<void>;
  fetchAll: () => Promise<void>;
  reset: () => void;
}

const initialState = {
  summary: null as CostSummary | null,
  daily: null as CostDailyResponse | null,
  outliers: null as CostOutliersResponse | null,
  isLoading: false,
  error: null as string | null,
  lastFetchedAt: null as number | null,
};

export const useCostsStore = create<CostsState>((set, get) => ({
  period: getStoredPeriod(),
  selectedBrokerId: getStoredBrokerId(),
  ...initialState,

  setPeriod(period) {
    set({ period });
    try {
      localStorage.setItem(PERIOD_KEY, period);
    } catch {
      // ignore
    }
  },

  setBrokerId(id) {
    set({ selectedBrokerId: id });
    try {
      if (id === null) localStorage.removeItem(BROKER_KEY);
      else localStorage.setItem(BROKER_KEY, String(id));
    } catch {
      // ignore
    }
  },

  async fetchSummary() {
    const { period, selectedBrokerId } = get();
    set({ isLoading: true, error: null });
    try {
      const summary = await costsApi.getSummary({
        period,
        broker_id: selectedBrokerId ?? undefined,
      });
      set({ summary, error: null, lastFetchedAt: Date.now() });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Error loading summary';
      set({ error: message, summary: null });
    } finally {
      set({ isLoading: false });
    }
  },

  async fetchDaily() {
    const { period, selectedBrokerId } = get();
    set({ isLoading: true, error: null });
    try {
      const daily = await costsApi.getDaily({
        period,
        broker_id: selectedBrokerId ?? undefined,
      });
      set({ daily, error: null });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Error loading daily';
      set({ error: message, daily: null });
    } finally {
      set({ isLoading: false });
    }
  },

  async fetchOutliers() {
    const { period, selectedBrokerId } = get();
    set({ isLoading: true, error: null });
    try {
      const outliers = await costsApi.getOutliers({
        period,
        broker_id: selectedBrokerId ?? undefined,
        limit: 10,
      });
      set({ outliers, error: null });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Error loading outliers';
      set({ error: message, outliers: null });
    } finally {
      set({ isLoading: false });
    }
  },

  async fetchAll() {
    const { period, selectedBrokerId } = get();
    set({ isLoading: true, error: null });
    const params = { period, broker_id: selectedBrokerId ?? undefined };
    try {
      const [summary, daily, outliers] = await Promise.all([
        costsApi.getSummary(params),
        costsApi.getDaily(params),
        costsApi.getOutliers({ ...params, limit: 10 }),
      ]);
      set({
        summary,
        daily,
        outliers,
        error: null,
        lastFetchedAt: Date.now(),
      });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Error loading costs';
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  reset() {
    set(initialState);
  },
}));
