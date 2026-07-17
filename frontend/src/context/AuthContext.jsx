import { createContext, useContext, useState, useCallback } from 'react';
import { authApi } from '../api/client';

const AuthContext = createContext(null);

const USER_KEY = 'genx_auth_user';

function loadUserFromStorage() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveUserToStorage(user) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

export function AuthProvider({ children }) {
  // Restore user from localStorage immediately (no API call needed)
  const [user, setUser] = useState(() => loadUserFromStorage());
  const loading = false;

  const login = useCallback(async (username, password) => {
    const data = await authApi.login(username, password);
    const u = { username: data.username, expires_at: data.expires_at };
    setUser(u);
    saveUserToStorage(u);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    setUser(null);
    saveUserToStorage(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// This module intentionally exports both the provider and its consumer hook.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
