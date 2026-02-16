import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authApi } from '../api/client';

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string | null;
  roles: string[];
  is_active: boolean;
  google_connected: boolean;
  needs_onboarding: boolean;
  email_verified: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithToken: (token: string, refreshToken?: string) => void;
  register: (data: { email: string; password: string; full_name: string; roles: string[]; teacher_type?: string; [key: string]: string | string[] | undefined }) => Promise<void>;
  logout: () => void;
  switchRole: (role: string) => Promise<void>;
  completeOnboarding: (roles: string[], teacherType?: string) => Promise<void>;
  resendVerification: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      setIsLoading(true);
      if (token) {
        try {
          const userData = await authApi.getMe();
          setUser(userData);
        } catch {
          localStorage.removeItem('token');
          setToken(null);
        }
      } else {
        setUser(null);
      }
      setIsLoading(false);
    };
    loadUser();
  }, [token]);

  const login = async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    localStorage.setItem('token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    setToken(data.access_token);
    const userData = await authApi.getMe();
    setUser(userData);
  };

  const loginWithToken = (newToken: string, refreshToken?: string) => {
    localStorage.setItem('token', newToken);
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken);
    setToken(newToken);
  };

  const register = async (data: { email: string; password: string; full_name: string; roles: string[]; teacher_type?: string; [key: string]: string | string[] | undefined }) => {
    await authApi.register(data);
    await login(data.email, data.password);
  };

  const logout = () => {
    // Best-effort server-side token revocation
    authApi.logout().catch(() => {});
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const switchRole = async (role: string) => {
    const userData = await authApi.switchRole(role);
    setUser(userData);
  };

  const completeOnboarding = async (roles: string[], teacherType?: string) => {
    const userData = await authApi.completeOnboarding(roles, teacherType);
    setUser(userData);
  };

  const resendVerification = async () => {
    await authApi.resendVerification();
  };

  const refreshUser = async () => {
    const userData = await authApi.getMe();
    setUser(userData);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, loginWithToken, register, logout, switchRole, completeOnboarding, resendVerification, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
