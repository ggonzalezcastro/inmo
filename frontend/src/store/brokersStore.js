import { create } from 'zustand';
import { brokerAPI } from '../services/api';

export const useBrokersStore = create((set, get) => ({
  brokers: [],
  loading: false,
  error: null,

  fetchBrokers: async () => {
    set({ loading: true, error: null });
    try {
      const response = await brokerAPI.getBrokers();
      set({ brokers: response.data?.data ?? response.data ?? [], loading: false });
      return get().brokers;
    } catch (error) {
      set({
        error: error.response?.data?.detail || error.message,
        loading: false,
      });
      return [];
    }
  },

  createBroker: async (data) => {
    set({ error: null });
    try {
      await brokerAPI.createBroker(data);
      await get().fetchBrokers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  updateBroker: async (brokerId, data) => {
    set({ error: null });
    try {
      await brokerAPI.updateBroker(brokerId, data);
      await get().fetchBrokers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  deleteBroker: async (brokerId) => {
    set({ error: null });
    try {
      await brokerAPI.deleteBroker(brokerId);
      await get().fetchBrokers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  clearError: () => set({ error: null }),
}));
