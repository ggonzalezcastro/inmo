import { create } from 'zustand';
import { pipelineAPI, leadsAPI } from '../services/api';

// Pipeline stages as defined in the requirements
export const PIPELINE_STAGES = [
  { id: 'entrada', label: 'Entrada', color: 'bg-gray-100' },
  { id: 'perfilamiento', label: 'Perfilamiento', color: 'bg-blue-100' },
  { id: 'calificacion_financiera', label: 'Calificación', color: 'bg-yellow-100' },
  { id: 'agendado', label: 'Agendado', color: 'bg-purple-100' },
  { id: 'seguimiento', label: 'Seguimiento', color: 'bg-green-100' },
  { id: 'ganado', label: 'Ganado', color: 'bg-emerald-100' },
  { id: 'perdido', label: 'Perdido', color: 'bg-red-100' },
];

export const usePipelineStore = create((set, get) => ({
  // Leads organized by stage
  leadsByStage: {},
  loading: false,
  error: null,
  
  // Filters
  filters: {
    assignedTo: null,
    campaign: null,
    dateFrom: null,
    dateTo: null,
    search: '',
  },
  
  // Metrics
  metrics: null,
  
  // Fetch leads for a specific stage
  fetchLeadsByStage: async (stage, filters = {}) => {
    set({ loading: true, error: null });
    try {
      const currentFilters = { ...get().filters, ...filters };
      const response = await pipelineAPI.getLeadsByStage(stage, currentFilters);
      
      set((state) => ({
        leadsByStage: {
          ...state.leadsByStage,
          [stage]: response.data.data || [],
        },
        loading: false,
      }));
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message, 
        loading: false 
      });
    }
  },
  
  // Fetch all stages at once
  fetchAllStages: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const currentFilters = { ...get().filters, ...filters };
      
      // Fetch leads for each stage in parallel
      const promises = PIPELINE_STAGES.map(stage => 
        pipelineAPI.getLeadsByStage(stage.id, currentFilters)
      );
      
      const responses = await Promise.all(promises);
      const leadsByStage = {};
      
      PIPELINE_STAGES.forEach((stage, index) => {
        leadsByStage[stage.id] = responses[index].data.data || [];
      });
      
      set({ leadsByStage, loading: false });
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message, 
        loading: false 
      });
    }
  },
  
  // Move lead to a new stage
  moveLeadToStage: async (leadId, newStage, reason = '') => {
    try {
      // Optimistic update
      const currentLeadsByStage = { ...get().leadsByStage };
      let leadToMove = null;
      let oldStage = null;
      
      // Find and remove lead from current stage
      for (const [stage, leads] of Object.entries(currentLeadsByStage)) {
        const leadIndex = leads.findIndex(l => l.id === leadId);
        if (leadIndex !== -1) {
          leadToMove = leads[leadIndex];
          oldStage = stage;
          currentLeadsByStage[stage] = leads.filter(l => l.id !== leadId);
          break;
        }
      }
      
      if (!leadToMove) {
        throw new Error('Lead not found');
      }
      
      // Add to new stage
      if (!currentLeadsByStage[newStage]) {
        currentLeadsByStage[newStage] = [];
      }
      currentLeadsByStage[newStage] = [
        ...currentLeadsByStage[newStage],
        { ...leadToMove, pipeline_stage: newStage }
      ];
      
      set({ leadsByStage: currentLeadsByStage });
      
      // API call
      await pipelineAPI.moveLeadToStage(leadId, newStage, reason);
      
      return true;
    } catch (error) {
      // Revert optimistic update on error
      await get().fetchAllStages();
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return false;
    }
  },
  
  // Get pipeline metrics
  getLeadMetrics: async () => {
    try {
      const response = await pipelineAPI.getStageMetrics();
      set({ metrics: response.data });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Set filters
  setFilters: (filters) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
    }));
  },
  
  // Clear filters
  clearFilters: () => {
    set({
      filters: {
        assignedTo: null,
        campaign: null,
        dateFrom: null,
        dateTo: null,
        search: '',
      },
    });
  },
}));

