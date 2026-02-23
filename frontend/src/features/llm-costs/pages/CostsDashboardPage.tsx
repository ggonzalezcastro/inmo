import { useEffect } from 'react';
import NavBar from '../../../components/NavBar';
import { useAuthStore } from '../../../store/authStore';
import { useCostsStore } from '../store/costsStore';
import { CostOverviewCards } from '../components/CostOverviewCards';
import { CostTrendChart } from '../components/CostTrendChart';
import { CostByProviderChart } from '../components/CostByProviderChart';
import { CostByBrokerChart } from '../components/CostByBrokerChart';
import { AlertsPanel } from '../components/AlertsPanel';
import { TopExpensiveLeads } from '../components/TopExpensiveLeads';
import { CostTable } from '../components/CostTable';

export function CostsDashboardPage() {
  const userRole = useAuthStore((s) => s.user?.role ?? '');
  const { fetchAll, error, period, setPeriod, selectedBrokerId } = useCostsStore();
  const isSuperadmin = userRole === 'superadmin';
  const shouldFetch = !isSuperadmin || selectedBrokerId != null;

  useEffect(() => {
    if (shouldFetch) fetchAll();
  }, [fetchAll, period, selectedBrokerId, shouldFetch]);

  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Costos LLM</h1>
          <PeriodSelector value={period} onChange={setPeriod} />
        </div>

        {isSuperadmin && selectedBrokerId == null && (
          <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md text-blue-800">
            Selecciona un broker en el gráfico &quot;Costos por broker&quot; para ver el detalle del dashboard.
          </div>
        )}

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
            {error}
          </div>
        )}

        <AlertsPanel />
        <CostOverviewCards />
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
          <CostTrendChart />
          <CostByProviderChart />
        </div>
        <div className="mt-8">
          <CostByBrokerChart />
        </div>
        <div className="mt-8">
          <TopExpensiveLeads />
        </div>
        <CostTable />
      </main>
    </div>
  );
}

function PeriodSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (p: 'today' | 'week' | 'month' | 'quarter') => void;
}) {
  const options: { label: string; period: 'today' | 'week' | 'month' | 'quarter' }[] = [
    { label: 'Hoy', period: 'today' },
    { label: '7 días', period: 'week' },
    { label: '30 días', period: 'month' },
    { label: '90 días', period: 'quarter' },
  ];
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as 'today' | 'week' | 'month' | 'quarter')}
      className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
    >
      {options.map((opt) => (
        <option key={opt.period} value={opt.period}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
