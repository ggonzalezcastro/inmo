import { useEffect, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { useObservabilityStore } from '../store/observabilityStore'
import { OverviewPanel } from '../components/OverviewPanel'
import { ConversationDebugger } from '../components/ConversationDebugger'
import { AgentPerformancePanel } from '../components/AgentPerformancePanel'
import { CostAnalysisPanel } from '../components/CostAnalysisPanel'
import { HandoffMonitor } from '../components/HandoffMonitor'
import { AlertsPanel } from '../components/AlertsPanel'
import { HealthPanel } from '../components/HealthPanel'
import { RAGPanel } from '../components/RAGPanel'
import { PromptVersioningPanel } from '../components/PromptVersioningPanel'
import { LiveTailPanel } from '../components/LiveTailPanel'

const OVERVIEW_REFRESH_MS = 30_000

export function ObservabilityPage() {
  const { isLoadingOverview, fetchOverview, fetchAlerts, alerts } = useObservabilityStore()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchOverview()
    fetchAlerts()
    intervalRef.current = setInterval(fetchOverview, OVERVIEW_REFRESH_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchOverview, fetchAlerts])

  const criticalCount = (alerts ?? []).filter(
    (a) => a.severity === 'critical' && a.status === 'active'
  ).length

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Observabilidad</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Monitoreo de agentes IA, costos y conversaciones
          </p>
        </div>
        <button
          onClick={fetchOverview}
          disabled={isLoadingOverview}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={isLoadingOverview ? 'animate-spin' : ''} />
          Actualizar
        </button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="resumen">
        <TabsList className="flex-wrap">
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="conversaciones">Conversaciones</TabsTrigger>
          <TabsTrigger value="agentes">Agentes</TabsTrigger>
          <TabsTrigger value="costos">Costos LLM</TabsTrigger>
          <TabsTrigger value="handoffs">Handoffs</TabsTrigger>
          <TabsTrigger value="alertas" className="relative">
            Alertas
            {criticalCount > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 text-xs font-bold rounded-full bg-red-600 text-white">
                {criticalCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="salud">Salud</TabsTrigger>
          <TabsTrigger value="rag">RAG</TabsTrigger>
          <TabsTrigger value="prompts">Prompts</TabsTrigger>
          <TabsTrigger value="livetail">Live tail</TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="mt-4">
          <OverviewPanel />
        </TabsContent>

        <TabsContent value="conversaciones" className="mt-4">
          <ConversationDebugger />
        </TabsContent>

        <TabsContent value="agentes" className="mt-4">
          <AgentPerformancePanel />
        </TabsContent>

        <TabsContent value="costos" className="mt-4">
          <CostAnalysisPanel />
        </TabsContent>

        <TabsContent value="handoffs" className="mt-4">
          <HandoffMonitor />
        </TabsContent>

        <TabsContent value="alertas" className="mt-4">
          <AlertsPanel />
        </TabsContent>

        <TabsContent value="salud" className="mt-4">
          <HealthPanel />
        </TabsContent>

        <TabsContent value="rag" className="mt-4">
          <RAGPanel />
        </TabsContent>

        <TabsContent value="prompts" className="mt-4">
          <PromptVersioningPanel />
        </TabsContent>

        <TabsContent value="livetail" className="mt-4">
          <LiveTailPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
