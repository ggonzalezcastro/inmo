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
      // Fetch lead data and messages in parallel
      const [ticketResponse, messagesResponse] = await Promise.all([
        ticketAPI.getTicket(leadId),
        ticketAPI.getMessages(leadId, 0, 100)
      ]);
      
      const ticket = ticketResponse.data;
      const messagesData = messagesResponse.data;
      
      // Map messages from the new endpoint format
      let messages = [];
      if (messagesData.messages && Array.isArray(messagesData.messages)) {
        messages = messagesData.messages.map(msg => ({
          id: msg.id,
          message_text: msg.message_text || msg.text,
          sender_type: msg.sender_type || (msg.direction === 'in' ? 'customer' : (msg.ai_response_used ? 'bot' : 'agent')),
          created_at: msg.created_at || msg.timestamp,
          timestamp: msg.timestamp || msg.created_at,
          direction: msg.direction,
          ai_response_used: msg.ai_response_used || false,
        }));
      }
      
      // Sort messages by timestamp (oldest first)
      messages.sort((a, b) => {
        const timeA = new Date(a.created_at || a.timestamp || 0);
        const timeB = new Date(b.created_at || b.timestamp || 0);
        return timeA - timeB;
      });
      
      console.log('📥 Ticket data loaded:', {
        leadId,
        ticket: ticket?.id,
        messagesCount: messages.length,
        total: messagesData.total,
        messages: messages.slice(0, 3), // Log first 3 messages
      });
      
      set({
        currentTicket: ticket,
        messages: messages,
        notes: ticket.notes || [],
        tasks: ticket.tasks || [],
        loading: false,
      });
      
      return ticket;
    } catch (error) {
      console.error('❌ Error fetching ticket:', error);
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
      
      // Add message to state immediately for better UX
      set((state) => ({
        messages: [...state.messages, {
          id: newMessage.id || Date.now(),
          message_text: newMessage.message_text || text,
          sender_type: 'agent',
          created_at: newMessage.created_at || new Date().toISOString(),
          timestamp: newMessage.timestamp || new Date().toISOString(),
          direction: 'out',
          ai_response_used: false,
        }],
      }));
      
      // Refresh messages to get the latest from server
      setTimeout(async () => {
        await get().fetchTicket(leadId);
      }, 500);
      
      return newMessage;
    } catch (error) {
      console.error('❌ Error sending message:', error);
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

