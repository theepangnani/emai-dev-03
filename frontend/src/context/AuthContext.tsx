import { createContext, useContext, useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { authApi } from '../api/client';

const IDLE_TIMEOUT_MS = 2 * 60 * 60 * 1000; // 2 hours
const WARNING_BEFORE_MS = 5 * 60 * 1000; // 5 minutes before timeout

interface User {
  id: number;
  email: string;
  username?: string;
  full_name: string;
  role: string | null;
  roles: string[];
  is_active: boolean;
  google_connected: boolean;
  needs_onboarding: boolean;
  onboarding_completed: boolean;
  email_verified: boolean;
  interests: string[];
  storage_used_bytes?: number;
  storage_limit_bytes?: number;
  upload_limit_bytes?: number;
  storage_used_pct?: number;
  storage_warning?: boolean;
  preferred_language?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (identifier: string, password: string, botFields?: { website?: string; started_at?: number }) => Promise<void>;
  loginWithToken: (token: string, refreshToken?: string) => void;
  register: (data: { email?: string; username?: string; parent_email?: string; password: string; full_name: string; roles?: string[]; teacher_type?: string; google_id?: string; token?: string; website?: string; started_at?: number; email_consent?: boolean }) => Promise<void>;
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
  const [showIdleWarning, setShowIdleWarning] = useState(false);

  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutRef = useRef<() => void>(() => {});

  const resetIdleTimers = useCallback(() => {
    setShowIdleWarning(false);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    warningTimerRef.current = setTimeout(() => {
      setShowIdleWarning(true);
    }, IDLE_TIMEOUT_MS - WARNING_BEFORE_MS);
    idleTimerRef.current = setTimeout(() => {
      logoutRef.current();
    }, IDLE_TIMEOUT_MS);
  }, []);

  // Idle timeout: track activity when user is logged in
  useEffect(() => {
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowIdleWarning(false);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      return;
    }

    const events: Array<keyof WindowEventMap> = ['mousemove', 'keydown', 'touchstart', 'scroll'];
    const handleActivity = () => resetIdleTimers();

    resetIdleTimers();
    events.forEach(e => window.addEventListener(e, handleActivity, { passive: true }));

    return () => {
      events.forEach(e => window.removeEventListener(e, handleActivity));
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  }, [token, resetIdleTimers]);

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

  const login = async (identifier: string, password: string, botFields?: { website?: string; started_at?: number }) => {
    const data = await authApi.login(identifier, password, botFields);
    localStorage.setItem('token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    setToken(data.access_token);
  };

  const loginWithToken = (newToken: string, refreshToken?: string) => {
    localStorage.setItem('token', newToken);
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken);
    setToken(newToken);
  };

  const register = async (data: { email?: string; username?: string; parent_email?: string; password: string; full_name: string; roles?: string[]; teacher_type?: string; google_id?: string; token?: string; website?: string; started_at?: number; email_consent?: boolean }) => {
    await authApi.register(data);
    // Login with email or username, whichever was provided
    const identifier = data.email || data.username || '';
    await login(identifier, data.password);
  };

  const logout = useCallback(() => {
    // Best-effort server-side token revocation
    authApi.logout().catch(() => {});
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  }, []);

  // Keep logoutRef in sync so idle timer can call logout without stale closure
  useEffect(() => {
    logoutRef.current = logout;
  }, [logout]);

  const switchRole = async (role: string) => {
    const userData = await authApi.switchRole(role);
    setUser(userData);
  };

  const completeOnboarding = async (roles: string[], teacherType?: string) => {
    const responseData = await authApi.completeOnboarding(roles, teacherType);
    // The onboarding endpoint now returns new JWT tokens along with user data
    if (responseData.access_token) {
      localStorage.setItem('token', responseData.access_token);
      if (responseData.refresh_token) {
        localStorage.setItem('refresh_token', responseData.refresh_token);
      }
      setToken(responseData.access_token);
    }
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
      {showIdleWarning && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }} role="alertdialog" aria-modal="true" aria-labelledby="session-expiring-title">
          <div style={{ background: 'var(--color-surface)', borderRadius: 8, padding: '2rem', maxWidth: 400, textAlign: 'center', boxShadow: '0 4px 24px rgba(0,0,0,0.2)' }}>
            <h3 id="session-expiring-title" style={{ margin: '0 0 1rem' }}>Session Expiring</h3>
            <p style={{ margin: '0 0 1.5rem', color: 'var(--color-ink-muted)' }}>Your session is about to expire. Click to stay logged in.</p>
            <button
              onClick={resetIdleTimers}
              style={{ padding: '0.5rem 1.5rem', fontSize: '1rem', borderRadius: 6, border: 'none', background: 'var(--color-accent)', color: 'var(--color-surface)', cursor: 'pointer' }}
            >
              Stay Logged In
            </button>
          </div>
        </div>
      )}
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
