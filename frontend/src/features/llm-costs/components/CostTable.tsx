import { Fragment, useEffect, useState } from 'react';
import * as costsApi from '../services/costsApi';
import { useCostsStore } from '../store/costsStore';
import type { LLMUsage } from '../types/costs.types';

const PAGE_SIZE = 50;

export function CostTable() {
  const { selectedBrokerId } = useCostsStore();
  const [items, setItems] = useState<LLMUsage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filters, setFilters] = useState({
    provider: '',
    status: '',
  });

  useEffect(() => {
    setLoading(true);
    costsApi.getCalls({
      page,
      limit: PAGE_SIZE,
      broker_id: selectedBrokerId ?? undefined,
      provider: filters.provider || undefined,
      status: filters.status || undefined,
    })
      .then((res) => {
        setItems(res.items as LLMUsage[]);
        setTotal(res.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, selectedBrokerId, filters.provider, filters.status]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="bg-white shadow rounded-lg p-6 mt-8">
      <h2 className="text-lg font-medium text-gray-900 mb-4">Detalle de llamadas LLM</h2>
      <div className="flex gap-4 mb-4">
        <select
          value={filters.provider}
          onChange={(e) => setFilters((f) => ({ ...f, provider: e.target.value }))}
          className="rounded border-gray-300 text-sm"
        >
          <option value="">Todos los providers</option>
          <option value="gemini">Gemini</option>
          <option value="claude">Claude</option>
          <option value="openai">OpenAI</option>
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          className="rounded border-gray-300 text-sm"
        >
          <option value="">Todos</option>
          <option value="success">Éxito</option>
          <option value="error">Error</option>
        </select>
      </div>
      {loading ? (
        <p className="text-gray-500">Cargando...</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="px-2 py-2">Timestamp</th>
                  <th className="px-2 py-2">Lead</th>
                  <th className="px-2 py-2">Provider</th>
                  <th className="px-2 py-2">Modelo</th>
                  <th className="px-2 py-2 text-right">Input</th>
                  <th className="px-2 py-2 text-right">Output</th>
                  <th className="px-2 py-2 text-right">Costo USD</th>
                  <th className="px-2 py-2 text-right">Latencia</th>
                  <th className="px-2 py-2">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {items.map((row) => (
                  <Fragment key={row.id}>
                    <tr
                      className={
                        row.error
                          ? 'bg-red-50'
                          : (row.latency_ms ?? 0) > 5000
                            ? 'bg-amber-50'
                            : ''
                      }
                    >
                      <td className="px-2 py-2 text-gray-700">
                        {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-2 py-2">{row.lead_id ?? '—'}</td>
                      <td className="px-2 py-2">{row.provider}</td>
                      <td className="px-2 py-2">{row.model}</td>
                      <td className="px-2 py-2 text-right">{row.input_tokens ?? '—'}</td>
                      <td className="px-2 py-2 text-right">{row.output_tokens ?? '—'}</td>
                      <td className="px-2 py-2 text-right">
                        {row.estimated_cost_usd != null
                          ? row.estimated_cost_usd.toFixed(6)
                          : '—'}
                      </td>
                      <td className="px-2 py-2 text-right">
                        {row.latency_ms != null ? `${row.latency_ms} ms` : '—'}
                      </td>
                      <td className="px-2 py-2">
                        {row.error ? (
                          <span className="text-red-600" title={row.error}>
                            Error
                          </span>
                        ) : (
                          <span className="text-green-600">OK</span>
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedId(expandedId === row.id ? null : row.id)
                          }
                          className="text-blue-600 hover:underline"
                        >
                          {expandedId === row.id ? 'Ocultar' : 'Detalle'}
                        </button>
                      </td>
                    </tr>
                    {expandedId === row.id && (
                      <tr>
                        <td colSpan={10} className="px-2 py-2 bg-gray-50 text-xs">
                          <pre className="whitespace-pre-wrap">
                            {JSON.stringify(
                              {
                                id: row.id,
                                call_type: row.call_type,
                                used_fallback: row.used_fallback,
                                error: row.error,
                              },
                              null,
                              2
                            )}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Total: {total} llamadas
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50 text-sm"
              >
                Anterior
              </button>
              <span className="py-1 text-sm">
                Página {page} de {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50 text-sm"
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
