import { useState } from 'react';
import { useAuthStore } from '../store/authStore';

/**
 * RoleDebugger - Component to test different roles in development
 * Only shows in development mode
 * 
 * Usage: Add <RoleDebugger /> to any page to test role-based features
 */
export default function RoleDebugger() {
  const { user, getUserRole, isAdmin } = useAuthStore();
  const [selectedRole, setSelectedRole] = useState(user?.role || 'agent');
  const [showDebugger, setShowDebugger] = useState(false);
  
  // Only show in development
  if (import.meta.env.PROD) {
    return null;
  }
  
  const handleRoleChange = (newRole) => {
    setSelectedRole(newRole);
    
    // Update user in localStorage and store
    const updatedUser = {
      ...user,
      role: newRole,
      id: user?.id || 1,
      email: user?.email || 'test@example.com',
      name: user?.name || 'Test User'
    };
    
    localStorage.setItem('user', JSON.stringify(updatedUser));
    
    // Force reload to apply changes
    window.location.reload();
  };
  
  const currentRole = getUserRole();
  const adminStatus = isAdmin();
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      {!showDebugger ? (
        <button
          onClick={() => setShowDebugger(true)}
          className="bg-purple-600 text-white px-4 py-2 rounded-lg shadow-lg hover:bg-purple-700 text-sm font-medium"
        >
          🔧 Debug Roles
        </button>
      ) : (
        <div className="bg-white border-2 border-purple-500 rounded-lg shadow-xl p-4 w-80">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-gray-900">🔧 Role Debugger</h3>
            <button
              onClick={() => setShowDebugger(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>
          
          <div className="space-y-3">
            <div className="bg-gray-50 p-2 rounded">
              <p className="text-xs text-gray-600 mb-1">Rol Actual:</p>
              <p className="font-semibold text-lg">
                {currentRole === 'superadmin' ? '👑 SuperAdmin' : 
                 currentRole === 'admin' ? '👔 Admin' : '🏠 Agent'}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                isAdmin: {adminStatus ? '✅ Sí' : '❌ No'}
              </p>
            </div>
            
            <div>
              <p className="text-xs font-medium text-gray-700 mb-2">
                Cambiar a:
              </p>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => handleRoleChange('superadmin')}
                  className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                    currentRole === 'superadmin'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  👑 SuperAdmin
                </button>
                <button
                  onClick={() => handleRoleChange('admin')}
                  className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                    currentRole === 'admin'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  👔 Admin
                </button>
                <button
                  onClick={() => handleRoleChange('agent')}
                  className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                    currentRole === 'agent'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  🏠 Agent
                </button>
              </div>
            </div>
            
            <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
              <p className="text-xs text-yellow-800">
                ⚠️ Esto actualiza localStorage y recarga la página
              </p>
            </div>
            
            <div className="text-xs text-gray-500 space-y-1">
              <p><strong>👑 SuperAdmin puede ver:</strong></p>
              <ul className="list-disc list-inside ml-2">
                <li>Dashboard</li>
                <li>Pipeline</li>
                <li>Campañas</li>
                <li>Chat</li>
                <li>⚙️ Configuración</li>
                <li>👤 Usuarios</li>
                <li>🏢 Brokers (solo superadmin)</li>
              </ul>
              <p className="mt-2"><strong>👔 Admin puede ver:</strong></p>
              <ul className="list-disc list-inside ml-2">
                <li>Dashboard</li>
                <li>Pipeline</li>
                <li>Campañas</li>
                <li>Chat</li>
                <li>⚙️ Configuración</li>
                <li>👤 Usuarios</li>
              </ul>
              <p className="mt-2"><strong>🏠 Agent puede ver:</strong></p>
              <ul className="list-disc list-inside ml-2">
                <li>Pipeline</li>
                <li>Campañas</li>
                <li>Chat</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

