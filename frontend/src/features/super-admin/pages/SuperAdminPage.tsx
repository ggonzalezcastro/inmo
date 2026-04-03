import { useEffect, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { useSuperAdminStore } from '../store/superAdminStore'
import { KPICards } from '../components/KPICards'
import { SystemHealthPanel } from '../components/SystemHealthPanel'
import { ErrorPanel } from '../components/ErrorPanel'
import { PlansPage } from '../components/PlansPage'
import { DLQPage } from '@/features/dlq'
import { AuditLogPage } from '@/features/audit-log'

const REFRESH_INTERVAL_MS = 30_000

export function SuperAdminPage() {
  const { kpis, health, isLoadingKPIs, isLoadingHealth, fetchKPIs, fetchHealth } = useSuperAdminStore()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = () => {
    fetchKPIs()
    fetchHealth()
  }

  useEffect(() => {
    refresh()
    intervalRef.current = setInterval(refresh, REFRESH_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const isLoading = isLoadingKPIs || isLoadingHealth

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Panel Super Admin</h1>
          <p className="text-sm text-slate-500 mt-0.5">Vista global del sistema</p>
        </div>
        <button
          onClick={refresh}
          disabled={isLoading}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          Actualizar
        </button>
      </div>

      {/* KPI Cards */}
      {kpis ? (
        <KPICards kpis={kpis} />
      ) : isLoadingKPIs ? (
        <div className="grid grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-24 bg-slate-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : null}

      {/* Tabs */}
      <Tabs defaultValue="health">
        <TabsList>
          <TabsTrigger value="health">System Health</TabsTrigger>
          <TabsTrigger value="errors">Errores</TabsTrigger>
          <TabsTrigger value="dlq">Dead Letter Queue</TabsTrigger>
          <TabsTrigger value="audit">Auditoría</TabsTrigger>
          <TabsTrigger value="plans">Planes</TabsTrigger>
        </TabsList>

        <TabsContent value="health" className="mt-4">
          {health ? (
            <SystemHealthPanel health={health} />
          ) : isLoadingHealth ? (
            <div className="grid grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-40 bg-slate-100 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="errors" className="mt-4">
          <ErrorPanel />
        </TabsContent>

        <TabsContent value="dlq" className="mt-4">
          <DLQPage />
        </TabsContent>

        <TabsContent value="audit" className="mt-4">
          <AuditLogPage />
        </TabsContent>

        <TabsContent value="plans" className="mt-4">
          <PlansPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
