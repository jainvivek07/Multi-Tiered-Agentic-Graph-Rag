import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CurrentUser {
  id: string;
  email: string;
  role: 'admin' | 'user';
}

interface AuthState {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  setUser: (u: CurrentUser) => void;
  clearUser: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      setUser: (u) => set({ user: u, isAuthenticated: true }),
      clearUser: () => set({ user: null, isAuthenticated: false }),
    }),
    { name: 'rag-auth' },
  ),
);
