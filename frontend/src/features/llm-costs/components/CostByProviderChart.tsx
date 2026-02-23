import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useCostsStore } from '../store/costsStore';

const PROVIDER_COLORS: Record<string, string> = {
  gemini: '#10b981',
  claude: '#f59e0b',
  openai: '#3b82f6',
};

function getColor(provider: string): string {
  return PROVIDER_COLORS[provider.toLowerCase()] ?? '#6b7280';
}

export function CostByProviderChart() {
  const { summary, isLoading } = useCostsStore();

  if (isLoading && !summary) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-80 flex items-center justify-center">
        <p className="text-gray-500">Cargando...</p>
      </div>
    );
  }

  const costByProvider = summary?.cost_by_provider ?? {};
  const total = Object.values(costByProvider).reduce((a, b) => a + b, 0);
  const data = Object.entries(costByProvider).map(([provider, cost_usd]) => ({
    name: provider,
    value: cost_usd,
    percent: total > 0 ? ((cost_usd / total) * 100).toFixed(1) : '0',
  }));

  if (data.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Costos por provider</h2>
        <p className="text-gray-500">No hay datos en el período seleccionado.</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 mb-4">Costos por provider</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={2}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            >
              {data.map((entry, i) => (
                <Cell key={entry.name} fill={getColor(entry.name)} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(6)} USD`, 'Costo']}
            />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500">
            <th>Provider</th>
            <th className="text-right">Costo USD</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.name}>
              <td>
                <span
                  className="inline-block w-3 h-3 rounded-full mr-2"
                  style={{ backgroundColor: getColor(row.name) }}
                />
                {row.name}
              </td>
              <td className="text-right">${row.value.toFixed(6)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
