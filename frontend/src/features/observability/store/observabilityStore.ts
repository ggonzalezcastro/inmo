import { create } from 'zustand'
import { observabilityApi } from '../services/observabilityApi'
import type {
  OverviewData,
  ConversationTrace,
  ConversationSearchItem,
  AgentPerformanceData,
  HandoffFlow,
  HandoffEscalations,
  CostByAgentData,
  CostByBrokerData,
  CostProjection,
  ObservabilityAlert,
  HealthData,
  RAGEffectivenessData,
  ObservabilityPeriod,
  AlertStatus,
} from '../types/observability.types'

interface ObservabilityState {
  // Overview
  overview: OverviewData | null
  overviewPeriod: ObservabilityPeriod
  isLoadingOverview: boolean
  overviewError: string | null

  // Conversations
  conversations: ConversationSearchItem[]
  conversationsTotal: number
  isLoadingConversations: boolean
  selectedTrace: ConversationTrace | null
  isLoadingTrace: boolean
  traceError: string | null

  // Agents
  agentPerformance: AgentPerformanceData | null
  agentPeriod: ObservabilityPeriod
  isLoadingAgents: boolean

  // Handoffs
  handoffFlow: HandoffFlow | null
  handoffEscalations: HandoffEscalations | null
  handoffPeriod: ObservabilityPeriod
  isLoadingHandoffs: boolean

  // Costs
  costByAgent: CostByAgentData | null
  costByBroker: CostByBrokerData | null
  costProjection: CostProjection | null
  costPeriod: ObservabilityPeriod
  isLoadingCosts: boolean

  // Alerts
  alerts: ObservabilityAlert[]
  alertsTotal: number
  alertsStatusFilter: AlertStatus | 'all'
  isLoadingAlerts: boolean

  // Health
  health: HealthData | null
  isLoadingHealth: boolean

  // RAG
  ragEffectiveness: RAGEffectivenessData | null
  isLoadingRAG: boolean

  // Actions
  setOverviewPeriod: (p: ObservabilityPeriod) => void
  setAgentPeriod: (p: ObservabilityPeriod) => void
  setHandoffPeriod: (p: ObservabilityPeriod) => void
  setCostPeriod: (p: ObservabilityPeriod) => void
  setAlertsStatusFilter: (s: AlertStatus | 'all') => void

  fetchOverview: () => Promise<void>
  searchConversations: (q?: string) => Promise<void>
  fetchTrace: (lead_id: number) => Promise<void>
  clearTrace: () => void
  fetchAgentPerformance: () => Promise<void>
  fetchHandoffs: () => Promise<void>
  fetchCosts: () => Promise<void>
  fetchAlerts: () => Promise<void>
  acknowledgeAlert: (id: string) => Promise<void>
  resolveAlert: (id: string) => Promise<void>
  dismissAlert: (id: string) => Promise<void>
  fetchHealth: () => Promise<void>
  fetchRAG: () => Promise<void>
}

