import { useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';
import { BRIDGE_DEFAULT_CACHE_KEY } from '../context/ThemeContext';
import { useFeatureFlagState } from '../hooks/useFeatureToggle';

/**
 * CB-THEME-001 Stream S0 — bridge force-apply gate.
 *
 * Mounted under <QueryClientProvider> so it can call useFeatureFlagState.
 * When `theme.bridge_default` resolves on for the current user AND the user
 * has not explicitly picked a theme yet, this component triggers
 * `applyBridgeDefaultIfUnset()` exactly once. The ThemeProvider ref-guards
 * subsequent calls so a manual ThemeToggle flip after force-apply is
 * respected.
 *
 * #4213 — FOWT mitigation: also persists the resolved flag value to
 * localStorage under `BRIDGE_DEFAULT_CACHE_KEY`. ThemeContext reads that
 * cache synchronously inside `getInitialTheme()` on the next mount, so
 * cold paint already shows `bridge` for users in the rollout cohort
 * instead of flashing `light` for 100-500ms while the flag query hydrates.
 *
 * Kill-switch: when the flag resolves to FALSE (and the query is no longer
 * loading — so we know it's a real `false`, not the safe-default-during-
 * hydration value), the cache key is cleared. Flipping the flag OFF in
 * production therefore stops force-applying bridge on the next cold load.
 *
 * Renders nothing.
 */
export function BridgeDefaultApplier() {
  const { enabled, isLoading } = useFeatureFlagState('theme.bridge_default');
  const { applyBridgeDefaultIfUnset } = useTheme();

  useEffect(() => {
    if (isLoading) return; // wait for a real resolution before touching cache
    if (enabled) {
      localStorage.setItem(BRIDGE_DEFAULT_CACHE_KEY, 'true');
      applyBridgeDefaultIfUnset();
    } else {
      // Kill-switch: flag resolved to false — drop the cache so the next
      // cold load no longer paints `bridge` synchronously.
      localStorage.removeItem(BRIDGE_DEFAULT_CACHE_KEY);
    }
  }, [enabled, isLoading, applyBridgeDefaultIfUnset]);

  return null;
}
