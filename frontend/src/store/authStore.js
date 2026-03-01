import { create } from 'zustand';
import { authAPI } from '../services/api';


export const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('token') || null,
  loading: false,
  error: null,
  
  isLoggedIn: () => !!localStorage.getItem('token'),
  
  register: async (email, password, broker_name) => {
    set({ loading: true, error: null });
    try {
      const response = await authAPI.register(email, password, broker_name);
      const { access_token } = response.data;
      
      localStorage.setItem('token', access_token);
      set({ token: access_token, loading: false });
      
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
      
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      set({ error: message, loading: false });
      return false;
    }
  },
  
  logout: () => {
    localStorage.removeItem('token');
    set({ token: null, user: null });
  },
}));

