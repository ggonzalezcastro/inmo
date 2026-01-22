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
      // Clean filters - remove empty values
      const cleanFilters = Object.entries({ ...get().filters, ...filters }).reduce((acc, [key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
          acc[key] = value;
        }
        return acc;
      }, {});
      
      const response = await pipelineAPI.getLeadsByStage(stage, cleanFilters);
      
      set((state) => ({
        leadsByStage: {
          ...state.leadsByStage,
          [stage]: response.data.data || [],
        },
        loading: false,
      }));
    } catch (error) {
      console.error(`Error fetching leads for stage ${stage}:`, error.response?.data || error.message);
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
      // Clean filters - remove empty values
      const currentFilters = Object.entries({ ...get().filters, ...filters }).reduce((acc, [key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
          acc[key] = value;
        }
        return acc;
      }, {});
      
      console.log('🔍 Fetching leads for all stages with filters:', currentFilters);
      
      // Fetch leads for each stage in parallel
      const promises = PIPELINE_STAGES.map(stage => 
        pipelineAPI.getLeadsByStage(stage.id, currentFilters)
          .then(response => {
            console.log(`✅ Stage ${stage.id}:`, response.data);
            return response;
          })
          .catch(err => {
            // If a stage fails, log and return empty array
            console.error(`❌ Error fetching leads for stage ${stage.id}:`, err.response?.data || err.message);
            return { data: { stage: stage.id, data: [], total: 0, skip: 0, limit: 50 } };
          })
      );
      
      const responses = await Promise.all(promises);
      const leadsByStage = {};
      
      PIPELINE_STAGES.forEach((stage, index) => {
        const response = responses[index];
        const responseData = response?.data;
        
        // Backend returns: { stage: string, data: Lead[], total: number, skip: number, limit: number }
        const leads = responseData?.data || [];
        leadsByStage[stage.id] = Array.isArray(leads) ? leads : [];
        
        console.log(`📊 Stage ${stage.id}: ${leads.length} leads loaded`);
        
        // Log cada lead en esta etapa
        if (leads.length > 0) {
          console.log(`\n📋 Leads en etapa "${stage.label}" (${stage.id}):`);
          leads.forEach((lead, idx) => {
            console.log(`  ${idx + 1}. ID: ${lead.id} | Nombre: ${lead.name || 'Sin nombre'} | Teléfono: ${lead.phone} | Stage: ${lead.pipeline_stage || 'NULL'} | Score: ${lead.lead_score || 0}`);
          });
        }
      });
      
      const totalLeads = Object.values(leadsByStage).reduce((sum, leads) => sum + leads.length, 0);
      console.log(`\n✅ Total leads loaded across all stages: ${totalLeads}`);
      
      // Log resumen completo
      console.log('\n📊 RESUMEN COMPLETO DEL PIPELINE:');
      console.log('='.repeat(60));
      Object.entries(leadsByStage).forEach(([stageId, leads]) => {
        const stage = PIPELINE_STAGES.find(s => s.id === stageId);
        console.log(`${stage?.label || stageId}: ${leads.length} leads`);
        if (leads.length > 0) {
          leads.forEach(lead => {
            console.log(`  - ID ${lead.id}: ${lead.name || 'Sin nombre'} (${lead.phone})`);
          });
        }
      });
      console.log('='.repeat(60));
      
      set({ leadsByStage, loading: false });
    } catch (error) {
      console.error('❌ Error fetching all stages:', error);
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

