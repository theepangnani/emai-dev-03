import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export interface FeatureToggles {
  google_classroom: boolean;
  waitlist_enabled: boolean;
  school_board_connectivity: boolean;
  report_cards: boolean;
  analytics: boolean;
  [key: string]: boolean;
}

const DEFAULTS: FeatureToggles = {
  google_classroom: false,
  waitlist_enabled: false,
  school_board_connectivity: false,
  report_cards: false,
  analytics: false,
};

async function fetchFeatures(): Promise<FeatureToggles> {
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

/** Convenience check for a single feature. */
export function useFeature(key: keyof FeatureToggles): boolean {
  const toggles = useFeatureToggles();
  return toggles[key] ?? false;
}
