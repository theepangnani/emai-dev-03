import { useQuery } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import { fetchFeatures } from '../hooks/useFeatureToggle';
import type { FeatureToggles } from '../hooks/useFeatureToggle';

const DEFAULTS: FeatureToggles = {
  google_classroom: false,
  waitlist_enabled: false,
  school_board_connectivity: false,
  report_cards: false,
  analytics: false,
};

interface FeatureGateProps {
  feature: keyof FeatureToggles;
  children: React.ReactNode;
}

export function FeatureGate({ feature, children }: FeatureGateProps) {
  const { data, isLoading } = useQuery<FeatureToggles>({
    queryKey: ['feature-toggles'],
    queryFn: fetchFeatures,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  if (isLoading) return null;
  const enabled = (data ?? DEFAULTS)[feature] ?? false;
  if (!enabled) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
