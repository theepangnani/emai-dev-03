/**
 * Hook that filters nav items based on feature flags.
 * Each guard agent adds its own filter logic here.
 *
 * Usage in DashboardLayout (or any nav builder):
 *   const filterNav = useNavItemFilter();
 *   const visibleItems = filterNav(rawNavItems);
 */
import { useFeatureFlags } from './useFeatureFlag';

/**
 * Map of nav-item paths to the feature flag key that must be enabled
 * for that item to appear. Add entries here when gating new nav items.
 */
export const NAV_FLAG_MAP: Record<string, string> = {
  // Google Classroom — no dedicated top-level nav item currently,
  // but if one is added in the future, map it here:
  // '/google-classroom': 'google_classroom',
};

/**
 * Returns a filter function that removes nav items whose required
 * feature flag is disabled.
 */
export function useNavItemFilter() {
  const { flags } = useFeatureFlags();

  return <T extends { path: string }>(items: T[]): T[] => {
    return items.filter(item => {
      const requiredFlag = NAV_FLAG_MAP[item.path];
      if (requiredFlag && !flags[requiredFlag]) return false;
      return true;
    });
  };
}
