import { useState } from 'react';
import { brokerAPI } from '../services/api';

/**
 * AgentConfigTab - Configuration tab for AI Agent settings
 */
export default function AgentConfigTab({ config, onSave }) {
  const [formData, setFormData] = useState({
    agent_name: config?.agent_name || 'Sofía',
    agent_role: config?.agent_role || 'asesora inmobiliaria',
    business_context: config?.business_context || '',
    behavior_rules: config?.behavior_rules || '',
    restrictions: config?.restrictions || '',
    enable_appointment_booking: config?.enable_appointment_booking ?? true
  });
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await brokerAPI.updatePromptConfig(formData);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
      onSave?.();
    } catch (error) {
      console.error('Error saving config:', error);
      setError(error.response?.data?.detail || 'Error al guardar configuración');
    } finally {
      setSaving(false);
    }
  };
  
  const handlePreview = async () => {
    try {
      const response = await brokerAPI.getPromptPreview();
      setPreview(response.data.prompt);
      setShowPreview(true);
    } catch (error) {
      console.error('Error getting preview:', error);
      setError('Error al generar vista previa');
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-md">
          ✅ Configuración guardada correctamente
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md">
          ❌ {error}
        </div>
      )}
      
      {/* Identidad */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Identidad del Agente</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del agente</label>
            <input
              type="text"
              value={formData.agent_name}
              onChange={e => setFormData({...formData, agent_name: e.target.value})}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: Sofía"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
            <input
              type="text"
              value={formData.agent_role}
              onChange={e => setFormData({...formData, agent_role: e.target.value})}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej: asesora inmobiliaria"
            />
          </div>
        </div>
      </section>
      
      {/* Contexto */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Contexto del Negocio</h2>
        <textarea
          value={formData.business_context}
          onChange={e => setFormData({...formData, business_context: e.target.value})}
          placeholder="Describe qué ofrece tu inmobiliaria, en qué zonas trabajan, qué tipo de propiedades manejan..."
          rows={5}
          className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-sm text-gray-500 mt-1">
          💡 Ej: "Somos especialistas en propiedades de lujo en Las Condes y Vitacura"
        </p>
      </section>
      
      {/* Reglas */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Reglas de Comunicación</h2>
        <textarea
          value={formData.behavior_rules}
          onChange={e => setFormData({...formData, behavior_rules: e.target.value})}
          placeholder="- Responde de forma formal&#10;- Usa 'usted' en lugar de 'tú'&#10;- Máximo 2 oraciones por mensaje"
          rows={4}
          className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </section>
      
      {/* Restricciones */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Restricciones</h2>
        <textarea
          value={formData.restrictions}
          onChange={e => setFormData({...formData, restrictions: e.target.value})}
          placeholder="- NUNCA menciones competidores&#10;- NO des precios exactos sin autorización"
          rows={4}
          className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </section>
      
      {/* Herramientas */}
      <section>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.enable_appointment_booking}
            onChange={e => setFormData({...formData, enable_appointment_booking: e.target.checked})}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700">
            Permitir agendar citas automáticamente
          </span>
        </label>
      </section>
      
      {/* Acciones */}
      <div className="flex gap-4 pt-4 border-t border-gray-200">
        <button
          onClick={handlePreview}
          className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Vista Previa del Prompt
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Guardando...' : 'Guardar Cambios'}
        </button>
      </div>
      
      {/* Modal de Preview */}
      {showPreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] overflow-auto shadow-xl">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold text-gray-900">Preview del System Prompt</h3>
                <button
                  onClick={() => setShowPreview(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <pre className="bg-gray-100 p-4 rounded text-sm whitespace-pre-wrap font-mono overflow-auto">
                {preview}
              </pre>
              <button
                onClick={() => setShowPreview(false)}
                className="mt-4 px-4 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


