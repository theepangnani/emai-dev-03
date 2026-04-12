import { Navigate } from 'react-router-dom';
import { useFeature } from '../hooks/useFeatureToggle';
import type { FeatureToggles } from '../hooks/useFeatureToggle';

interface FeatureGateProps {
  feature: keyof FeatureToggles;
  children: React.ReactNode;
}

export function FeatureGate({ feature, children }: FeatureGateProps) {
  const enabled = useFeature(feature);
  if (!enabled) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}
