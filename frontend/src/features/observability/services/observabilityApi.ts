import { apiClient } from '@/shared/lib/api-client'
import type {
  OverviewData,
  ConversationTrace,
  ConversationSearchResponse,
  AgentPerformanceData,
  HandoffFlow,
  HandoffEscalations,
  CostByAgentData,
  CostByBrokerData,
  CostProjection,
  AlertsResponse,
  ObservabilityAlert,
  HealthData,
  RAGEffectivenessData,
  ObservabilityPeriod,
  AlertStatus,
} from '../types/observability.types'

const BASE = '/api/v1/admin/observability'

export const observabilityApi = {
  // Overview
  getOverview: (period: ObservabilityPeriod = '24h', broker_id?: number) =>
    apiClient.get<OverviewData>(`${BASE}/overview`, {
      params: { period, ...(broker_id ? { broker_id } : {}) },
    }),

  // Conversation trace
  getConversationTrace: (lead_id: number) =>
    apiClient.get<ConversationTrace>(`${BASE}/conversations/${lead_id}/trace`),

  // Conversations search
  searchConversations: (params?: {
    q?: string
    stage?: string
    agent?: string
    human_mode?: boolean
    page?: number
    limit?: number
  }) =>
    apiClient.get<ConversationSearchResponse>(`${BASE}/conversations/search`, { params }),

  // Agent performance
  getAgentPerformance: (period: ObservabilityPeriod = '7d') =>
    apiClient.get<AgentPerformanceData>(`${BASE}/agents/performance`, { params: { period } }),

  // Handoffs
  getHandoffFlow: (period: ObservabilityPeriod = '7d') =>
    apiClient.get<HandoffFlow>(`${BASE}/handoffs/flow`, { params: { period } }),

  getHandoffEscalations: (period: ObservabilityPeriod = '7d') =>
    apiClient.get<HandoffEscalations>(`${BASE}/handoffs/escalations`, { params: { period } }),

  // Costs
  getCostByAgent: (period: ObservabilityPeriod = '7d') =>
    apiClient.get<CostByAgentData>(`${BASE}/costs/by-agent`, { params: { period } }),

  getCostByBroker: (period: string = 'month') =>
    apiClient.get<CostByBrokerData>('/api/v1/admin/costs/by-broker', { params: { period } }),

  getCostProjection: () => apiClient.get<CostProjection>(`${BASE}/costs/projection`),

  // Alerts
  getAlerts: (status?: AlertStatus) =>
    apiClient.get<AlertsResponse>(`${BASE}/alerts`, {
      params: status && status !== 'active' ? { status } : undefined,
    }),

  acknowledgeAlert: (id: string) =>
    apiClient.post<ObservabilityAlert>(`${BASE}/alerts/${id}/acknowledge`),

  resolveAlert: (id: string) =>
    apiClient.post<ObservabilityAlert>(`${BASE}/alerts/${id}/resolve`),

  dismissAlert: (id: string) =>
    apiClient.post<ObservabilityAlert>(`${BASE}/alerts/${id}/dismiss`),

  // Health
  getHealth: () => apiClient.get<HealthData>(`${BASE}/health`),

  // RAG
  getRAGEffectiveness: () =>
    apiClient.get<RAGEffectivenessData>(`${BASE}/rag/property-search-effectiveness`),
}
