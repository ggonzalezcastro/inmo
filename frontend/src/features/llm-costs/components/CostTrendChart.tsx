import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useCostsStore } from '../store/costsStore';

export function CostTrendChart() {
  const { daily, isLoading } = useCostsStore();

  if (isLoading && !daily) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-80 flex items-center justify-center">
        <p className="text-gray-500">Cargando...</p>
      </div>
    );
  }

  const data = daily?.daily ?? [];
  const chartData = data.map((d) => ({
    date: d.date,
    cost_usd: Number(d.cost_usd.toFixed(6)),
    name: d.date,
  }));

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">Tendencia de costos</h2>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(6)} USD`, 'Costo']}
              labelFormatter={(label) => `Fecha: ${label}`}
            />
            <Line
              type="monotone"
              dataKey="cost_usd"
              stroke="#2563eb"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Costo USD"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
