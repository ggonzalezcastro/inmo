import axios from 'axios';


const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';


const api = axios.create({
  baseURL: API_URL,
  timeout: 60000, // 60 seconds - increased for chat requests that may take longer
});


// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});


// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);


export const authAPI = {
  register: (email, password, broker_name) =>
    api.post('/auth/register', { email, password, broker_name }),
  login: (email, password) =>
    api.post('/auth/login', { email, password }),
  getCurrentUser: () => api.get('/auth/me'),
};


export const leadsAPI = {
  getAll: (params) => api.get('/api/v1/leads', { params }),
  getOne: (id) => api.get(`/api/v1/leads/${id}`),
  create: (data) => api.post('/api/v1/leads', data),
  update: (id, data) => api.put(`/api/v1/leads/${id}`, data),
  delete: (id) => api.delete(`/api/v1/leads/${id}`),
  bulkImport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/v1/leads/bulk-import', formData);
  },
  // New endpoints
  assign: (id, agentId) => api.put(`/api/v1/leads/${id}/assign`, { agent_id: agentId }),
  movePipeline: (id, stage) => api.put(`/api/v1/leads/${id}/pipeline`, { stage }),
  recalculate: (id) => api.post(`/api/v1/leads/${id}/recalculate`),
};

export const pipelineAPI = {
  getLeadsByStage: (stage, filters = {}) => {
    // Remove empty/null/undefined params to avoid sending empty query strings
    const cleanParams = Object.entries(filters).reduce((acc, [key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        acc[key] = value;
      }
      return acc;
    }, {});
    return api.get(`/api/v1/pipeline/stages/${stage}/leads`, { params: cleanParams });
  },
  moveLeadToStage: (leadId, newStage, reason = '') => 
    api.post(`/api/v1/pipeline/leads/${leadId}/move-stage`, { 
      new_stage: newStage, 
      reason 
    }),
  autoAdvanceStage: (leadId) => 
    api.post(`/api/v1/pipeline/leads/${leadId}/auto-advance`),
  getStageMetrics: () => 
    api.get('/api/v1/pipeline/metrics'),
  getInactiveLeads: (stage, inactivityDays = 7) => 
    api.get(`/api/v1/pipeline/stages/${stage}/inactive`, { params: { inactivity_days: inactivityDays } }),
};

export const campaignAPI = {
  getAll: (params = {}) => api.get('/api/v1/campaigns', { params }),
  getOne: (id) => api.get(`/api/v1/campaigns/${id}`),
  create: (data) => api.post('/api/v1/campaigns', data),
  update: (id, data) => api.put(`/api/v1/campaigns/${id}`, data),
  delete: (id) => api.delete(`/api/v1/campaigns/${id}`),
  addStep: (campaignId, stepData) => 
    api.post(`/api/v1/campaigns/${campaignId}/steps`, stepData),
  deleteStep: (campaignId, stepId) => 
    api.delete(`/api/v1/campaigns/${campaignId}/steps/${stepId}`),
  applyToLead: (campaignId, leadId) => 
    api.post(`/api/v1/campaigns/${campaignId}/apply-to-lead/${leadId}`),
  getStats: (id) => api.get(`/api/v1/campaigns/${id}/stats`),
  getLogs: (id, params = {}) => 
    api.get(`/api/v1/campaigns/${id}/logs`, { params }),
};

export const ticketAPI = {
  // Get lead data
  getTicket: (leadId) => api.get(`/api/v1/leads/${leadId}`),
  // Get messages for a lead (new endpoint)
  getMessages: (leadId, skip = 0, limit = 100) => 
    api.get(`/api/v1/chat/${leadId}/messages`, { params: { skip, limit } }),
  sendMessage: (leadId, data) => 
    api.post(`/api/v1/leads/${leadId}/messages`, data),
  updateField: (leadId, field, value) => 
    api.put(`/api/v1/leads/${leadId}`, { [field]: value }),
  addNote: (leadId, note) => 
    api.put(`/api/v1/leads/${leadId}`, { notes: note }),
  addTask: (leadId, task) => 
    api.post(`/api/v1/leads/${leadId}/tasks`, task),
};

// Broker Configuration API
export const brokerAPI = {
  getConfig: () => api.get('/api/broker/config'),
  updatePromptConfig: (data) => api.put('/api/broker/config/prompt', data),
  updateLeadConfig: (data) => api.put('/api/broker/config/leads', data),
  getPromptPreview: () => api.get('/api/broker/config/prompt/preview'),
  getDefaults: () => api.get('/api/broker/config/defaults'),
  // Users management
  getUsers: () => api.get('/api/broker/users'),
  createUser: (data) => api.post('/api/broker/users', data),
  updateUser: (userId, data) => api.put(`/api/broker/users/${userId}`, data),
  deleteUser: (userId) => api.delete(`/api/broker/users/${userId}`),
  // Brokers management (SuperAdmin only)
  getBrokers: () => api.get('/api/brokers/'),  // Use trailing slash to match route
  createBroker: (data) => api.post('/api/brokers/', data),
  updateBroker: (brokerId, data) => api.put(`/api/brokers/${brokerId}`, data),
  deleteBroker: (brokerId) => api.delete(`/api/brokers/${brokerId}`),
};

export const templateAPI = {
  getAll: (params = {}) => api.get('/api/v1/templates', { params }),
  getOne: (id) => api.get(`/api/v1/templates/${id}`),
  getByAgentType: (agentType, channel = null) => 
    api.get(`/api/v1/templates/agent-type/${agentType}`, { params: channel ? { channel } : {} }),
  create: (data) => api.post('/api/v1/templates', data),
  update: (id, data) => api.put(`/api/v1/templates/${id}`, data),
  delete: (id) => api.delete(`/api/v1/templates/${id}`),
};

export const callsAPI = {
  initiate: (data) => api.post('/api/v1/calls/initiate', data),
  getByLead: (leadId) => api.get(`/api/v1/calls/leads/${leadId}`),
  getOne: (callId) => api.get(`/api/v1/calls/${callId}`),
};

// LLM costs dashboard (admin)
export const costsAPI = {
  getSummary: (params) => api.get('/api/v1/admin/costs/summary', { params }),
  getDaily: (params) => api.get('/api/v1/admin/costs/daily', { params }),
  getOutliers: (params) => api.get('/api/v1/admin/costs/outliers', { params }),
  exportCsv: (params) =>
    api.get('/api/v1/admin/costs/export', { params, responseType: 'blob' }),
  getByBroker: (params) => api.get('/api/v1/admin/costs/by-broker', { params }),
  getCalls: (params) => api.get('/api/v1/admin/costs/calls', { params }),
};

export default api;

