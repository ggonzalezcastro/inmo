import { useCostsStore } from '../store/costsStore';

export function CostOverviewCards() {
  const { summary, isLoading } = useCostsStore();

  if (isLoading && !summary) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white overflow-hidden shadow rounded-lg animate-pulse">
            <div className="px-4 py-5 sm:p-6">
              <div className="h-4 bg-gray-200 rounded w-24 mb-4" />
              <div className="h-8 bg-gray-200 rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!summary) return null;

  const cards = [
    {
      title: 'Costo total',
      value: `$${summary.total_cost_usd.toFixed(4)} USD`,
      sub: '—',
      aria: 'Costo total del período en dólares',
    },
    {
      title: 'Costo por lead',
      value:
        summary.cost_per_qualified_lead_usd != null
          ? `$${summary.cost_per_qualified_lead_usd.toFixed(6)} USD`
          : '—',
      sub: '—',
      aria: 'Costo promedio por lead calificado',
    },
    {
      title: 'Llamadas LLM',
      value: summary.total_calls.toLocaleString(),
      sub: '—',
      aria: 'Total de llamadas al LLM en el período',
    },
    {
      title: 'Latencia promedio',
      value: `${summary.avg_latency_ms.toFixed(0)} ms`,
      sub: '—',
      aria: 'Latencia promedio en milisegundos',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className="bg-white overflow-hidden shadow rounded-lg"
          title={card.aria}
        >
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">{card.title}</dt>
            <dd className="mt-1 text-2xl font-semibold text-gray-900">{card.value}</dd>
            {card.sub !== '—' && (
              <dd className="mt-1 text-xs text-gray-500">{card.sub}</dd>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
