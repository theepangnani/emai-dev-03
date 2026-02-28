import { useState, useCallback } from 'react';

/**
 * All localStorage keys managed by session-state hooks.
 * Cleared on logout via clearAllSessionState().
 */
export const SESSION_KEYS = [
  'last_selected_child',
  'last_visited_path',
  'pd-section-states',
  'pd-view-mode',
  'calendar_collapsed',
  'calendar-visited',
] as const;

/**
 * Hook that mirrors a value to localStorage so it persists across sessions.
 *
 * - Reads the stored value on first render (falling back to `defaultValue`).
 * - Writes to localStorage on every `setValue` call.
 * - Safe for SSR / private-browsing (swallows storage errors).
 */
export function useSessionState<T>(key: string, defaultValue: T): [T, (val: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      if (stored !== null) {
        return JSON.parse(stored) as T;
      }
    } catch {
      // localStorage unavailable or JSON parse failure
    }
    return defaultValue;
  });

  const set = useCallback(
    (newValue: T) => {
      setValue(newValue);
      try {
        localStorage.setItem(key, JSON.stringify(newValue));
      } catch {
        // Storage full or unavailable — silently ignore
      }
    },
    [key],
  );

  return [value, set];
}

/**
 * Clear all session-state keys from localStorage.
 * Call this on logout to reset persisted UI state.
 */
export function clearAllSessionState(): void {
  for (const key of SESSION_KEYS) {
    try {
      localStorage.removeItem(key);
    } catch {
      // ignore
    }
  }
  // Also clear the legacy sessionStorage key
  try {
    sessionStorage.removeItem('selectedChildId');
  } catch {
    // ignore
  }
}
