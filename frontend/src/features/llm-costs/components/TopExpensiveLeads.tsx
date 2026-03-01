import { Link } from 'react-router-dom';
import { useCostsStore } from '../store/costsStore';
import * as costsApi from '../services/costsApi';
import type { CostPeriod } from '../types/costs.types';

export function TopExpensiveLeads() {
  const { outliers, isLoading, period, selectedBrokerId } = useCostsStore();

  const handleExportCsv = async () => {
    try {
      const { blob, filename } = await costsApi.exportCsv(
        period as CostPeriod,
        selectedBrokerId
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed', e);
    }
  };

  if (isLoading && !outliers) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <p className="text-gray-500">Cargando...</p>
      </div>
    );
  }

  const list = outliers?.outliers ?? [];

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-medium text-gray-900">
          Top 10 conversaciones más costosas
        </h2>
        <button
          type="button"
          onClick={handleExportCsv}
          className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm font-medium"
        >
          Exportar CSV
        </button>
      </div>
      {list.length === 0 ? (
        <p className="text-gray-500">No hay datos en el período seleccionado.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Lead
                </th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                  Turnos
                </th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                  Costo USD
                </th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                  Latencia avg (ms)
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Acción
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {list.map((row) => (
                <tr key={row.lead_id}>
                  <td className="px-4 py-2 text-sm text-gray-900">{row.lead_id}</td>
                  <td className="px-4 py-2 text-sm text-right text-gray-700">
                    {row.call_count}
                  </td>
                  <td className="px-4 py-2 text-sm text-right text-gray-700">
                    ${row.total_cost_usd.toFixed(6)}
                  </td>
                  <td className="px-4 py-2 text-sm text-right text-gray-700">
                    {row.avg_latency_ms.toFixed(0)}
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/chat?leadId=${row.lead_id}`}
                      className="text-blue-600 hover:underline text-sm"
                    >
                      Ver conversación
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
