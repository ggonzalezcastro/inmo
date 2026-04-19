import { useState, useEffect } from 'react';
import { brokerAPI } from '../services/api';
import NavBar from '../components/NavBar';
import UserModal from '../components/UserModal';

/**
 * UsersPage - Page for managing broker users (Admin only)
 */
export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    loadUsers();
  }, []);
  
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await brokerAPI.getUsers();
      // Handle different response structures
      const usersData = response.data;
      // If response.data is an array, use it directly
      // If it's an object with a 'users' property, use that
      // Otherwise, default to empty array
      const usersArray = Array.isArray(usersData) 
        ? usersData 
        : (usersData?.users && Array.isArray(usersData.users))
        ? usersData.users
        : [];
      
      console.log('Users response:', response.data);
      console.log('Parsed users:', usersArray);
      
      setUsers(usersArray);
    } catch (error) {
      console.error('Error loading users:', error);
      setError(error.response?.data?.detail || 'Error al cargar usuarios');
      setUsers([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };
  
  const handleCreate = async (userData) => {
    try {
      await brokerAPI.createUser(userData);
      loadUsers();
      setShowModal(false);
    } catch (error) {
      console.error('Error creating user:', error);
      alert(error.response?.data?.detail || 'Error al crear usuario');
    }
  };
  
  const handleUpdate = async (userId, updates) => {
    try {
      await brokerAPI.updateUser(userId, updates);
      loadUsers();
      setEditingUser(null);
    } catch (error) {
      console.error('Error updating user:', error);
      alert(error.response?.data?.detail || 'Error al actualizar usuario');
    }
  };
  
  const handleDeactivate = async (userId) => {
    if (window.confirm('¿Estás seguro de desactivar este usuario?')) {
      try {
        await brokerAPI.deleteUser(userId);
        loadUsers();
      } catch (error) {
        console.error('Error deactivating user:', error);
        alert(error.response?.data?.detail || 'Error al desactivar usuario');
      }
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <p className="text-gray-500">Cargando usuarios...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">👤 Usuarios del Equipo</h1>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            + Nuevo Usuario
          </button>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md mb-4">
            ❌ {error}
          </div>
        )}
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {!Array.isArray(users) || users.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p>No hay usuarios registrados</p>
              <p className="text-sm mt-2">Crea el primer usuario para comenzar</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {users.map(user => (
                <div key={user.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <p className="text-gray-500 text-sm mb-1">📧 {user.email}</p>
                      <p className="font-semibold text-gray-900">{user.name || 'Sin nombre'}</p>
                      <span className={`inline-block mt-2 px-2 py-1 text-xs rounded font-medium ${
                        user.role === 'admin' 
                          ? 'bg-purple-100 text-purple-700' 
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {user.role === 'admin' ? '👔 Admin' : '🏠 Agente'}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setEditingUser(user)}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDeactivate(user.id)}
                        className="px-3 py-1 border border-red-300 rounded-md text-sm text-red-600 hover:bg-red-50 transition-colors"
                      >
                        Desactivar
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Modal para crear/editar */}
      {(showModal || editingUser) && (
        <UserModal
          user={editingUser}
          onSave={editingUser ? handleUpdate : handleCreate}
          onClose={() => {
            setShowModal(false);
            setEditingUser(null);
          }}
        />
      )}
    </div>
  );
}


