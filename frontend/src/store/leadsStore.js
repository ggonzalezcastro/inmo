import { create } from 'zustand';
import { leadsAPI } from '../services/api';


export const useLeadsStore = create((set, get) => ({
  leads: [],
  total: 0,
  loading: false,
  error: null,
  filters: {
    search: '',
    status: '',
    minScore: 0,
    maxScore: 100,
  },
  pagination: {
    skip: 0,
    limit: 50,
  },
  
  fetchLeads: async () => {
    set({ loading: true, error: null });
    try {
      const { filters, pagination } = get();
      
      const response = await leadsAPI.getAll({
        search: filters.search,
        status: filters.status,
        min_score: filters.minScore,
        max_score: filters.maxScore,
        skip: pagination.skip,
        limit: pagination.limit,
      });
      
      set({
        leads: response.data.data,
        total: response.data.total,
        loading: false,
      });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },
  
  createLead: async (lead_data) => {
    try {
      await leadsAPI.create(lead_data);
      await get().fetchLeads();
      return true;
    } catch (error) {
      set({ error: error.message });
      return false;
    }
  },
  
  updateLead: async (id, lead_data) => {
    try {
      await leadsAPI.update(id, lead_data);
      await get().fetchLeads();
      return true;
    } catch (error) {
      set({ error: error.message });
      return false;
    }
  },
  
  deleteLead: async (id) => {
    try {
      await leadsAPI.delete(id);
      await get().fetchLeads();
      return true;
    } catch (error) {
      set({ error: error.message });
      return false;
    }
  },
  
  setFilters: (filters) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
      pagination: { ...state.pagination, skip: 0 },
    }));
  },
  
  setPagination: (pagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...pagination },
    }));
  },
}));

