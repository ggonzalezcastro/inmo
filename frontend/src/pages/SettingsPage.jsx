import { useState, useEffect } from 'react';
import { brokerAPI } from '../services/api';
import NavBar from '../components/NavBar';
import AgentConfigTab from '../components/AgentConfigTab';
import LeadConfigTab from '../components/LeadConfigTab';
import AlertsConfigTab from '../components/AlertsConfigTab';

/**
 * SettingsPage - Main settings page with tabs for Agent, Lead Scoring, and Alerts
 * Only accessible by Admin users
 */
export default function SettingsPage() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('agent');
  const [error, setError] = useState(null);
  
  useEffect(() => {
    loadConfig();
  }, []);
  
  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await brokerAPI.getConfig();
      setConfig(response.data);
    } catch (error) {
      console.error('Error loading config:', error);
      
      // Handle different error types
      if (error.code === 'ERR_NETWORK' || error.message?.includes('CORS')) {
        setError('Error de conexión con el servidor. Verifica que el backend esté corriendo y que CORS esté configurado correctamente.');
      } else if (error.response?.status === 500) {
        setError('Error interno del servidor. El usuario puede no tener broker_id asignado o hay un problema en el backend.');
      } else if (error.response?.status === 404) {
        setError('Usuario no pertenece a un broker. Contacta al administrador.');
      } else {
        setError(error.response?.data?.detail || 'Error al cargar configuración');
      }
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <p className="text-gray-500">Cargando configuración...</p>
        </div>
      </div>
    );
  }
  
  if (error && !config) {
    return (
      <div className="min-h-screen bg-gray-100">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={loadConfig}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Reintentar
            </button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">⚙️ Configuración</h1>
        
        {/* Tabs */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('agent')}
                className={`flex-1 px-6 py-4 text-sm font-medium text-center border-b-2 transition-colors ${
                  activeTab === 'agent'
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🤖 Agente
              </button>
              <button
                onClick={() => setActiveTab('leads')}
                className={`flex-1 px-6 py-4 text-sm font-medium text-center border-b-2 transition-colors ${
                  activeTab === 'leads'
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                📊 Calificación
              </button>
              <button
                onClick={() => setActiveTab('alerts')}
                className={`flex-1 px-6 py-4 text-sm font-medium text-center border-b-2 transition-colors ${
                  activeTab === 'alerts'
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🔔 Alertas
              </button>
            </nav>
          </div>
          
          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'agent' && (
              <AgentConfigTab 
                config={config?.prompt_config} 
                onSave={loadConfig}
              />
            )}
            {activeTab === 'leads' && (
              <LeadConfigTab 
                config={config?.lead_config}
                onSave={loadConfig}
              />
            )}
            {activeTab === 'alerts' && (
              <AlertsConfigTab 
                config={config?.lead_config?.alerts}
                onSave={loadConfig}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


