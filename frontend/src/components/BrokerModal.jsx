import { useState, useEffect } from 'react';

/**
 * BrokerModal - Modal for creating or editing brokers
 */
export default function BrokerModal({ broker, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    contact_phone: '',
    contact_email: '',
    business_hours: 'Lunes a Viernes 9:00-18:00',
    service_zones: [],
    is_active: true
  });
  const [errors, setErrors] = useState({});
  const [newZone, setNewZone] = useState('');
  
  useEffect(() => {
    if (broker) {
      setFormData({
        name: broker.name || '',
        slug: broker.slug || '',
        contact_phone: broker.contact_phone || '',
        contact_email: broker.contact_email || '',
        business_hours: broker.business_hours || 'Lunes a Viernes 9:00-18:00',
        service_zones: broker.service_zones || [],
        is_active: broker.is_active !== undefined ? broker.is_active : true
      });
    }
  }, [broker]);
  
  const validate = () => {
    const newErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'El nombre es requerido';
    }
    
    if (formData.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.contact_email)) {
      newErrors.contact_email = 'Email inválido';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }
    
    const dataToSend = {
      ...formData,
      // Asegurar que service_zones sea un array
      service_zones: Array.isArray(formData.service_zones) ? formData.service_zones : []
    };
    
    if (broker) {
      onSave(broker.id, dataToSend);
    } else {
      onSave(dataToSend);
    }
  };
  
  const handleAddZone = () => {
    if (newZone.trim() && !formData.service_zones.includes(newZone.trim())) {
      setFormData({
        ...formData,
        service_zones: [...formData.service_zones, newZone.trim()]
      });
      setNewZone('');
    }
  };
  
  const handleRemoveZone = (zone) => {
    setFormData({
      ...formData,
      service_zones: formData.service_zones.filter(z => z !== zone)
    });
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-gray-900">
              {broker ? 'Editar Broker' : '➕ Nuevo Broker'}
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
                Nombre del Broker *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
                className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.name ? 'border-red-300' : 'border-gray-300'
                }`}
                placeholder="Ej: InmoChile"
                required
              />
              {errors.name && (
                <p className="text-xs text-red-600 mt-1">{errors.name}</p>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Slug (opcional)
              </label>
              <input
                type="text"
                value={formData.slug}
                onChange={e => setFormData({...formData, slug: e.target.value.toLowerCase().replace(/\s+/g, '-')})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="inmochile"
              />
              <p className="text-xs text-gray-500 mt-1">URL amigable (se genera automáticamente si se deja vacío)</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Teléfono de Contacto
                </label>
                <input
                  type="tel"
                  value={formData.contact_phone}
                  onChange={e => setFormData({...formData, contact_phone: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="+56912345678"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email de Contacto
                </label>
                <input
                  type="email"
                  value={formData.contact_email}
                  onChange={e => setFormData({...formData, contact_email: e.target.value})}
                  className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    errors.contact_email ? 'border-red-300' : 'border-gray-300'
                  }`}
                  placeholder="contacto@inmochile.cl"
                />
                {errors.contact_email && (
                  <p className="text-xs text-red-600 mt-1">{errors.contact_email}</p>
                )}
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Horario de Atención
              </label>
              <input
                type="text"
                value={formData.business_hours}
                onChange={e => setFormData({...formData, business_hours: e.target.value})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Lunes a Viernes 9:00-18:00"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Zonas de Servicio
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={newZone}
                  onChange={e => setNewZone(e.target.value)}
                  onKeyPress={e => e.key === 'Enter' && (e.preventDefault(), handleAddZone())}
                  className="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: Las Condes, Vitacura"
                />
                <button
                  type="button"
                  onClick={handleAddZone}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Agregar
                </button>
              </div>
              {formData.service_zones.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {formData.service_zones.map((zone, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                    >
                      {zone}
                      <button
                        type="button"
                        onClick={() => handleRemoveZone(zone)}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            
            <div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={e => setFormData({...formData, is_active: e.target.checked})}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm font-medium text-gray-700">
                  Broker activo
                </span>
              </label>
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
                {broker ? 'Guardar Cambios' : 'Crear Broker'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}


