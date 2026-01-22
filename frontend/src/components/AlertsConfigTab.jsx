import { useState } from 'react';
import { brokerAPI } from '../services/api';

/**
 * AlertsConfigTab - Configuration tab for alerts and notifications
 */
export default function AlertsConfigTab({ config, onSave }) {
  const [formData, setFormData] = useState({
    on_hot_lead: config?.on_hot_lead ?? true,
    score_threshold: config?.score_threshold || 70,
    on_complete_profile: config?.on_complete_profile ?? true,
    email: config?.email || ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      // Update alerts config through lead config endpoint
      await brokerAPI.updateLeadConfig({
        alerts: formData
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
      onSave?.();
    } catch (error) {
      console.error('Error saving alerts config:', error);
      setError(error.response?.data?.detail || 'Error al guardar configuración');
    } finally {
      setSaving(false);
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
      
      {/* Alertas */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Alertas y Notificaciones</h2>
        
        {/* Hot Lead Alert */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.on_hot_lead}
              onChange={e => setFormData({...formData, on_hot_lead: e.target.checked})}
              className="mt-1 w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <div className="flex-1">
              <span className="block text-sm font-medium text-gray-900">
                Notificarme cuando un lead llegue a HOT
              </span>
              {formData.on_hot_lead && (
                <div className="mt-2">
                  <label className="block text-xs text-gray-600 mb-1">
                    Umbral de score:
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.score_threshold}
                    onChange={e => setFormData({...formData, score_threshold: parseInt(e.target.value) || 0})}
                    className="w-24 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="ml-2 text-xs text-gray-500">pts</span>
                </div>
              )}
            </div>
          </label>
        </div>
        
        {/* Complete Profile Alert */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.on_complete_profile}
              onChange={e => setFormData({...formData, on_complete_profile: e.target.checked})}
              className="mt-1 w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <div className="flex-1">
              <span className="block text-sm font-medium text-gray-900">
                Notificarme cuando un lead complete su perfil
              </span>
              <p className="text-xs text-gray-500 mt-1">
                Se enviará una notificación cuando el lead tenga todos los datos principales capturados
              </p>
            </div>
          </label>
        </div>
        
        {/* Email */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <label className="block text-sm font-medium text-gray-900 mb-2">
            📧 Email para notificaciones:
          </label>
          <input
            type="email"
            value={formData.email}
            onChange={e => setFormData({...formData, email: e.target.value})}
            placeholder="ventas@miinmobiliaria.cl"
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Las notificaciones se enviarán a este email cuando se cumplan las condiciones configuradas
          </p>
        </div>
      </section>
      
      {/* Guardar */}
      <div className="pt-4 border-t border-gray-200">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Guardando...' : 'Guardar Cambios'}
        </button>
      </div>
    </div>
  );
}


