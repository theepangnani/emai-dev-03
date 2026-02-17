import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';

export type Theme = 'light' | 'dark' | 'focus';
export type StyleMode = 'flat' | 'gradient';

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  cycleTheme: () => void;
  style: StyleMode;
  toggleStyle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'classbridge-theme';
const STYLE_STORAGE_KEY = 'classbridge-style';
const THEMES: Theme[] = ['light', 'dark', 'focus'];
const STYLES: StyleMode[] = ['flat', 'gradient'];

function getInitialTheme(): Theme {
  // Check localStorage first
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && THEMES.includes(stored as Theme)) {
    return stored as Theme;
  }
  // Auto-detect OS preference
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

function getInitialStyle(): StyleMode {
  const stored = localStorage.getItem(STYLE_STORAGE_KEY);
  if (stored && STYLES.includes(stored as StyleMode)) {
    return stored as StyleMode;
  }
  return 'flat';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);
  const [style, setStyleState] = useState<StyleMode>(getInitialStyle);

  const applyTheme = useCallback((t: Theme) => {
    document.documentElement.setAttribute('data-theme', t);
  }, []);

  const applyStyle = useCallback((s: StyleMode) => {
    if (s === 'gradient') {
      document.documentElement.setAttribute('data-style', 'gradient');
    } else {
      document.documentElement.removeAttribute('data-style');
    }
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

  const toggleStyle = useCallback(() => {
    setStyleState(prev => {
      const next: StyleMode = prev === 'flat' ? 'gradient' : 'flat';
      localStorage.setItem(STYLE_STORAGE_KEY, next);
      applyStyle(next);
      return next;
    });
  }, [applyStyle]);

  // Apply theme and style on mount
  useEffect(() => {
    applyTheme(theme);
    applyStyle(style);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for OS theme changes
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      // Only auto-switch if user hasn't manually set a preference
      if (!localStorage.getItem(STORAGE_KEY)) {
        const next = e.matches ? 'dark' : 'light';
        setThemeState(next);
        applyTheme(next);
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [applyTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, cycleTheme, style, toggleStyle }}>
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
