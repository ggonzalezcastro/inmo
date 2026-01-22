import { useState } from 'react';
import { useLeadsStore } from '../store/leadsStore';
import { useAuthStore } from '../store/authStore';
import AssignmentDropdown from './AssignmentDropdown';


export default function LeadTable({ leads, loading, total, onAssignLead }) {
  const { pagination, setPagination, fetchLeads } = useLeadsStore();
  const { isAdmin } = useAuthStore();
  const [sortBy, setSortBy] = useState('score');
  
  const handleAssign = async (leadId, agentId) => {
    if (onAssignLead) {
      await onAssignLead(leadId, agentId);
    } else {
      // Fallback: actualizar directamente
      try {
        const { ticketAPI } = await import('../services/api');
        await ticketAPI.updateField(leadId, 'assigned_to', agentId);
        fetchLeads(); // Refresh leads
      } catch (error) {
        console.error('Error assigning lead:', error);
        alert('Error al asignar lead');
      }
    }
  };
  
  const getStatusColor = (status) => {
    const colors = {
      cold: 'bg-blue-100 text-blue-800',
      warm: 'bg-yellow-100 text-yellow-800',
      hot: 'bg-red-100 text-red-800',
      converted: 'bg-green-100 text-green-800',
      lost: 'bg-gray-100 text-gray-800',
    };
    return colors[status] || colors.cold;
  };
  
  const sortedLeads = [...leads].sort((a, b) => {
    if (sortBy === 'score') return b.lead_score - a.lead_score;
    if (sortBy === 'name') return (a.name || '').localeCompare(b.name || '');
    return 0;
  });
  
  const totalPages = Math.ceil(total / pagination.limit);
  const currentPage = Math.floor(pagination.skip / pagination.limit) + 1;
  
  return (
    <div className="mt-8 bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Nombre
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Teléfono
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Estado
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer" onClick={() => setSortBy('score')}>
              Score ↑↓
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Creado
            </th>
            {isAdmin() && (
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Asignado a
              </th>
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {loading ? (
            <tr>
              <td colSpan={isAdmin() ? 6 : 5} className="px-6 py-4 text-center">
                Cargando...
              </td>
            </tr>
          ) : sortedLeads.length === 0 ? (
            <tr>
              <td colSpan={isAdmin() ? 6 : 5} className="px-6 py-4 text-center">
                No hay leads
              </td>
            </tr>
          ) : (
            sortedLeads.map((lead) => (
              <tr key={lead.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {lead.name || '—'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {lead.phone}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(lead.status)}`}>
                    {lead.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  <div className="flex items-center">
                    <div className="w-full bg-gray-200 rounded-full h-2 max-w-xs">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${lead.lead_score}%` }}
                      ></div>
                    </div>
                    <span className="ml-2 text-xs font-semibold">
                      {Math.round(lead.lead_score)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {new Date(lead.created_at).toLocaleDateString()}
                </td>
                {isAdmin() && (
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <AssignmentDropdown 
                      lead={lead} 
                      onAssign={handleAssign}
                    />
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
      
      {/* Pagination */}
      <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
        <button
          onClick={() => setPagination({ skip: Math.max(0, pagination.skip - pagination.limit) })}
          disabled={currentPage === 1}
          className="px-3 py-1 border rounded-md text-sm disabled:opacity-50"
        >
          ← Anterior
        </button>
        
        <span className="text-sm text-gray-600">
          Página {currentPage} de {totalPages}
        </span>
        
        <button
          onClick={() => setPagination({ skip: pagination.skip + pagination.limit })}
          disabled={currentPage === totalPages}
          className="px-3 py-1 border rounded-md text-sm disabled:opacity-50"
        >
          Siguiente →
        </button>
      </div>
    </div>
  );
}

