import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

interface FeatureToggles {
  google_classroom: boolean;
}

const DEFAULTS: FeatureToggles = {
  google_classroom: false,
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
