import { create } from 'zustand';
import { authAPI } from '../services/api';


export const useAuthStore = create((set, get) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token') || null,
  loading: false,
  error: null,
  
  isLoggedIn: () => !!localStorage.getItem('token'),
  
  // Fetch current user info
  fetchUser: async () => {
    try {
      // Try to get user from /auth/me endpoint
      const response = await authAPI.getCurrentUser();
      const user = response.data;
      localStorage.setItem('user', JSON.stringify(user));
      set({ user });
      return user;
    } catch (error) {
      console.error('Error fetching user from /auth/me:', error);
      // If endpoint doesn't exist, decode JWT token to get user info
      try {
        const token = localStorage.getItem('token');
        if (token) {
          // Decode JWT token (simple base64 decode, no verification needed for client-side)
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
          }).join(''));
          const payload = JSON.parse(jsonPayload);
          
          const user = {
            id: parseInt(payload.sub),
            email: payload.email,
            role: payload.role ? payload.role.toLowerCase() : 'agent',
            broker_id: payload.broker_id || null
          };
          
          localStorage.setItem('user', JSON.stringify(user));
          set({ user });
          return user;
        }
      } catch (decodeError) {
        console.error('Error decoding token:', decodeError);
      }
      return null;
    }
  },
  
  register: async (email, password, broker_name) => {
    set({ loading: true, error: null });
    try {
      const response = await authAPI.register(email, password, broker_name);
      const { access_token } = response.data;
      
      localStorage.setItem('token', access_token);
      set({ token: access_token, loading: false });
      
      // After registration, fetch user info from API to get updated broker_id and role
      // The backend creates the broker automatically, so we need fresh data
      try {
        const user = await get().fetchUser();
        if (user) {
          console.log('Register - User info after registration:', user);
          console.log('✅ Broker creado automáticamente. Broker ID:', user.broker_id);
          console.log('✅ Rol asignado:', user.role);
        }
      } catch (fetchError) {
        console.error('Error fetching user after register:', fetchError);
        // Fallback to token decode
        try {
          const base64Url = access_token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
          }).join(''));
          const payload = JSON.parse(jsonPayload);
          
          const user = {
            id: parseInt(payload.sub),
            email: payload.email || email,
            role: payload.role ? payload.role.toLowerCase() : 'agent',
            broker_id: payload.broker_id || null
          };
          
          localStorage.setItem('user', JSON.stringify(user));
          set({ user });
        } catch (decodeError) {
          console.error('Error decoding token after register:', decodeError);
        }
      }
      
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed';
      set({ error: message, loading: false });
      return false;
    }
  },
  
  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const response = await authAPI.login(email, password);
      const { access_token } = response.data;
      
      localStorage.setItem('token', access_token);
      set({ token: access_token, loading: false });
      
      // Decode token immediately to get user info
      try {
        const base64Url = access_token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
          return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        const payload = JSON.parse(jsonPayload);
        
        const user = {
          id: parseInt(payload.sub),
          email: payload.email || email,
          role: payload.role ? payload.role.toLowerCase() : 'agent',
          broker_id: payload.broker_id || null
        };
        
        console.log('Login - Decoded user from token:', user);
        localStorage.setItem('user', JSON.stringify(user));
        set({ user });
      } catch (decodeError) {
        console.error('Error decoding token after login:', decodeError);
        // Try to fetch from API as fallback
        await get().fetchUser();
      }
      
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      set({ error: message, loading: false });
      return false;
    }
  },
  
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, user: null });
  },
  
  // Decode token to get user info
  decodeToken: () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return null;
      
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      const payload = JSON.parse(jsonPayload);
      
      return {
        id: parseInt(payload.sub),
        email: payload.email,
        role: payload.role ? payload.role.toLowerCase() : 'agent',
        broker_id: payload.broker_id || null
      };
    } catch (error) {
      console.error('Error decoding token:', error);
      return null;
    }
  },
  
  // Get user role (normalize to lowercase)
  getUserRole: () => {
    let user = get().user;
    
    // If user is null, try to decode from token
    if (!user) {
      user = get().decodeToken();
      if (user) {
        localStorage.setItem('user', JSON.stringify(user));
        set({ user });
      }
    }
    
    const role = user?.role;
    if (!role) return 'agent'; // Default to agent if no role
    
    // Normalize role to lowercase (backend may return ADMIN, SUPERADMIN, etc.)
    return role.toLowerCase();
  },
  
  // Check if user is admin
  isAdmin: () => {
    const role = get().getUserRole();
    return role === 'admin' || role === 'superadmin';
  },
  
  // Check if user is superadmin
  isSuperAdmin: () => {
    return get().getUserRole() === 'superadmin';
  },
}));

