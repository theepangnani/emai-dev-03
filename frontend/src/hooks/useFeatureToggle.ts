import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export type FeatureVariant = 'off' | 'on_50' | 'on_for_all';

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
 * Fetch feature toggles from the backend.
 * Caches for 5 minutes and returns safe defaults while loading.
 */
export function useFeatureToggles() {
  const { data } = useQuery({
    queryKey: ['feature-toggles'],
    queryFn: fetchFeatures,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  return data ?? DEFAULTS;
}

/** Convenience check for a single feature (boolean). */
export function useFeature(key: keyof FeatureToggles): boolean {
  const toggles = useFeatureToggles();
  const value = toggles[key];
  return typeof value === 'boolean' ? value : false;
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
