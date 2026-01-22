import { useState } from 'react';
import { useLeadsStore } from '../store/leadsStore';


export default function LeadFilters({ onApply }) {
  const { setFilters, filters } = useLeadsStore();
  
  const [search, setSearch] = useState(filters.search);
  const [status, setStatus] = useState(filters.status);
  const [minScore, setMinScore] = useState(filters.minScore);
  const [maxScore, setMaxScore] = useState(filters.maxScore);
  
  const handleApply = () => {
    setFilters({
      search,
      status,
      minScore: parseFloat(minScore),
      maxScore: parseFloat(maxScore),
    });
    onApply();
  };
  
  const handleReset = () => {
    setSearch('');
    setStatus('');
    setMinScore(0);
    setMaxScore(100);
    setFilters({
      search: '',
      status: '',
      minScore: 0,
      maxScore: 100,
    });
    onApply();
  };
  
  return (
    <div className="mt-8 bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Filtros</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Búsqueda
          </label>
          <input
            type="text"
            placeholder="Nombre o teléfono"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border px-3 py-2"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Estado
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border px-3 py-2"
          >
            <option value="">Todos</option>
            <option value="cold">Cold</option>
            <option value="warm">Warm</option>
            <option value="hot">Hot</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Score Mín
          </label>
          <input
            type="number"
            min="0"
            max="100"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border px-3 py-2"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Score Máx
          </label>
          <input
            type="number"
            min="0"
            max="100"
            value={maxScore}
            onChange={(e) => setMaxScore(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border px-3 py-2"
          />
        </div>
      </div>
      
      <div className="mt-4 flex gap-2">
        <button
          onClick={handleApply}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Aplicar Filtros
        </button>
        <button
          onClick={handleReset}
          className="px-4 py-2 bg-gray-300 text-gray-800 rounded-md hover:bg-gray-400"
        >
          Limpiar
        </button>
      </div>
    </div>
  );
}

