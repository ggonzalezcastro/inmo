import { create } from 'zustand';
import { ticketAPI, callsAPI, templateAPI } from '../services/api';

export const useTicketStore = create((set, get) => ({
  currentTicket: null,
  messages: [],
  notes: [],
  tasks: [],
  loading: false,
  error: null,
  
  // Fetch full ticket data
  fetchTicket: async (leadId) => {
    set({ loading: true, error: null });
    try {
      const response = await ticketAPI.getTicket(leadId);
      const ticket = response.data;
      
      set({
        currentTicket: ticket,
        messages: ticket.messages || [],
        notes: ticket.notes || [],
        tasks: ticket.tasks || [],
        loading: false,
      });
      
      return ticket;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message,
        loading: false 
      });
      return null;
    }
  },
  
  // Send message
  sendMessage: async (leadId, text, type = 'manual') => {
    try {
      const response = await ticketAPI.sendMessage(leadId, {
        message_text: text,
        message_type: type,
      });
      
      const newMessage = response.data;
      set((state) => ({
        messages: [...state.messages, newMessage],
      }));
      
      // Refresh ticket to get updated data
      await get().fetchTicket(leadId);
      
      return newMessage;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Update any ticket field
  updateTicketField: async (leadId, field, value) => {
    try {
      await ticketAPI.updateField(leadId, field, value);
      
      set((state) => ({
        currentTicket: state.currentTicket
          ? { ...state.currentTicket, [field]: value }
          : null,
      }));
      
      return true;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return false;
    }
  },
  
  // Move to stage
  moveToStage: async (leadId, newStage, reason = '') => {
    return await get().updateTicketField(leadId, 'pipeline_stage', newStage);
  },
  
  // Initiate call
  initiateCall: async (leadId, campaignId = null, agentType = null) => {
    try {
      const response = await callsAPI.initiate({
        lead_id: leadId,
        campaign_id: campaignId,
        agent_type: agentType,
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Get calls for lead
  getCallsForLead: async (leadId) => {
    try {
      const response = await callsAPI.getByLead(leadId);
      return response.data.data || [];
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return [];
    }
  },
  
  // Get call details
  getCallDetails: async (callId) => {
    try {
      const response = await callsAPI.getOne(callId);
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Apply template
  applyTemplate: async (leadId, templateId) => {
    try {
      // Get template first
      const templateResponse = await templateAPI.getOne(templateId);
      const template = templateResponse.data;
      
      // Get current ticket data
      const currentTicket = get().currentTicket;
      const lead = currentTicket?.lead || currentTicket;
      
      // Prepare variables
      const variables = {
        name: lead?.name || '',
        phone: lead?.phone || '',
        email: lead?.email || '',
        budget: lead?.lead_metadata?.budget || lead?.metadata?.budget || '',
        timeline: lead?.lead_metadata?.timeline || lead?.metadata?.timeline || '',
        location: lead?.lead_metadata?.location || lead?.metadata?.location || '',
        score: lead?.lead_score || 0,
        stage: lead?.pipeline_stage || '',
      };
      
      // Render template
      let renderedText = template.content || '';
      Object.entries(variables).forEach(([key, value]) => {
        const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
        renderedText = renderedText.replace(regex, String(value || ''));
      });
      
      // Send rendered message
      return await get().sendMessage(leadId, renderedText, 'template');
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Add internal note
  addNote: async (leadId, note) => {
    try {
      const response = await ticketAPI.addNote(leadId, note);
      const newNote = response.data;
      
      set((state) => ({
        notes: [...state.notes, newNote],
      }));
      
      return newNote;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Add task
  addTask: async (leadId, task) => {
    try {
      const response = await ticketAPI.addTask(leadId, task);
      const newTask = response.data;
      
      set((state) => ({
        tasks: [...state.tasks, newTask],
      }));
      
      return newTask;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || error.message 
      });
      return null;
    }
  },
  
  // Clear current ticket
  clearTicket: () => {
    set({
      currentTicket: null,
      messages: [],
      notes: [],
      tasks: [],
      error: null,
    });
  },
}));