export const useObservabilityStore = create<ObservabilityState>((set, get) => ({
  // Overview
  overview: null,
  overviewPeriod: '24h',
  isLoadingOverview: false,
  overviewError: null,

  // Conversations
  conversations: [],
  conversationsTotal: 0,
  isLoadingConversations: false,
  selectedTrace: null,
  isLoadingTrace: false,
  traceError: null,

  // Agents
  agentPerformance: null,
  agentPeriod: '7d',
  isLoadingAgents: false,

  // Handoffs
  handoffFlow: null,
  handoffEscalations: null,
  handoffPeriod: '7d',
  isLoadingHandoffs: false,

  // Costs
  costByAgent: null,
  costByBroker: null,
  costProjection: null,
  costPeriod: '7d',
  isLoadingCosts: false,

  // Alerts
  alerts: [],
  alertsTotal: 0,
  alertsStatusFilter: 'all',
  isLoadingAlerts: false,

  // Health
  health: null,
  isLoadingHealth: false,

  // RAG
  ragEffectiveness: null,
  isLoadingRAG: false,

  // Period setters
  setOverviewPeriod: (p) => {
    set({ overviewPeriod: p })
    get().fetchOverview()
  },
  setAgentPeriod: (p) => {
    set({ agentPeriod: p })
    get().fetchAgentPerformance()
  },
  setHandoffPeriod: (p) => {
    set({ handoffPeriod: p })
    get().fetchHandoffs()
  },
  setCostPeriod: (p) => {
    set({ costPeriod: p })
    get().fetchCosts()
  },
  setAlertsStatusFilter: (s) => {
    set({ alertsStatusFilter: s })
    get().fetchAlerts()
  },

  // Fetch actions
  fetchOverview: async () => {
    set({ isLoadingOverview: true, overviewError: null })
    try {
      const data = await observabilityApi.getOverview(get().overviewPeriod)
      set({ overview: data, isLoadingOverview: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar resumen'
      set({ overviewError: msg, isLoadingOverview: false })
    }
  },

  searchConversations: async (q?: string) => {
    set({ isLoadingConversations: true })
    try {
      const data = await observabilityApi.searchConversations({ q, limit: 50 })
      set({ conversations: data.items, conversationsTotal: data.total, isLoadingConversations: false })
    } catch {
      set({ isLoadingConversations: false })
    }
  },

  fetchTrace: async (lead_id: number) => {
    set({ isLoadingTrace: true, traceError: null, selectedTrace: null })
    try {
      const data = await observabilityApi.getConversationTrace(lead_id)
      set({ selectedTrace: data, isLoadingTrace: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar traza'
      set({ traceError: msg, isLoadingTrace: false })
    }
  },

  clearTrace: () => set({ selectedTrace: null, traceError: null }),

  fetchAgentPerformance: async () => {
    set({ isLoadingAgents: true })
    try {
      const data = await observabilityApi.getAgentPerformance(get().agentPeriod)
      set({ agentPerformance: data, isLoadingAgents: false })
    } catch {
      set({ isLoadingAgents: false })
    }
  },

  fetchHandoffs: async () => {
    set({ isLoadingHandoffs: true })
    try {
      const [flow, escalations] = await Promise.all([
        observabilityApi.getHandoffFlow(get().handoffPeriod),
        observabilityApi.getHandoffEscalations(get().handoffPeriod),
      ])
      set({ handoffFlow: flow, handoffEscalations: escalations, isLoadingHandoffs: false })
    } catch {
      set({ isLoadingHandoffs: false })
    }
  },

  fetchCosts: async () => {
    set({ isLoadingCosts: true })
    try {
      const [byAgent, byBroker, projection] = await Promise.all([
        observabilityApi.getCostByAgent(get().costPeriod),
        observabilityApi.getCostByBroker('month'),
        observabilityApi.getCostProjection(),
      ])
      set({ costByAgent: byAgent, costByBroker: byBroker, costProjection: projection, isLoadingCosts: false })
    } catch {
      set({ isLoadingCosts: false })
    }
  },

  fetchAlerts: async () => {
    set({ isLoadingAlerts: true })
    try {
      const filter = get().alertsStatusFilter
      const data = await observabilityApi.getAlerts(
        filter === 'all' ? undefined : filter
      )
      set({ alerts: data?.alerts ?? [], alertsTotal: data?.total ?? 0, isLoadingAlerts: false })
    } catch {
      set({ isLoadingAlerts: false })
    }
  },

  acknowledgeAlert: async (id: string) => {
    try {
      await observabilityApi.acknowledgeAlert(id)
      await get().fetchAlerts()
    } catch {
      // silently fail — UI remains unchanged
    }
  },

  resolveAlert: async (id: string) => {
    try {
      await observabilityApi.resolveAlert(id)
      await get().fetchAlerts()
    } catch {}
  },

  dismissAlert: async (id: string) => {
    try {
      await observabilityApi.dismissAlert(id)
      await get().fetchAlerts()
    } catch {}
  },

  fetchHealth: async () => {
    set({ isLoadingHealth: true })
    try {
      const data = await observabilityApi.getHealth()
      set({ health: data, isLoadingHealth: false })
    } catch {
      set({ isLoadingHealth: false })
    }
  },

  fetchRAG: async () => {
    set({ isLoadingRAG: true })
    try {
      const data = await observabilityApi.getRAGEffectiveness()
      set({ ragEffectiveness: data, isLoadingRAG: false })
    } catch {
      set({ isLoadingRAG: false })
    }
  },
}))
