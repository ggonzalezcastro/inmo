import { useEffect, useState } from 'react';
import { useTemplateStore } from '../store/templateStore';

/**
 * TemplateManager - Manage message templates
 * 
 * Features:
 * - CRUD operations for templates
 * - Filter by channel and agent type
 * - Preview rendered template
 * - Variable hints
 */
export default function TemplateManager() {
  const {
    templates,
    selectedTemplate,
    loading,
    error,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    renderTemplate,
  } = useTemplateStore();

  const [filters, setFilters] = useState({
    channel: '',
    agent_type: '',
    search: '',
  });

  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [previewVariables, setPreviewVariables] = useState({});
  const [previewText, setPreviewText] = useState('');

  const [formData, setFormData] = useState({
    name: '',
    channel: 'telegram',
    agent_type: 'perfilador',
    content: '',
  });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleOpenEditor = (template = null) => {
    if (template) {
      setEditingTemplate(template);
      setFormData({
        name: template.name || '',
        channel: template.channel || 'telegram',
        agent_type: template.agent_type || 'perfilador',
        content: template.content || template.message_text || '',
      });
    } else {
      setEditingTemplate(null);
      setFormData({
        name: '',
        channel: 'telegram',
        agent_type: 'perfilador',
        content: '',
      });
    }
    setShowEditor(true);
  };

  const handleCloseEditor = () => {
    setShowEditor(false);
    setEditingTemplate(null);
    setFormData({
      name: '',
      channel: 'telegram',
      agent_type: 'perfilador',
      content: '',
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.content.trim()) {
      return;
    }

    try {
      if (editingTemplate) {
        await updateTemplate(editingTemplate.id, formData);
      } else {
        await createTemplate(formData);
      }
      handleCloseEditor();
      fetchTemplates();
    } catch (error) {
      console.error('Error saving template:', error);
    }
  };

  const handleDelete = async (templateId) => {
    if (window.confirm('¿Estás seguro de eliminar esta plantilla?')) {
      await deleteTemplate(templateId);
      fetchTemplates();
    }
  };

  const handlePreview = async () => {
    if (!formData.content) return;
    
    // Extract variables from template
    const variableMatches = formData.content.match(/\{\{(\w+)\}\}/g) || [];
    const variables = {};
    variableMatches.forEach((match) => {
      const varName = match.replace(/\{\{|\}\}/g, '');
      if (!variables[varName]) {
        variables[varName] = previewVariables[varName] || `[${varName}]`;
      }
    });

    // Simple preview (replace variables)
    let preview = formData.content;
    Object.entries(variables).forEach(([key, value]) => {
      preview = preview.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value);
    });
    setPreviewText(preview);
  };

  const extractVariables = (content) => {
    const matches = content.match(/\{\{(\w+)\}\}/g) || [];
    return [...new Set(matches.map((m) => m.replace(/\{\{|\}\}/g, '')))];
  };

  const filteredTemplates = templates.filter((template) => {
    if (filters.channel && template.channel !== filters.channel) return false;
    if (filters.agent_type && template.agent_type !== filters.agent_type) return false;
    if (filters.search && !template.name.toLowerCase().includes(filters.search.toLowerCase())) {
      return false;
    }
    return true;
  });

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

  const getAgentTypeBadge = (agentType) => {
    const typeMap = {
      perfilador: { label: 'Perfilador', color: 'bg-blue-100 text-blue-800' },
      calificador: { label: 'Calificador Financiero', color: 'bg-yellow-100 text-yellow-800' },
      agendador: { label: 'Agendador', color: 'bg-green-100 text-green-800' },
      seguimiento: { label: 'Seguimiento', color: 'bg-purple-100 text-purple-800' },
    };
    const typeInfo = typeMap[agentType] || typeMap.perfilador;
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${typeInfo.color}`}>
        {typeInfo.label}
      </span>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Plantillas de Mensajes</h2>
          <button
            onClick={() => handleOpenEditor()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
          >
            + Nueva Plantilla
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Buscar
            </label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              placeholder="Nombre de plantilla..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
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
              Tipo de agente
            </label>
            <select
              value={filters.agent_type}
              onChange={(e) => handleFilterChange('agent_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="perfilador">Perfilador</option>
              <option value="calificador">Calificador Financiero</option>
              <option value="agendador">Agendador</option>
              <option value="seguimiento">Seguimiento</option>
            </select>
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
            Cargando plantillas...
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No hay plantillas que coincidan con los filtros
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
                  Tipo de agente
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Variables
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
              {filteredTemplates.map((template) => {
                const variables = extractVariables(template.content || template.message_text || '');
                return (
                  <tr key={template.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{template.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getChannelBadge(template.channel)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getAgentTypeBadge(template.agent_type)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {variables.length > 0 ? (
                          variables.map((varName) => (
                            <span
                              key={varName}
                              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800"
                            >
                              {`{{${varName}}}`}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-gray-500">Sin variables</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {template.created_at
                        ? new Date(template.created_at).toLocaleDateString()
                        : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleOpenEditor(template)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDelete(template.id)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Editor Modal */}
      {showEditor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  {editingTemplate ? 'Editar Plantilla' : 'Nueva Plantilla'}
                </h3>
                <button
                  onClick={handleCloseEditor}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
            </div>

            <form onSubmit={handleSave} className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Canal *
                </label>
                <select
                  value={formData.channel}
                  onChange={(e) => setFormData({ ...formData, channel: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="telegram">Telegram</option>
                  <option value="call">Llamada</option>
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tipo de agente *
                </label>
                <select
                  value={formData.agent_type}
                  onChange={(e) => setFormData({ ...formData, agent_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="perfilador">Perfilador</option>
                  <option value="calificador">Calificador Financiero</option>
                  <option value="agendador">Agendador</option>
                  <option value="seguimiento">Seguimiento</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contenido *
                </label>
                <textarea
                  value={formData.content}
                  onChange={(e) => {
                    setFormData({ ...formData, content: e.target.value });
                    handlePreview();
                  }}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  placeholder="Escribe el mensaje. Usa {{variable}} para variables. Ej: Hola {{name}}, tu presupuesto es {{budget}}"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  Variables disponibles: name, phone, email, budget, timeline, location, etc.
                </p>
              </div>

              {/* Preview */}
              {previewText && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Vista previa
                  </label>
                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-md">
                    <p className="text-sm whitespace-pre-wrap">{previewText}</p>
                  </div>
                </div>
              )}

              {/* Variables used */}
              {extractVariables(formData.content).length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Variables usadas
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {extractVariables(formData.content).map((varName) => (
                      <span
                        key={varName}
                        className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800"
                      >
                        {`{{${varName}}}`}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={handleCloseEditor}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  {editingTemplate ? 'Actualizar' : 'Crear'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


