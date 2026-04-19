import { useState, useEffect, useRef } from 'react';
import { brokerAPI } from '../services/api';

/**
 * AssignmentDropdown - Component to assign leads to agents (Admin only)
 */
export default function AssignmentDropdown({ lead, onAssign }) {
  const [isOpen, setIsOpen] = useState(false);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);
  
  useEffect(() => {
    // Fetch agents when dropdown opens
    if (isOpen && agents.length === 0) {
      loadAgents();
    }
    
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);
  
  const loadAgents = async () => {
    setLoading(true);
    try {
      const response = await brokerAPI.getUsers();
      // Filter only agents (not admins)
      const agentUsers = response.data.filter(user => 
        user.role === 'agent' && user.is_active
      );
      setAgents(agentUsers);
    } catch (error) {
      console.error('Error loading agents:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAssign = async (agentId) => {
    try {
      await onAssign(lead.id, agentId);
      setIsOpen(false);
    } catch (error) {
      console.error('Error assigning lead:', error);
      alert('Error al asignar lead. Por favor, intenta nuevamente.');
    }
  };
  
  const handleUnassign = async () => {
    try {
      await onAssign(lead.id, null);
      setIsOpen(false);
    } catch (error) {
      console.error('Error unassigning lead:', error);
      alert('Error al desasignar lead. Por favor, intenta nuevamente.');
    }
  };
  
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {lead.assigned_to 
          ? `👤 Asignado a: ${lead.assigned_agent?.name || 'Usuario'}` 
          : '👤 Sin asignar'
        }
        <span className="ml-1">▼</span>
      </button>
      
      {isOpen && (
        <div className="absolute left-0 mt-1 w-56 bg-white rounded-md shadow-lg z-50 border border-gray-200">
          <div className="py-1">
            <button
              onClick={handleUnassign}
              className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Sin asignar
            </button>
            {loading ? (
              <div className="px-4 py-2 text-sm text-gray-500">Cargando agentes...</div>
            ) : agents.length === 0 ? (
              <div className="px-4 py-2 text-sm text-gray-500">No hay agentes disponibles</div>
            ) : (
              agents.map(agent => (
                <button
                  key={agent.id}
                  onClick={() => handleAssign(agent.id)}
                  className={`block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ${
                    lead.assigned_to === agent.id ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'
                  }`}
                >
                  {agent.name} ({agent.email})
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

