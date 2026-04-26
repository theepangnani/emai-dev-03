import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react';

export type Theme = 'light' | 'dark' | 'focus' | 'bridge';

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  cycleTheme: () => void;
  /** CB-THEME-001: force-apply `bridge` if the user has not made an explicit
   *  pick yet. No-op after the first call this session, after any explicit
   *  toggle, or when the stored theme is already `bridge`. */
  applyBridgeDefaultIfUnset: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'classbridge-theme';
// CB-THEME-001 #4213: cached resolved value of the `theme.bridge_default`
// feature flag. Written by `<BridgeDefaultApplier>` after TanStack Query
// resolves the flag, read synchronously here on the next mount so cold
// paint already shows `bridge` for users in the rollout cohort. This
// eliminates the 100-500ms FOWT (Flash of Wrong Theme) that otherwise
// occurs while the flag query hydrates.
//
// Kill-switch contract: `<BridgeDefaultApplier>` clears this key whenever
// the flag resolves to false on a future mount, so flipping the flag OFF
// in production stops force-applying bridge on the cycle after that.
export const BRIDGE_DEFAULT_CACHE_KEY = 'classbridge-theme-bridge-default-cached';
const THEMES: Theme[] = ['light', 'dark', 'focus', 'bridge'];

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && THEMES.includes(stored as Theme)) {
    return stored as Theme;
  }
  // CB-THEME-001 #4213: no explicit pick — fall back to the cached
  // bridge-default flag value if present so we paint `bridge` synchronously
  // on cold load instead of flashing `light` while the flag query resolves.
  if (localStorage.getItem(BRIDGE_DEFAULT_CACHE_KEY) === 'true') {
    return 'bridge';
  }
  return 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  // CB-THEME-001: tracks whether `applyBridgeDefaultIfUnset` has already fired
  // this session. We use a ref so re-renders never re-trigger force-apply and
  // user toggles after force-apply are respected.
  const forcedRef = useRef(false);

  const applyTheme = useCallback((t: Theme) => {
    document.documentElement.setAttribute('data-theme', t);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
    applyTheme(t);
  }, [applyTheme]);

  const cycleTheme = useCallback(() => {
    setThemeState(prev => {
      const idx = THEMES.indexOf(prev);
      const next = THEMES[(idx + 1) % THEMES.length];
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
      return next;
    });
  }, [applyTheme]);

  /**
   * CB-THEME-001 force-apply hook. Called once by `<BridgeDefaultApplier>`
   * (mounted under the QueryClientProvider) when the
   * `theme.bridge_default` feature flag resolves on for the user. We never
   * overwrite a theme already chosen explicitly via localStorage so user
   * toggles after force-apply remain sticky.
   */
  const applyBridgeDefaultIfUnset = useCallback(() => {
    if (forcedRef.current) return;
    forcedRef.current = true;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && THEMES.includes(stored as Theme)) {
      // User has already made an explicit pick — respect it.
      return;
    }
    setThemeState('bridge');
    applyTheme('bridge');
  }, [applyTheme]);

  useEffect(() => {
    applyTheme(theme);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ThemeContext.Provider value={{ theme, setTheme, cycleTheme, applyBridgeDefaultIfUnset }}>
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
