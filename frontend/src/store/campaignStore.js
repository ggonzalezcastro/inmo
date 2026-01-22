import { create } from 'zustand';
import { campaignAPI } from '../services/api';

export const useCampaignStore = create((set, get) => ({
  campaigns: [],
  selectedCampaign: null,
  loading: false,
  error: null,
  stats: null,
  
  // Fetch all campaigns
  fetchCampaigns: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const response = await campaignAPI.getAll(filters);
      set({
        campaigns: response.data.data || response.data || [],
        loading: false,
      });
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
    }
  },
  
  // Get single campaign
  getCampaign: async (campaignId) => {
    set({ loading: true, error: null });
    try {
      const response = await campaignAPI.getOne(campaignId);
      set({
        selectedCampaign: response.data,
        loading: false,
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Create campaign
  createCampaign: async (data) => {
    set({ loading: true, error: null });
    try {
      const { steps, ...campaignData } = data;
      const response = await campaignAPI.create(campaignData);
      const newCampaign = response.data;
      
      // Add steps if provided
      if (steps && steps.length > 0) {
        for (const step of steps) {
          await campaignAPI.addStep(newCampaign.id, step);
        }
        // Fetch campaign again to get steps
        const updatedCampaign = await campaignAPI.getOne(newCampaign.id);
        set((state) => ({
          campaigns: [...state.campaigns, updatedCampaign.data],
          loading: false,
        }));
        return updatedCampaign.data;
      }
      
      set((state) => ({
        campaigns: [...state.campaigns, newCampaign],
        loading: false,
      }));
      
      return newCampaign;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Update campaign
  updateCampaign: async (campaignId, data) => {
    set({ loading: true, error: null });
    try {
      const response = await campaignAPI.update(campaignId, data);
      const updatedCampaign = response.data;
      
      set((state) => ({
        campaigns: state.campaigns.map(c => 
          c.id === campaignId ? updatedCampaign : c
        ),
        selectedCampaign: state.selectedCampaign?.id === campaignId
          ? updatedCampaign
          : state.selectedCampaign,
        loading: false,
      }));
      
      return updatedCampaign;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Delete campaign
  deleteCampaign: async (campaignId) => {
    set({ loading: true, error: null });
    try {
      await campaignAPI.delete(campaignId);
      
      set((state) => ({
        campaigns: state.campaigns.filter(c => c.id !== campaignId),
        selectedCampaign: state.selectedCampaign?.id === campaignId
          ? null
          : state.selectedCampaign,
        loading: false,
      }));
      
      return true;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return false;
    }
  },
  
  // Get campaign stats
  getCampaignStats: async (campaignId) => {
    set({ loading: true, error: null });
    try {
      const response = await campaignAPI.getStats(campaignId);
      set({
        stats: response.data,
        loading: false,
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Apply campaign to lead
  applyCampaignToLead: async (campaignId, leadId) => {
    try {
      const response = await campaignAPI.applyToLead(campaignId, leadId);
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Add step to campaign
  addStep: async (campaignId, stepData) => {
    try {
      const response = await campaignAPI.addStep(campaignId, stepData);
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Delete step from campaign
  deleteStep: async (campaignId, stepId) => {
    try {
      await campaignAPI.deleteStep(campaignId, stepId);
      return true;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return false;
    }
  },
  
  // Get campaign logs
  getCampaignLogs: async (campaignId, params = {}) => {
    try {
      const response = await campaignAPI.getLogs(campaignId, params);
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Set selected campaign
  setSelectedCampaign: (campaign) => {
    set({ selectedCampaign: campaign });
  },
}));

