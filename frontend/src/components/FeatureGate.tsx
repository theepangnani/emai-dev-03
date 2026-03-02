import { ReactNode } from 'react';
import { useFeatureFlag } from '../hooks/useFeatureFlag';

interface FeatureGateProps {
  /** The feature flag key to check (e.g. "google_classroom"). */
  flag: string;
  /** Content to render when the feature is enabled. */
  children: ReactNode;
  /** Optional content to render when the feature is disabled. Defaults to null. */
  fallback?: ReactNode;
}

/**
 * Conditionally renders children based on a feature flag.
 *
 * Usage:
 *   <FeatureGate flag="google_classroom">
 *     <GoogleClassroomSection />
 *   </FeatureGate>
 *
 *   <FeatureGate flag="tutor_marketplace" fallback={<ComingSoon />}>
 *     <TutorMarketplace />
 *   </FeatureGate>
 */
export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const isEnabled = useFeatureFlag(flag);
  return <>{isEnabled ? children : fallback}</>;
}
