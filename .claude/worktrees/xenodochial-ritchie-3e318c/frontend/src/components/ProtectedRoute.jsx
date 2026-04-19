import { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * ProtectedRoute - Component to protect routes based on authentication and roles
 * 
 * @param {React.ReactNode} children - The component to render if access is granted
 * @param {string[]} allowedRoles - Array of roles that can access this route (empty = any authenticated user)
 */
export default function ProtectedRoute({ children, allowedRoles = [] }) {
  const { isLoggedIn, user, userLoading, fetchUser } = useAuthStore();
  
  // Fetch user once when we have token but no user (e.g. page refresh)
  useEffect(() => {
    if (isLoggedIn() && !user && !userLoading) {
      fetchUser();
    }
  }, [isLoggedIn(), user, userLoading, fetchUser]);
  
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  
  // Show loading only while fetching user (request has timeout; when it ends userLoading becomes false)
  if (!user && userLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">Cargando...</p>
      </div>
    );
  }
  
  // After fetch: if still no user, fetchUser already tried token decode in catch — show error
  if (!user) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">No se pudo cargar el usuario. <a href="/login" className="text-blue-600 underline">Volver a entrar</a></p>
      </div>
    );
  }
  
  if (allowedRoles.length > 0) {
    const userRole = user.role || 'agent';
    if (!allowedRoles.includes(userRole)) {
      return <Navigate to="/403" replace />;
    }
  }
  
  return children;
}


