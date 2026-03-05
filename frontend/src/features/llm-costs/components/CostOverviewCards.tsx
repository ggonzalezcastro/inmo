import { useCostsStore } from '../store/costsStore';

/** Format a USD cost for display. Uses smart scaling:
 *  < $0.01  → show in ¢ (cents) with 4 decimal places, e.g. "0.1194¢"
 *  >= $0.01 → show in $ with 4 decimal places, e.g. "$1.2345"
 */
function formatUSD(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) {
    return `${(usd * 100).toFixed(4)}¢`;
  }
  return `$${usd.toFixed(4)}`;
}

export function CostOverviewCards() {
  const { summary, isLoading } = useCostsStore();

  if (isLoading && !summary) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
        {[1, 2, 3, 4, 5].map((i) => (
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
      value: formatUSD(summary.total_cost_usd),
      sub: 'USD · 1¢ = $0.01',
      aria: 'Costo total del período en dólares',
    },
    {
      title: 'Costo por lead',
      value:
        summary.cost_per_qualified_lead_usd != null
          ? formatUSD(summary.cost_per_qualified_lead_usd)
          : '—',
      sub: 'por lead calificado',
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
    {
      title: 'Minutos de voz',
      value: `${summary.total_voice_minutes.toLocaleString()} min`,
      sub: 'llamadas de voz IA',
      aria: 'Total de minutos hablados en llamadas de voz',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
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
