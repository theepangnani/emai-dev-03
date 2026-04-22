import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

// CB-DEMO-001 used the legacy 'on_50'|'on_for_all' scheme (#3601).
// CB-LAND-001 added percentage-ramp variants 'on_5'|'on_25'|'on_100' (#3802).
// Both schemes coexist — new flags should use the percentage-ramp scheme.
export type FeatureVariant =
  | 'off'
  | 'on_50'
  | 'on_for_all'
  | 'on_5'
  | 'on_25'
  | 'on_100';

export interface FeatureToggles {
  google_classroom: boolean;
  waitlist_enabled: boolean;
  school_board_connectivity: boolean;
  report_cards: boolean;
  analytics: boolean;
  [key: string]: boolean | Record<string, FeatureVariant> | undefined;
  // `_variants` is a sibling map of DB-backed flag variants (#3601).
  // It is intentionally typed loosely here so existing boolean consumers
  // keep compiling; use `useFeatureVariant(key)` for typed access.
  _variants?: Record<string, FeatureVariant>;
}

const DEFAULTS: FeatureToggles = {
  google_classroom: false,
  waitlist_enabled: false,
  school_board_connectivity: false,
  report_cards: false,
  analytics: false,
  _variants: {},
};

// Export for direct query usage (e.g., FeatureGate)
export async function fetchFeatures(): Promise<FeatureToggles> {
  const { data } = await api.get<FeatureToggles>('/api/features');
  return data;
}

/**
 * Shared `useQuery` hook for the feature-toggle endpoint. Kept private so
 * both `useFeatureToggles` and `useFeature` read from a single source of
 * truth (same query key + staleTime + retry policy). Changing it once
 * updates both consumers.
 */
function useFeatureQuery() {
  return useQuery({
    queryKey: ['feature-toggles'],
    queryFn: fetchFeatures,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

/**
 * Fetch feature toggles from the backend.
 * Caches for 5 minutes and returns safe defaults while loading.
 */
export function useFeatureToggles() {
  const { data } = useFeatureQuery();
  return data ?? DEFAULTS;
}

/**
 * Per-key defaults applied while the `/api/features` query is still
 * hydrating (#3895). `waitlist_enabled` defaults to TRUE because the
 * pre-launch production posture keeps waitlist on — flipping it off is
 * a deliberate launch action, so defaulting to true prevents the
 * "Get Started" flicker on cold loads while the query resolves.
 * All other flags keep their implicit `false` default (opt-in features).
 */
const DEFAULT_DURING_LOAD: Partial<Record<keyof FeatureToggles, boolean>> = {
  waitlist_enabled: true,
};

/**
 * Convenience check for a single feature (boolean).
 *
 * Reads the raw query data directly (not `useFeatureToggles()`'s
 * resolved-with-DEFAULTS shape) so we can distinguish "still loading"
 * from "resolved to false" and apply the per-key `DEFAULT_DURING_LOAD`
 * fallback. Currently only `waitlist_enabled` defaults to `true` during
 * hydration; all other flags fall back to `false` (opt-in features).
 * See #3895 for the landing-page "Get Started" flicker this guards against.
 */
export function useFeature(key: keyof FeatureToggles): boolean {
  const { data } = useFeatureQuery();
  const value = data?.[key];
  if (typeof value === 'boolean') return value;
  return DEFAULT_DURING_LOAD[key] ?? false;
}

/**
 * Returns the A/B variant for a DB-backed feature flag (#3601).
 * Defaults to 'off' when the flag is unknown or the variant is missing.
 */
export function useFeatureVariant(key: string): FeatureVariant {
  const toggles = useFeatureToggles();
  const variants = toggles._variants ?? {};
  return variants[key] ?? 'off';
}

/**
 * Returns whether an arbitrary feature-flag key's `enabled` column is true.
 *
 * Unlike `useFeature` (which is typed to `keyof FeatureToggles` for the
 * static compile-time flags), this accepts any string key so composable
 * hooks can read DB-backed flags like `landing_v2` or `demo_landing_v1_1`
 * that aren't declared in the `FeatureToggles` interface.
 *
 * Reads from the same `useFeatureQuery` cache as `useFeature` to preserve
 * a single source of truth. Returns `false` while the query is hydrating
 * or when the key is missing / non-boolean — this is the safe default for
 * the kill-switch semantics in #3930 (enabled=false must force 'off').
 */
export function useFeatureFlagEnabled(key: string): boolean {
  const { data } = useFeatureQuery();
  if (!data) return false;
  const value = (data as Record<string, unknown>)[key];
  return typeof value === 'boolean' ? value : false;
}
