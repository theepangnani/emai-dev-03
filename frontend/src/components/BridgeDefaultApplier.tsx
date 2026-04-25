import { useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';
import { useFeatureFlagEnabled } from '../hooks/useFeatureToggle';

/**
 * CB-THEME-001 Stream S0 — bridge force-apply gate.
 *
 * Mounted under <QueryClientProvider> so it can call useFeatureFlagEnabled.
 * When `theme.bridge_default` resolves on for the current user AND the user
 * has not explicitly picked a theme yet, this component triggers
 * `applyBridgeDefaultIfUnset()` exactly once. The ThemeProvider ref-guards
 * subsequent calls so a manual ThemeToggle flip after force-apply is
 * respected.
 *
 * Renders nothing.
 */
export function BridgeDefaultApplier() {
  const enabled = useFeatureFlagEnabled('theme.bridge_default');
  const { applyBridgeDefaultIfUnset } = useTheme();

  useEffect(() => {
    if (enabled) {
      applyBridgeDefaultIfUnset();
    }
  }, [enabled, applyBridgeDefaultIfUnset]);

  return null;
}
