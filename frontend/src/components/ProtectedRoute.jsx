import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * ProtectedRoute - Component to protect routes based on authentication and roles
 * 
 * @param {React.ReactNode} children - The component to render if access is granted
 * @param {string[]} allowedRoles - Array of roles that can access this route (empty = any authenticated user)
 */
export default function ProtectedRoute({ children, allowedRoles = [] }) {
  const { isLoggedIn, user, loading, fetchUser } = useAuthStore();
  
  // Check if user is logged in
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  
  // Fetch user if not loaded yet
  if (!user && !loading) {
    fetchUser();
    return <div className="flex items-center justify-center h-screen">
      <p className="text-gray-500">Cargando...</p>
    </div>;
  }
  
  // If roles are specified, check if user has one of them
  if (allowedRoles.length > 0) {
    const userRole = user?.role || 'agent';
    if (!allowedRoles.includes(userRole)) {
      // Redirect to a page the user can access
      return <Navigate to="/pipeline" replace />;
    }
  }
  
  return children;
}


