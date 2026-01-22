import { useEffect, useState } from 'react';
import { useCampaignStore } from '../store/campaignStore';

/**
 * CampaignsList - List view for managing campaigns
 * 
 * Features:
 * - Table with all campaigns
 * - Filters: status, channel, trigger type
 * - Search by name
 * - Actions: edit, delete, duplicate, view stats
 */
export default function CampaignsList({ onCampaignClick, onCreateNew, canEdit = true }) {
  const {
    campaigns,
    loading,
    error,
    fetchCampaigns,
    deleteCampaign,
  } = useCampaignStore();

  const [filters, setFilters] = useState({
    status: '',
    channel: '',
    triggered_by: '',
    search: '',
  });

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleApplyFilters = () => {
    fetchCampaigns(filters);
  };

  const handleDelete = async (campaignId, e) => {
    e.stopPropagation();
    if (window.confirm('¿Estás seguro de eliminar esta campaña?')) {
      await deleteCampaign(campaignId);
      fetchCampaigns(filters);
    }
  };

  const handleDuplicate = async (campaignId, e) => {
    e.stopPropagation();
    const campaign = campaigns.find(c => c.id === campaignId);
    if (campaign) {
      // Create a copy with a new name
      const duplicated = {
        ...campaign,
        name: `${campaign.name} (Copia)`,
        status: 'draft',
      };
      delete duplicated.id;
      delete duplicated.created_at;
      delete duplicated.updated_at;
      // This would call createCampaign - for now just navigate to builder
      if (onCreateNew) {
        onCreateNew(duplicated);
      }
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      draft: { label: 'Borrador', color: 'bg-gray-100 text-gray-800' },
      active: { label: 'Activa', color: 'bg-green-100 text-green-800' },
      paused: { label: 'Pausada', color: 'bg-yellow-100 text-yellow-800' },
      completed: { label: 'Completada', color: 'bg-blue-100 text-blue-800' },
    };
    const statusInfo = statusMap[status] || statusMap.draft;
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${statusInfo.color}`}>
        {statusInfo.label}
      </span>
    );
  };

  const getChannelBadge = (channel) => {
    const channelMap = {
      telegram: { label: 'Telegram', color: 'bg-blue-100 text-blue-800' },
      call: { label: 'Llamada', color: 'bg-purple-100 text-purple-800' },
      email: { label: 'Email', color: 'bg-gray-100 text-gray-800' },
      whatsapp: { label: 'WhatsApp', color: 'bg-green-100 text-green-800' },
    };
    const channelInfo = channelMap[channel] || channelMap.telegram;
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${channelInfo.color}`}>
        {channelInfo.label}
      </span>
    );
  };

  const filteredCampaigns = campaigns.filter((campaign) => {
    if (filters.status && campaign.status !== filters.status) return false;
    if (filters.channel && campaign.channel !== filters.channel) return false;
    if (filters.triggered_by && campaign.triggered_by !== filters.triggered_by) return false;
    if (filters.search && !campaign.name.toLowerCase().includes(filters.search.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Campañas</h2>
          {canEdit && (
            <button
              onClick={onCreateNew}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              + Nueva Campaña
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Buscar
            </label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              placeholder="Nombre de campaña..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Estado
            </label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="draft">Borrador</option>
              <option value="active">Activa</option>
              <option value="paused">Pausada</option>
              <option value="completed">Completada</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Canal
            </label>
            <select
              value={filters.channel}
              onChange={(e) => handleFilterChange('channel', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="telegram">Telegram</option>
              <option value="call">Llamada</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Trigger
            </label>
            <select
              value={filters.triggered_by}
              onChange={(e) => handleFilterChange('triggered_by', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="manual">Manual</option>
              <option value="lead_score">Score</option>
              <option value="stage_change">Etapa</option>
              <option value="inactivity">Inactividad</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleApplyFilters}
              className="w-full px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium"
            >
              Aplicar
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-6 py-4 bg-red-50 border-l-4 border-red-400">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-500">
            Cargando campañas...
          </div>
        ) : filteredCampaigns.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No hay campañas que coincidan con los filtros
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Nombre
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Canal
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Trigger
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Leads
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tasa éxito
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Creada
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredCampaigns.map((campaign) => (
                <tr
                  key={campaign.id}
                  onClick={() => onCampaignClick?.(campaign)}
                  className="hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{campaign.name}</div>
                    {campaign.description && (
                      <div className="text-sm text-gray-500">{campaign.description}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getChannelBadge(campaign.channel)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getStatusBadge(campaign.status)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {campaign.triggered_by === 'manual' && 'Manual'}
                    {(campaign.triggered_by === 'lead_score' || campaign.triggered_by === 'score') && 'Score'}
                    {(campaign.triggered_by === 'stage_change' || campaign.triggered_by === 'stage') && 'Etapa'}
                    {campaign.triggered_by === 'inactivity' && 'Inactividad'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {/* This would come from stats endpoint */}
                    N/A
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {/* This would come from stats endpoint */}
                    N/A
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {campaign.created_at
                      ? new Date(campaign.created_at).toLocaleDateString()
                      : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onCampaignClick?.(campaign);
                        }}
                        className="text-blue-600 hover:text-blue-900"
                        title="Editar"
                      >
                        Editar
                      </button>
                      <button
                        onClick={(e) => handleDuplicate(campaign.id, e)}
                        className="text-gray-600 hover:text-gray-900"
                        title="Duplicar"
                      >
                        Duplicar
                      </button>
                      <button
                        onClick={(e) => handleDelete(campaign.id, e)}
                        className="text-red-600 hover:text-red-900"
                        title="Eliminar"
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

