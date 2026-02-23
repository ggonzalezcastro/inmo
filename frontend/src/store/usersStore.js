import { create } from 'zustand';
import { brokerAPI } from '../services/api';

export const useUsersStore = create((set, get) => ({
  users: [],
  loading: false,
  error: null,

  fetchUsers: async () => {
    set({ loading: true, error: null });
    try {
      const response = await brokerAPI.getUsers();
      set({ users: response.data?.data ?? response.data ?? [], loading: false });
      return get().users;
    } catch (error) {
      set({
        error: error.response?.data?.detail || error.message,
        loading: false,
      });
      return [];
    }
  },

  createUser: async (data) => {
    set({ error: null });
    try {
      await brokerAPI.createUser(data);
      await get().fetchUsers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  updateUser: async (userId, data) => {
    set({ error: null });
    try {
      await brokerAPI.updateUser(userId, data);
      await get().fetchUsers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  deleteUser: async (userId) => {
    set({ error: null });
    try {
      await brokerAPI.deleteUser(userId);
      await get().fetchUsers();
      return true;
    } catch (error) {
      set({ error: error.response?.data?.detail || error.message });
      return false;
    }
  },

  clearError: () => set({ error: null }),
}));
