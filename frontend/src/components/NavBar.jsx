import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * NavBar - Reusable navigation bar component
 * Shows current page and allows navigation between pages
 * Filters navigation items based on user role
 */
export default function NavBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, getUserRole, user } = useAuthStore();
  const userRole = getUserRole();
  const isAdmin = userRole === 'admin';
  
  // Debug: Log user role to console
  console.log('NavBar - User:', user);
  console.log('NavBar - UserRole:', userRole);

  // Define all navigation items with their allowed roles
  const allNavItems = [
    { path: '/dashboard', label: 'Dashboard', roles: ['admin', 'superadmin'] },
    { path: '/leads', label: 'Leads', roles: ['admin', 'agent', 'superadmin'] },
    { path: '/pipeline', label: 'Pipeline', roles: ['admin', 'agent', 'superadmin'] },
    { path: '/campaigns', label: 'Campañas', roles: ['admin', 'agent', 'superadmin'] },
    { path: '/chat', label: 'Chat', roles: ['admin', 'agent', 'superadmin'] },
    { path: '/settings', label: 'Configuración', roles: ['admin', 'superadmin'] },
    { path: '/users', label: 'Usuarios', roles: ['admin', 'superadmin'] },
    { path: '/brokers', label: 'Brokers', roles: ['superadmin'] }, // Solo superadmin
  ];

  // Filter navigation items based on user role
  const navItems = allNavItems.filter(item => {
    const hasAccess = item.roles.includes(userRole);
    console.log(`NavBar - Item: ${item.label}, Roles: ${item.roles.join(', ')}, UserRole: ${userRole}, HasAccess: ${hasAccess}`);
    return hasAccess;
  });
  
  console.log('NavBar - Filtered items:', navItems.map(i => i.label));

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <header className="bg-white shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-gray-900">
              {navItems.find(item => isActive(item.path))?.label || 'Inmo'}
            </h1>
            <nav className="flex gap-2">
              {navItems.map((item) => (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    isActive(item.path)
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}


