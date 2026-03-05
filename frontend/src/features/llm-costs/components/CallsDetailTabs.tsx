import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import * as costsApi from '../services/costsApi';
import { useCostsStore } from '../store/costsStore';
import type { LLMUsage, VoiceCallItem, CostPeriod } from '../types/costs.types';

const PAGE_SIZE = 50;

/** Format USD with smart scaling */
function formatUSD(usd: number | null): string {
  if (usd == null) return '—';
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `${(usd * 100).toFixed(4)}¢`;
  return `$${usd.toFixed(4)}`;
}

/** Format seconds as m:ss */
function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')} min`;
}

/** Format datetime compactly */
function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('es-CL', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-emerald-700 bg-emerald-50',
  answered: 'text-emerald-700 bg-emerald-50',
  failed: 'text-red-700 bg-red-50',
  no_answer: 'text-amber-700 bg-amber-50',
  busy: 'text-amber-700 bg-amber-50',
  initiated: 'text-blue-700 bg-blue-50',
  ringing: 'text-blue-700 bg-blue-50',
  cancelled: 'text-gray-700 bg-gray-100',
};

// ─── Chat Tab ──────────────────────────────────────────────────────────────────

function ChatCallsTab({ period, brokerId }: { period: string; brokerId: number | null }) {
  const [items, setItems] = useState<LLMUsage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    setPage(1);
  }, [period, brokerId, statusFilter]);

  useEffect(() => {
    setLoading(true);
    costsApi
      .getCalls({
        page,
        limit: PAGE_SIZE,
        broker_id: brokerId ?? undefined,
        status: statusFilter || undefined,
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
  }, [page, brokerId, statusFilter, period]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const CALL_TYPE_LABELS: Record<string, string> = {
    chat_response: 'Chat',
    qualification: 'Calificación',
    tool_call: 'Herramienta',
  };

  return (
    <div>
      {/* Filters row */}
      <div className="flex items-center gap-3 mb-5">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 text-sm px-3 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Todos los estados</option>
          <option value="success">Sin errores</option>
          <option value="error">Con error</option>
        </select>
        <span className="ml-auto text-sm text-gray-500">{total.toLocaleString()} llamadas</span>
      </div>

      {loading ? (
        <div className="py-12 flex justify-center">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-10 text-center text-sm text-gray-500">No hay datos en el período seleccionado.</p>
      ) : (
        <>
          <div className="overflow-x-auto -mx-6">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Fecha</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Lead</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Tipo</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Tokens</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Costo</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Latencia</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Estado</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((row) => (
                  <Fragment key={row.id}>
                    <tr className={`hover:bg-gray-50 transition-colors ${row.error ? 'bg-red-50/40' : ''}`}>
                      <td className="px-6 py-3 text-sm text-gray-600 whitespace-nowrap">
                        {row.created_at ? fmtDate(row.created_at) : '—'}
                      </td>
                      <td className="px-6 py-3 text-sm">
                        {row.lead_id ? (
                          <Link to={`/chat?leadId=${row.lead_id}`} className="text-blue-600 hover:underline font-medium">
                            #{row.lead_id}
                          </Link>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-700">
                        {CALL_TYPE_LABELS[row.call_type] ?? row.call_type ?? '—'}
                      </td>
                      <td className="px-6 py-3 text-sm text-right text-gray-700 tabular-nums">
                        {row.input_tokens != null || row.output_tokens != null
                          ? `${(row.input_tokens ?? 0) + (row.output_tokens ?? 0)}`
                          : '—'}
                      </td>
                      <td className="px-6 py-3 text-sm text-right font-medium text-gray-900 tabular-nums">
                        {formatUSD(row.estimated_cost_usd)}
                      </td>
                      <td className="px-6 py-3 text-sm text-right text-gray-600 tabular-nums">
                        {row.latency_ms != null ? `${row.latency_ms} ms` : '—'}
                      </td>
                      <td className="px-6 py-3">
                        {row.error ? (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-50 text-red-700">
                            Error
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700">
                            OK
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-right">
                        {row.error && (
                          <button
                            type="button"
                            onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            {expandedId === row.id ? 'Ocultar' : 'Ver error'}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expandedId === row.id && row.error && (
                      <tr>
                        <td colSpan={8} className="px-6 py-3 bg-red-50 text-xs text-red-800 font-mono">
                          {row.error}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} total={total} />
        </>
      )}
    </div>
  );
}

// ─── Voice Tab ─────────────────────────────────────────────────────────────────

function VoiceCallsTab({ period, brokerId }: { period: string; brokerId: number | null }) {
  const [items, setItems] = useState<VoiceCallItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => { setPage(1); }, [period, brokerId]);

  useEffect(() => {
    setLoading(true);
    costsApi
      .getVoiceCalls({
        page,
        limit: PAGE_SIZE,
        broker_id: brokerId ?? undefined,
        period: period as CostPeriod,
      })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, brokerId, period]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const STATUS_LABELS: Record<string, string> = {
    completed: 'Completada',
    answered: 'Atendida',
    failed: 'Fallida',
    no_answer: 'No contestó',
    busy: 'Ocupado',
    initiated: 'Iniciada',
    ringing: 'Sonando',
    cancelled: 'Cancelada',
  };

  return (
    <div>
      <div className="flex items-center mb-5">
        <span className="ml-auto text-sm text-gray-500">{total.toLocaleString()} llamadas</span>
      </div>

      {loading ? (
        <div className="py-12 flex justify-center">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-10 text-center text-sm text-gray-500">No hay llamadas de voz en el período seleccionado.</p>
      ) : (
        <>
          <div className="overflow-x-auto -mx-6">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Fecha</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Lead</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Teléfono</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Duración</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((row) => (
                  <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {row.created_at ? fmtDate(row.created_at) : '—'}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {row.lead_id ? (
                        <Link to={`/chat?leadId=${row.lead_id}`} className="text-blue-600 hover:underline font-medium">
                          #{row.lead_id}
                        </Link>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-600">{row.phone_number ?? '—'}</td>
                    <td className="px-6 py-3 text-sm text-right font-medium text-gray-900 tabular-nums">
                      {formatDuration(row.duration_seconds)}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_COLORS[row.status] ?? 'text-gray-700 bg-gray-100'
                        }`}
                      >
                        {STATUS_LABELS[row.status] ?? row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} total={total} />
        </>
      )}
    </div>
  );
}

// ─── Pagination helper ─────────────────────────────────────────────────────────

function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  return (
    <div className="mt-5 flex items-center justify-between border-t border-gray-200 pt-4">
      <p className="text-sm text-gray-500">
        Página {page} de {totalPages} · {total.toLocaleString()} registros
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="px-3 py-1.5 rounded-md border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ← Anterior
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="px-3 py-1.5 rounded-md border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Siguiente →
        </button>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

export function CallsDetailTabs() {
  const { period, selectedBrokerId } = useCostsStore();
  const [activeTab, setActiveTab] = useState<'chat' | 'voice'>('chat');

  const tabs = [
    { id: 'chat' as const, label: 'Conversaciones chat', icon: '💬' },
    { id: 'voice' as const, label: 'Llamadas de voz', icon: '📞' },
  ];

  return (
    <div className="bg-white shadow rounded-lg mt-8 overflow-hidden">
      {/* Tab header */}
      <div className="border-b border-gray-200 px-6 pt-6 pb-0">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Detalle de actividad</h2>
        </div>
        <nav className="-mb-px flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
                ${activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="px-6 py-5">
        {activeTab === 'chat' && (
          <ChatCallsTab period={period} brokerId={selectedBrokerId} />
        )}
        {activeTab === 'voice' && (
          <VoiceCallsTab period={period} brokerId={selectedBrokerId} />
        )}
      </div>
    </div>
  );
}
