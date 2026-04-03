import { useEffect, useState, Fragment } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/lib/utils';
import {
  MessageSquare, Phone, DollarSign, Zap, Clock, TrendingUp,
  CheckCircle, PhoneOff,
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { useAuthStore } from '../../../store/authStore';
import { useCostsStore } from '../store/costsStore';
import { AlertsPanel } from '../components/AlertsPanel';
import { TopExpensiveLeads } from '../components/TopExpensiveLeads';
import * as costsApi from '../services/costsApi';
import type { LLMUsage, VoiceCallItem, VoiceSummary, CostPeriod } from '../types/costs.types';

// ─── Design tokens (matches system) ──────────────────────────────────────────
const BLUE = '#1A56DB';
const BORDER = '#D1D9E6';

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatUSD(usd: number | null | undefined): string {
  if (usd == null) return '—';
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `${(usd * 100).toFixed(4)}¢`;
  return `$${usd.toFixed(4)}`;
}
function fmtDuration(s: number | null): string {
  if (s == null) return '—';
  const m = Math.floor(s / 60); const sec = Math.round(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}
function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}
function fmtShortDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
}

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, icon: Icon, accent = false,
}: {
  label: string; value: string; sub?: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  accent?: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-3 rounded-xl p-6 flex-1 shadow-sm ${
        accent ? 'bg-[#1A56DB]' : 'bg-white border border-[#D1D9E6]'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold uppercase tracking-[1.2px] ${accent ? 'text-[#93B4F5]' : 'text-[#9CA3AF]'}`}>
          {label}
        </span>
        <Icon size={16} className={accent ? 'text-[#93B4F5]' : 'text-[#9CA3AF]'} />
      </div>
      <span className={`text-[28px] font-bold leading-none tabular-nums ${accent ? 'text-white' : 'text-[#111827]'}`}>
        {value}
      </span>
      {sub && (
        <span className={`text-[12px] ${accent ? 'text-[#93B4F5]' : 'text-[#1A56DB]'}`}>{sub}</span>
      )}
    </div>
  );
}

// ─── Chart card wrapper ───────────────────────────────────────────────────────
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-[#D1D9E6] rounded-xl p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-[#111827] mb-4">{title}</h3>
      {children}
    </div>
  );
}

// ─── Pagination ───────────────────────────────────────────────────────────────
function Pagination({ page, totalPages, total, onPageChange }: {
  page: number; totalPages: number; total: number; onPageChange: (p: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between border-t border-[#D1D9E6] pt-4">
      <p className="text-xs text-[#9CA3AF]">Página {page} de {totalPages} · {total.toLocaleString()} registros</p>
      <div className="flex gap-2">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}
          className="px-3 py-1.5 rounded-lg border border-[#D1D9E6] text-sm text-[#374151] hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          ← Anterior
        </button>
        <button type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}
          className="px-3 py-1.5 rounded-lg border border-[#D1D9E6] text-sm text-[#374151] hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          Siguiente →
        </button>
      </div>
    </div>
  );
}

// ─── Chat Tab ─────────────────────────────────────────────────────────────────
function ChatTab({ period, brokerId }: { period: string; brokerId: number | null }) {
  const { summary, daily, outliers, isLoading } = useCostsStore();
  const [items, setItems] = useState<LLMUsage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [callsLoading, setCallsLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const PAGE_SIZE = 50;

  useEffect(() => { setPage(1); }, [period, brokerId]);
  useEffect(() => {
    setCallsLoading(true);
    costsApi.getCalls({ page, limit: PAGE_SIZE, broker_id: brokerId ?? undefined })
      .then(r => { setItems(r.items as LLMUsage[]); setTotal(r.total); })
      .catch(() => { setItems([]); setTotal(0); })
      .finally(() => setCallsLoading(false));
  }, [page, brokerId, period]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const chartData = (daily?.daily ?? []).map(d => ({ date: fmtShortDate(d.date), costo: Number(d.cost_usd.toFixed(6)) }));

  // Call type pie
  const callTypeData = Object.entries(summary?.cost_by_call_type ?? {}).map(([k, v]) => ({
    name: k === 'chat_response' ? 'Chat' : k === 'qualification' ? 'Calificación' : k,
    value: v,
  }));
  const PIE_COLORS = ['#1A56DB', '#10B981', '#F59E0B', '#8B5CF6'];

  const CALL_LABELS: Record<string, string> = { chat_response: 'Chat', qualification: 'Calificación', tool_call: 'Herramienta' };

  return (
    <div className="flex flex-col gap-6">
      <AlertsPanel />

      {/* KPI Cards */}
      <div className="flex gap-4">
        <StatCard label="Costo total" value={formatUSD(summary?.total_cost_usd ?? 0)} sub="USD en el período" icon={DollarSign} accent />
        <StatCard label="Costo por lead" value={formatUSD(summary?.cost_per_qualified_lead_usd ?? null)} sub="por lead calificado" icon={TrendingUp} />
        <StatCard label="Llamadas LLM" value={(summary?.total_calls ?? 0).toLocaleString()} sub={`${summary?.fallback_calls ?? 0} fallbacks`} icon={Zap} />
        <StatCard label="Latencia promedio" value={`${(summary?.avg_latency_ms ?? 0).toFixed(0)} ms`} icon={Clock} />
      </div>

      {/* Charts */}
      {isLoading && !summary ? (
        <div className="grid grid-cols-2 gap-6">
          {[1, 2].map(i => <div key={i} className="bg-white border border-[#D1D9E6] rounded-xl h-64 animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard title="Tendencia de costos">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9CA3AF' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} tickFormatter={v => `$${v}`} />
                  <Tooltip formatter={(v: number) => [`$${v.toFixed(6)}`, 'Costo']} />
                  <Line type="monotone" dataKey="costo" stroke={BLUE} strokeWidth={2} dot={{ r: 3, fill: BLUE }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
          <ChartCard title="Distribución por tipo">
            {callTypeData.length === 0 ? (
              <p className="text-sm text-[#9CA3AF] py-8 text-center">Sin datos</p>
            ) : (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={callTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3}>
                      {callTypeData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => formatUSD(v)} />
                    <Legend iconType="circle" iconSize={8} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </ChartCard>
        </div>
      )}

      {/* Top expensive leads */}
      <TopExpensiveLeads />

      {/* Paginated calls table */}
      <div className="bg-white border border-[#D1D9E6] rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-[#111827]">Todas las llamadas</h3>
          <span className="text-xs text-[#9CA3AF]">{total.toLocaleString()} registros</span>
        </div>
        {callsLoading ? (
          <div className="py-10 flex justify-center"><div className="w-5 h-5 border-2 border-[#1A56DB] border-t-transparent rounded-full animate-spin" /></div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-[#9CA3AF]">No hay llamadas en este período.</p>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-[#D1D9E6]">
                    {['Fecha', 'Lead', 'Tipo', 'Tokens', 'Costo', 'Latencia', 'Estado', ''].map(h => (
                      <th key={h} className={`px-6 py-3 text-[10px] font-bold uppercase tracking-[1px] text-[#9CA3AF] ${h === 'Tokens' || h === 'Costo' || h === 'Latencia' ? 'text-right' : 'text-left'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F3F4F6]">
                  {items.map(row => (
                    <Fragment key={row.id}>
                      <tr className={`hover:bg-gray-50/60 transition-colors ${row.error ? 'bg-red-50/40' : ''}`}>
                        <td className="px-6 py-3 text-xs text-[#6B7280] whitespace-nowrap">{row.created_at ? fmtDate(row.created_at) : '—'}</td>
                        <td className="px-6 py-3 text-sm">
                          {row.lead_id ? <Link to={`/chat?leadId=${row.lead_id}`} className="text-[#1A56DB] hover:underline font-medium">#{row.lead_id}</Link> : <span className="text-[#9CA3AF]">—</span>}
                        </td>
                        <td className="px-6 py-3 text-xs text-[#374151]">{CALL_LABELS[row.call_type] ?? row.call_type ?? '—'}</td>
                        <td className="px-6 py-3 text-xs text-right text-[#374151] tabular-nums">
                          {row.input_tokens != null || row.output_tokens != null ? ((row.input_tokens ?? 0) + (row.output_tokens ?? 0)).toLocaleString() : '—'}
                        </td>
                        <td className="px-6 py-3 text-xs text-right font-semibold text-[#111827] tabular-nums">{formatUSD(row.estimated_cost_usd)}</td>
                        <td className="px-6 py-3 text-xs text-right text-[#6B7280] tabular-nums">{row.latency_ms != null ? `${row.latency_ms} ms` : '—'}</td>
                        <td className="px-6 py-3">
                          {row.error
                            ? <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-red-50 text-red-700">Error</span>
                            : <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-emerald-50 text-emerald-700">OK</span>}
                        </td>
                        <td className="px-6 py-3 text-right">
                          {row.error && (
                            <button type="button" onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
                              className="text-[11px] text-[#1A56DB] hover:underline">
                              {expandedId === row.id ? 'Cerrar' : 'Ver error'}
                            </button>
                          )}
                        </td>
                      </tr>
                      {expandedId === row.id && row.error && (
                        <tr><td colSpan={8} className="px-6 py-3 bg-red-50 text-xs text-red-800 font-mono">{row.error}</td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} totalPages={totalPages} total={total} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}

// ─── Voice Tab ────────────────────────────────────────────────────────────────
const VOICE_STATUS_BADGE: Record<string, string> = {
  completed: 'bg-emerald-50 text-emerald-700',
  answered: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
  no_answer: 'bg-amber-50 text-amber-700',
  busy: 'bg-amber-50 text-amber-700',
  initiated: 'bg-blue-50 text-blue-700',
  ringing: 'bg-blue-50 text-blue-700',
  cancelled: 'bg-gray-100 text-gray-600',
};
const VOICE_STATUS_LABELS: Record<string, string> = {
  completed: 'Completada', answered: 'Atendida', failed: 'Fallida',
  no_answer: 'No contestó', busy: 'Ocupado', initiated: 'Iniciada',
  ringing: 'Sonando', cancelled: 'Cancelada',
};

function VoiceTab({ period, brokerId }: { period: string; brokerId: number | null }) {
  const [summary, setSummary] = useState<VoiceSummary | null>(null);
  const [items, setItems] = useState<VoiceCallItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const PAGE_SIZE = 50;

  useEffect(() => { setPage(1); }, [period, brokerId]);
  useEffect(() => {
    setLoading(true);
    const params = { period: period as CostPeriod, broker_id: brokerId ?? undefined };
    Promise.all([
      costsApi.getVoiceSummary(params),
      costsApi.getVoiceCalls({ ...params, page, limit: PAGE_SIZE }),
    ]).then(([s, c]) => {
      setSummary(s);
      setItems(c.items);
      setTotal(c.total);
    }).catch(() => {
      setSummary(null); setItems([]); setTotal(0);
    }).finally(() => setLoading(false));
  }, [page, brokerId, period]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const barData = (summary?.daily ?? []).map(d => ({ date: fmtShortDate(d.date), llamadas: d.calls, minutos: d.minutes }));
  const statusData = summary ? [
    { name: 'Completadas', value: summary.completed_calls, color: '#10B981' },
    { name: 'Fallidas', value: summary.failed_calls, color: '#EF4444' },
    { name: 'Otras', value: Math.max(0, summary.total_calls - summary.completed_calls - summary.failed_calls), color: '#9CA3AF' },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="flex flex-col gap-6">
      {/* KPI Cards */}
      <div className="flex gap-4">
        <StatCard label="Minutos totales" value={loading ? '…' : `${summary?.total_minutes ?? 0} min`} sub="hablados en el período" icon={Phone} accent />
        <StatCard label="Llamadas completadas" value={loading ? '…' : (summary?.completed_calls ?? 0).toString()} icon={CheckCircle} />
        <StatCard label="Duración promedio" value={loading ? '…' : fmtDuration(summary?.avg_duration_seconds ?? null)} icon={Clock} />
        <StatCard label="Fallidas / sin respuesta" value={loading ? '…' : (summary?.failed_calls ?? 0).toString()} icon={PhoneOff} />
      </div>

      {/* Charts */}
      {loading ? (
        <div className="grid grid-cols-2 gap-6">
          {[1, 2].map(i => <div key={i} className="bg-white border border-[#D1D9E6] rounded-xl h-64 animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard title="Llamadas por día">
            {barData.length === 0 ? <p className="text-sm text-[#9CA3AF] py-8 text-center">Sin datos</p> : (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9CA3AF' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} />
                    <Tooltip />
                    <Bar dataKey="llamadas" fill={BLUE} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </ChartCard>
          <ChartCard title="Distribución por estado">
            {statusData.length === 0 ? <p className="text-sm text-[#9CA3AF] py-8 text-center">Sin datos</p> : (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3}>
                      {statusData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip />
                    <Legend iconType="circle" iconSize={8} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </ChartCard>
        </div>
      )}

      {/* Calls table */}
      <div className="bg-white border border-[#D1D9E6] rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-[#111827]">Todas las llamadas</h3>
          <span className="text-xs text-[#9CA3AF]">{total.toLocaleString()} registros</span>
        </div>
        {loading ? (
          <div className="py-10 flex justify-center"><div className="w-5 h-5 border-2 border-[#1A56DB] border-t-transparent rounded-full animate-spin" /></div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-[#9CA3AF]">No hay llamadas de voz en este período.</p>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-[#D1D9E6]">
                    {['Fecha', 'Lead', 'Teléfono', 'Duración', 'Estado'].map(h => (
                      <th key={h} className={`px-6 py-3 text-[10px] font-bold uppercase tracking-[1px] text-[#9CA3AF] ${h === 'Duración' ? 'text-right' : 'text-left'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F3F4F6]">
                  {items.map(row => (
                    <tr key={row.id} className="hover:bg-gray-50/60 transition-colors">
                      <td className="px-6 py-3 text-xs text-[#6B7280] whitespace-nowrap">{row.created_at ? fmtDate(row.created_at) : '—'}</td>
                      <td className="px-6 py-3 text-sm">
                        {row.lead_id ? <Link to={`/chat?leadId=${row.lead_id}`} className="text-[#1A56DB] hover:underline font-medium">#{row.lead_id}</Link> : <span className="text-[#9CA3AF]">—</span>}
                      </td>
                      <td className="px-6 py-3 text-xs text-[#374151]">{row.phone_number ?? '—'}</td>
                      <td className="px-6 py-3 text-xs text-right font-semibold text-[#111827] tabular-nums">{fmtDuration(row.duration_seconds)}</td>
                      <td className="px-6 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${VOICE_STATUS_BADGE[row.status] ?? 'bg-gray-100 text-gray-600'}`}>
                          {VOICE_STATUS_LABELS[row.status] ?? row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} totalPages={totalPages} total={total} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function CostsDashboardPage() {
  const userRole = useAuthStore((s) => s.user?.role ?? '');
  const { fetchAll, error, period, setPeriod, selectedBrokerId } = useCostsStore();
  const isSuperadmin = userRole === 'superadmin';
  const [activeTab, setActiveTab] = useState<'chat' | 'voice'>('chat');

  // Superadmin sees all brokers by default (no broker_id required)
  useEffect(() => {
    fetchAll();
  }, [fetchAll, period, selectedBrokerId]);

  const tabs = [
    { id: 'chat' as const, label: 'Chat IA', icon: MessageSquare },
    { id: 'voice' as const, label: 'Llamadas de Voz', icon: Phone },
  ];

  return (
    <div className="flex flex-col gap-0 p-10 h-full">
      <div className="max-w-7xl w-full mx-auto flex flex-col gap-6">
        {/* Header */}
        <div className="mb-2">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-[1.4375rem] font-bold text-[#111827] tracking-tight leading-tight">Costos LLM</h1>
              <p className="text-[13px] text-[#6B7280] mt-0.5">Monitorea el uso y costo de todos los canales de IA</p>
            </div>
            <PeriodSelector value={period} onChange={setPeriod} />
          </div>
          <div className="mt-4 h-px bg-[#D1D9E6]" />
        </div>

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
        )}

        {/* Tab bar */}
        <div className="relative flex gap-1 border-b border-[#D1D9E6]">
          {tabs.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors relative',
                  active
                    ? 'text-[#1A56DB]'
                    : 'text-[#6B7280] hover:text-[#374151]'
                )}
              >
                {active && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1A56DB] rounded-full" />
                )}
                <Icon size={15} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {activeTab === 'chat' && <ChatTab period={period} brokerId={selectedBrokerId} />}
        {activeTab === 'voice' && <VoiceTab period={period} brokerId={selectedBrokerId} />}
      </div>
    </div>
  );
}

function PeriodSelector({ value, onChange }: { value: string; onChange: (p: CostPeriod) => void }) {
  const options: { label: string; period: CostPeriod }[] = [
    { label: 'Hoy', period: 'today' },
    { label: '7 días', period: 'week' },
    { label: '30 días', period: 'month' },
    { label: '90 días', period: 'quarter' },
  ];
  return (
    <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-[#E2EAF4]">
      {options.map(opt => (
        <button
          key={opt.period}
          type="button"
          onClick={() => onChange(opt.period)}
          className={cn(
            'px-3 py-1.5 text-[12px] font-medium rounded-md transition-all',
            value === opt.period
              ? 'bg-white text-[#1A56DB] shadow-sm font-semibold'
              : 'text-[#6B7280] hover:text-[#374151]'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
