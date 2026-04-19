import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { useAuthStore } from '../../../store/authStore';
import { useCostsStore } from '../store/costsStore';
import * as costsApi from '../services/costsApi';
import type { CostByBrokerItem, CostPeriod } from '../types/costs.types';

const BAR_COLORS = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'];

export function CostByBrokerChart() {
  const userRole = useAuthStore((s) => s.user?.role ?? '');
  const { period, setBrokerId, selectedBrokerId } = useCostsStore();
  const [brokers, setBrokers] = useState<CostByBrokerItem[]>([]);
  const [loading, setLoading] = useState(false);

  const isSuperadmin = userRole === 'superadmin';

  useEffect(() => {
    if (!isSuperadmin) return;
    setLoading(true);
    costsApi
      .getByBroker(period as CostPeriod)
      .then((res) => setBrokers(res.brokers ?? []))
      .catch(() => setBrokers([]))
      .finally(() => setLoading(false));
  }, [isSuperadmin, period]);

  const handleExportRanking = () => {
    const headers = ['Broker', 'Broker ID', 'Costo USD', 'Llamadas', 'Leads calificados', 'Costo por lead'];
    const rows = brokers.map((b) => [
      b.broker_name ?? '',
      b.broker_id,
      b.total_cost_usd.toFixed(6),
      b.total_calls,
      b.leads_qualified ?? '',
      b.cost_per_lead != null ? b.cost_per_lead.toFixed(6) : '',
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `costs_by_broker_${period}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!isSuperadmin) return null;

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Costos por broker</h2>
        <p className="text-gray-500">Cargando...</p>
      </div>
    );
  }

  const chartData = brokers.slice(0, 10).map((b) => ({
    name: b.broker_name ?? `Broker ${b.broker_id}`,
    broker_id: b.broker_id,
    cost_usd: b.total_cost_usd,
    total_calls: b.total_calls,
    leads_qualified: b.leads_qualified ?? 0,
    cost_per_lead: b.cost_per_lead ?? 0,
  }));

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-medium text-gray-900">Costos por broker (Top 10)</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExportRanking}
            className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm font-medium"
          >
            Exportar ranking CSV
          </button>
          {selectedBrokerId != null && (
            <button
              type="button"
              onClick={() => setBrokerId(null)}
              className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 text-sm font-medium"
            >
              Limpiar filtro
            </button>
          )}
        </div>
      </div>
      {chartData.length === 0 ? (
        <p className="text-gray-500">No hay datos en el período.</p>
      ) : (
        <>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tickFormatter={(v) => `$${v}`} />
                <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number, name: string) => {
                    if (name === 'cost_usd') return [`$${value.toFixed(6)}`, 'Costo USD'];
                    return [value, name];
                  }}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.name}
                />
                <Bar
                  dataKey="cost_usd"
                  name="Costo USD"
                  onClick={(data: unknown) => setBrokerId((data as { broker_id: number }).broker_id)}
                  cursor="pointer"
                >
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th>Broker</th>
                <th className="text-right">Leads calificados</th>
                <th className="text-right">Costo total</th>
                <th className="text-right">Costo por lead</th>
              </tr>
            </thead>
            <tbody>
              {chartData.map((row) => (
                <tr
                  key={row.broker_id}
                  className={selectedBrokerId === row.broker_id ? 'bg-blue-50' : ''}
                >
                  <td>
                    <button
                      type="button"
                      onClick={() => setBrokerId(row.broker_id)}
                      className="text-left font-medium text-blue-600 hover:underline"
                    >
                      {row.name}
                    </button>
                  </td>
                  <td className="text-right">{row.leads_qualified}</td>
                  <td className="text-right">${row.cost_usd.toFixed(6)}</td>
                  <td className="text-right">
                    {row.cost_per_lead > 0 ? `$${row.cost_per_lead.toFixed(6)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
