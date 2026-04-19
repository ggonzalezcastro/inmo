import { useState, useEffect } from 'react';
import { brokerAPI } from '../services/api';
import NavBar from '../components/NavBar';
import BrokerModal from '../components/BrokerModal';

/**
 * BrokersPage - Page for managing brokers (SuperAdmin only)
 */
export default function BrokersPage() {
  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingBroker, setEditingBroker] = useState(null);
  
  useEffect(() => {
    loadBrokers();
  }, []);
  
  const loadBrokers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await brokerAPI.getBrokers();
      // El backend puede devolver un array directamente o dentro de data
      setBrokers(Array.isArray(response.data) ? response.data : response.data?.brokers || []);
    } catch (error) {
      console.error('Error loading brokers:', error);
      setError(error.response?.data?.detail || 'Error al cargar brokers');
    } finally {
      setLoading(false);
    }
  };
  
  const handleCreate = async (brokerData) => {
    try {
      await brokerAPI.createBroker(brokerData);
      loadBrokers();
      setShowModal(false);
    } catch (error) {
      console.error('Error creating broker:', error);
      alert(error.response?.data?.detail || 'Error al crear broker');
    }
  };
  
  const handleUpdate = async (brokerId, updates) => {
    try {
      await brokerAPI.updateBroker(brokerId, updates);
      loadBrokers();
      setEditingBroker(null);
    } catch (error) {
      console.error('Error updating broker:', error);
      alert(error.response?.data?.detail || 'Error al actualizar broker');
    }
  };
  
  const handleDelete = async (brokerId) => {
    if (window.confirm('¿Estás seguro de desactivar este broker? Esta acción no se puede deshacer.')) {
      try {
        await brokerAPI.deleteBroker(brokerId);
        loadBrokers();
      } catch (error) {
        console.error('Error deleting broker:', error);
        alert(error.response?.data?.detail || 'Error al desactivar broker');
      }
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <p className="text-gray-500">Cargando brokers...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">🏢 Gestión de Brokers</h1>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            + Nuevo Broker
          </button>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md mb-4">
            <p className="font-medium">❌ {error}</p>
          </div>
        )}
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {brokers.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p className="text-lg mb-2">No hay brokers registrados</p>
              <p className="text-sm">
                Los brokers aparecerán aquí una vez que el backend implemente los endpoints necesarios.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {brokers.map(broker => (
                <div key={broker.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 text-lg">{broker.name}</h3>
                      {broker.contact_email && (
                        <p className="text-gray-500 text-sm mt-1">📧 {broker.contact_email}</p>
                      )}
                      {broker.contact_phone && (
                        <p className="text-gray-500 text-sm">📞 {broker.contact_phone}</p>
                      )}
                      <span className={`inline-block mt-2 px-2 py-1 text-xs rounded font-medium ${
                        broker.is_active 
                          ? 'bg-green-100 text-green-700' 
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {broker.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setEditingBroker(broker)}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(broker.id)}
                        disabled={!broker.is_active}
                        className="px-3 py-1 border border-red-300 rounded-md text-sm text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {broker.is_active ? 'Desactivar' : 'Desactivado'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Modal para crear/editar */}
        {(showModal || editingBroker) && (
          <BrokerModal
            broker={editingBroker}
            onSave={editingBroker ? handleUpdate : handleCreate}
            onClose={() => {
              setShowModal(false);
              setEditingBroker(null);
            }}
          />
        )}
      </div>
    </div>
  );
}

