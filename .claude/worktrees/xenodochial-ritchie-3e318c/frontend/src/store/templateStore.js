import { create } from 'zustand';
import { templateAPI } from '../services/api';

export const useTemplateStore = create((set, get) => ({
  templates: [],
  selectedTemplate: null,
  loading: false,
  error: null,
  
  // Fetch templates
  fetchTemplates: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const response = await templateAPI.getAll(filters);
      set({
        templates: response.data.data || response.data || [],
        loading: false,
      });
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
    }
  },
  
  // Get single template
  getTemplate: async (templateId) => {
    set({ loading: true, error: null });
    try {
      const response = await templateAPI.getOne(templateId);
      set({
        selectedTemplate: response.data,
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
  
  // Create template
  createTemplate: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await templateAPI.create(data);
      const newTemplate = response.data;
      
      set((state) => ({
        templates: [...state.templates, newTemplate],
        loading: false,
      }));
      
      return newTemplate;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Update template
  updateTemplate: async (templateId, data) => {
    set({ loading: true, error: null });
    try {
      const response = await templateAPI.update(templateId, data);
      const updatedTemplate = response.data;
      
      set((state) => ({
        templates: state.templates.map(t => 
          t.id === templateId ? updatedTemplate : t
        ),
        selectedTemplate: state.selectedTemplate?.id === templateId
          ? updatedTemplate
          : state.selectedTemplate,
        loading: false,
      }));
      
      return updatedTemplate;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Delete template
  deleteTemplate: async (templateId) => {
    set({ loading: true, error: null });
    try {
      await templateAPI.delete(templateId);
      
      set((state) => ({
        templates: state.templates.filter(t => t.id !== templateId),
        selectedTemplate: state.selectedTemplate?.id === templateId
          ? null
          : state.selectedTemplate,
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
  
  // Render template with variables (client-side)
  renderTemplate: (templateContent, variables) => {
    if (!templateContent) return '';
    let rendered = templateContent;
    Object.entries(variables).forEach(([key, value]) => {
      const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
      rendered = rendered.replace(regex, String(value || ''));
    });
    return rendered;
  },
  
  // Get templates by agent type
  getTemplatesByAgentType: async (agentType, channel = null) => {
    set({ loading: true, error: null });
    try {
      const response = await templateAPI.getByAgentType(agentType, channel);
      set({
        templates: response.data.data || [],
        loading: false,
      });
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
    }
  },
  
  // Set selected template
  setSelectedTemplate: (template) => {
    set({ selectedTemplate: template });
  },
}));

