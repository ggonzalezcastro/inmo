import { useEffect } from 'react'
import { useObservabilityStore } from '../store/observabilityStore'

const STRATEGY_LABELS: Record<string, string> = {
  hybrid: 'Híbrida',
  structured: 'Estructurada',
  semantic: 'Semántica',
}

export function RAGPanel() {
  const { ragEffectiveness, isLoadingRAG, fetchRAG } = useObservabilityStore()

  useEffect(() => {
    fetchRAG()
  }, [fetchRAG])

  return (
    <div className="space-y-6">
      <h2 className="text-sm font-semibold text-slate-700">Efectividad de búsqueda de propiedades (RAG)</h2>

      {isLoadingRAG && !ragEffectiveness ? (
        <div className="space-y-4">
          <div className="flex gap-4">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="flex-1 h-24 bg-slate-100 animate-pulse rounded-xl" />
            ))}
          </div>
          <div className="h-40 bg-slate-100 animate-pulse rounded-xl" />
        </div>
      ) : !ragEffectiveness ? (
        <div className="rounded-xl border border-slate-200 py-16 text-center">
          <p className="text-sm text-slate-400">
            Aún no hay datos de búsqueda RAG. Los datos aparecerán cuando los agentes realicen búsquedas de propiedades.
          </p>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="flex gap-4">
            <div className="rounded-xl border border-slate-200 p-4 bg-white flex-1">
              <p className="text-xs text-slate-500 mb-1">Total de búsquedas</p>
              <p className="text-2xl font-bold text-slate-900">
                {ragEffectiveness.total_searches.toLocaleString()}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">en el período</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4 bg-white flex-1">
              <p className="text-xs text-slate-500 mb-1">Resultados promedio</p>
              <p className="text-2xl font-bold text-slate-900">
                {ragEffectiveness.avg_results_per_search.toFixed(1)}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">por búsqueda</p>
            </div>
          </div>

          {/* By strategy table */}
          {ragEffectiveness.by_strategy.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-900">Por estrategia</h3>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Estrategia
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Búsquedas
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Resultados prom.
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Latencia prom.
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ragEffectiveness.by_strategy.map((s) => (
                    <tr
                      key={s.strategy}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {STRATEGY_LABELS[s.strategy] ?? s.strategy}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-700">
                        {s.search_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-700">
                        {s.avg_results.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-500">
                        {s.avg_latency_ms != null ? `${s.avg_latency_ms.toFixed(0)} ms` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 py-10 text-center">
              <p className="text-sm text-slate-400">Sin desglose por estrategia disponible</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
