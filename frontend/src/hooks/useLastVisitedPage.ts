import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const LAST_VISITED_KEY = 'last_visited_path';

/** Pages that should NOT be saved as "last visited" (auth/system pages). */
const EXCLUDED_PATHS = ['/login', '/register', '/onboarding', '/accept-invite', '/forgot-password', '/reset-password', '/verify-email', '/privacy', '/terms'];

/**
 * Tracks the current page path + search params in localStorage.
 * Call this once from a top-level authenticated component (e.g. DashboardLayout).
 */
export function useLastVisitedPage(): void {
  const location = useLocation();

  useEffect(() => {
    const fullPath = location.pathname + location.search;

    // Don't save auth/system pages
    if (EXCLUDED_PATHS.some(p => location.pathname.startsWith(p))) return;

    try {
      localStorage.setItem(LAST_VISITED_KEY, fullPath);
    } catch {
      // Storage full or unavailable
    }
  }, [location.pathname, location.search]);
}

/**
 * Returns the last visited path (or null).
 * Safe to call outside React (e.g. in login handler).
 */
export function getLastVisitedPage(): string | null {
  try {
    return localStorage.getItem(LAST_VISITED_KEY);
  } catch {
    return null;
  }
}
