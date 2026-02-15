import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/auth';
import type { User } from '../types/user';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load token from storage on app start
  useEffect(() => {
    const loadStoredAuth = async () => {
      const storedToken = await AsyncStorage.getItem('token');
      if (storedToken) {
        setToken(storedToken);
      } else {
        setIsLoading(false);
      }
    };
    loadStoredAuth();
  }, []);

  // Fetch user when token changes
  useEffect(() => {
    const loadUser = async () => {
      if (!token) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const userData = await authApi.getMe();
        setUser(userData);
      } catch {
        await AsyncStorage.multiRemove(['token', 'refresh_token']);
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    loadUser();
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    await AsyncStorage.setItem('token', data.access_token);
    if (data.refresh_token) {
      await AsyncStorage.setItem('refresh_token', data.refresh_token);
    }
    setToken(data.access_token);
  }, []);

  const logout = useCallback(async () => {
    authApi.logout().catch(() => {});
    await AsyncStorage.multiRemove(['token', 'refresh_token']);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
