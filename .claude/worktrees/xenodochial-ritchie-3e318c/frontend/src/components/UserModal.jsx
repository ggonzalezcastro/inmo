import { useState, useEffect } from 'react';
import { useAuthStore } from '../store/authStore';
import { brokerAPI } from '../services/api';

/**
 * UserModal - Modal for creating or editing users
 */
export default function UserModal({ user, onSave, onClose }) {
  const { user: currentUser, isSuperAdmin } = useAuthStore();
  const [brokers, setBrokers] = useState([]);
  const [loadingBrokers, setLoadingBrokers] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'agent',
    broker_id: null
  });
  const [errors, setErrors] = useState({});
  
  useEffect(() => {
    // Load brokers if superadmin
    if (isSuperAdmin() && !user) {
      loadBrokers();
    }
    
    // Set broker_id from current user if admin (not superadmin)
    if (!isSuperAdmin() && currentUser?.broker_id) {
      setFormData(prev => ({ ...prev, broker_id: currentUser.broker_id }));
    }
    
    if (user) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        password: '',
        role: user.role || 'agent',
        broker_id: user.broker_id || currentUser?.broker_id || null
      });
    }
  }, [user, currentUser, isSuperAdmin]);
  
  const loadBrokers = async () => {
    setLoadingBrokers(true);
    try {
      const response = await brokerAPI.getBrokers();
      const brokersData = Array.isArray(response.data) 
        ? response.data 
        : (response.data?.brokers && Array.isArray(response.data.brokers))
        ? response.data.brokers
        : [];
      setBrokers(brokersData);
      
      // Auto-select first broker if available
      if (brokersData.length > 0 && !formData.broker_id) {
        setFormData(prev => ({ ...prev, broker_id: brokersData[0].id }));
      }
    } catch (error) {
      console.error('Error loading brokers:', error);
    } finally {
      setLoadingBrokers(false);
    }
  };
  
  const validate = () => {
    const newErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'El nombre es requerido';
    }
    
    if (!formData.email.trim()) {
      newErrors.email = 'El email es requerido';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Email inválido';
    }
    
    // Validate broker_id only when creating new user and user is superadmin
    if (!user && isSuperAdmin() && !formData.broker_id) {
      newErrors.broker_id = 'Debe seleccionar un broker';
    }
    
    if (!user && !formData.password) {
      newErrors.password = 'La contraseña es requerida';
    } else if (formData.password && formData.password.length < 6) {
      newErrors.password = 'La contraseña debe tener al menos 6 caracteres';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }
    
    const dataToSend = { ...formData };
    // Don't send password if editing and password is empty
    if (user && !dataToSend.password) {
      delete dataToSend.password;
    }
    
    // For superadmin, send broker_id. For admin, backend will use current_user.broker_id
    // If not superadmin, remove broker_id as backend doesn't accept it from regular admin
    if (!isSuperAdmin()) {
      delete dataToSend.broker_id;
    }
    
    if (user) {
      onSave(user.id, dataToSend);
    } else {
      onSave(dataToSend);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-gray-900">
              {user ? 'Editar Usuario' : '➕ Nuevo Usuario'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nombre completo
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
                className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.name ? 'border-red-300' : 'border-gray-300'
                }`}
                placeholder="Juan Pérez"
              />
              {errors.name && (
                <p className="text-xs text-red-600 mt-1">{errors.name}</p>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={e => setFormData({...formData, email: e.target.value})}
                disabled={!!user}
                className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.email ? 'border-red-300' : 'border-gray-300'
                } ${user ? 'bg-gray-100 cursor-not-allowed' : ''}`}
                placeholder="juan@inmochile.cl"
              />
              {errors.email && (
                <p className="text-xs text-red-600 mt-1">{errors.email}</p>
              )}
            </div>
            
            {!user && (
              <>
                {/* Broker selection - only for superadmin */}
                {isSuperAdmin() && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Broker *
                    </label>
                    {loadingBrokers ? (
                      <p className="text-sm text-gray-500">Cargando brokers...</p>
                    ) : (
                      <select
                        value={formData.broker_id || ''}
                        onChange={e => setFormData({...formData, broker_id: parseInt(e.target.value)})}
                        className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          errors.broker_id ? 'border-red-300' : 'border-gray-300'
                        }`}
                        required
                      >
                        <option value="">Seleccione un broker</option>
                        {brokers.map(broker => (
                          <option key={broker.id} value={broker.id}>
                            {broker.name}
                          </option>
                        ))}
                      </select>
                    )}
                    {errors.broker_id && (
                      <p className="text-xs text-red-600 mt-1">{errors.broker_id}</p>
                    )}
                  </div>
                )}
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Contraseña
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={e => setFormData({...formData, password: e.target.value})}
                    className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.password ? 'border-red-300' : 'border-gray-300'
                    }`}
                    placeholder="Mínimo 6 caracteres"
                  />
                  {errors.password && (
                    <p className="text-xs text-red-600 mt-1">{errors.password}</p>
                  )}
                </div>
              </>
            )}
            
            {user && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nueva contraseña (opcional)
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={e => setFormData({...formData, password: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Dejar vacío para mantener la actual"
                />
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rol
              </label>
              <div className="space-y-2">
                <label className="flex items-start gap-3 cursor-pointer p-3 border border-gray-200 rounded-md hover:bg-gray-50">
                  <input
                    type="radio"
                    name="role"
                    value="admin"
                    checked={formData.role === 'admin'}
                    onChange={e => setFormData({...formData, role: e.target.value})}
                    className="mt-1"
                  />
                  <div>
                    <span className="font-medium text-gray-900">Admin</span>
                    <p className="text-sm text-gray-500">
                      Puede configurar el agente IA y gestionar usuarios
                    </p>
                  </div>
                </label>
                <label className="flex items-start gap-3 cursor-pointer p-3 border border-gray-200 rounded-md hover:bg-gray-50">
                  <input
                    type="radio"
                    name="role"
                    value="agent"
                    checked={formData.role === 'agent'}
                    onChange={e => setFormData({...formData, role: e.target.value})}
                    className="mt-1"
                  />
                  <div>
                    <span className="font-medium text-gray-900">Agente</span>
                    <p className="text-sm text-gray-500">
                      Trabaja con leads, pipeline y campañas
                    </p>
                  </div>
                </label>
              </div>
            </div>
            
            <div className="flex justify-end gap-2 pt-4 border-t border-gray-200">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                {user ? 'Guardar Cambios' : 'Crear Usuario'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}


