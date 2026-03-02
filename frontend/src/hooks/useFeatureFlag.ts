/**
 * Feature flag hooks.
 *
 * Usage:
 *   // Check multiple flags at once
 *   const { flags, loading } = useFeatureFlags();
 *   if (flags['ai_email_agent']) { ... }
 *
 *   // Check a single flag
 *   const isEnabled = useFeatureFlag('ai_email_agent');
 *
 * Flags are fetched once per minute (staleTime: 60_000) and shared across all
 * components via TanStack Query's cache — no duplicate network requests.
 */

import { useQuery } from '@tanstack/react-query';
import { featureFlagsApi } from '../api/featureFlags';

// ─── Pre-defined flag key constants (mirrors the backend) ─────────────────────

export const FLAG_AI_EMAIL_AGENT = 'ai_email_agent';
export const FLAG_TUTOR_MARKETPLACE = 'tutor_marketplace';
export const FLAG_LESSON_PLANNER = 'lesson_planner';
export const FLAG_AI_PERSONALIZATION = 'ai_personalization';
export const FLAG_BRIGHTSPACE_LMS = 'brightspace_lms';
export const FLAG_STRIPE_BILLING = 'stripe_billing';
export const FLAG_MCP_TOOLS = 'mcp_tools';
export const FLAG_BETA_FEATURES = 'beta_features';
export const FLAG_PWA_OFFLINE = 'pwa_offline';

// ─── Hooks ────────────────────────────────────────────────────────────────────

/**
 * Fetch all feature flags for the current user.
 * Returns a map of { flagKey: boolean } and a loading state.
 */
export function useFeatureFlags(): { flags: Record<string, boolean>; loading: boolean } {
  const { data, isLoading } = useQuery<Record<string, boolean>>({
    queryKey: ['feature-flags'],
    queryFn: () => featureFlagsApi.getAll(),
    staleTime: 60_000,  // 1-minute cache — mirrors backend TTL
    retry: false,       // Silently fail; default to false for all flags
  });

  return { flags: data ?? {}, loading: isLoading };
}

/**
 * Convenience hook to check a single feature flag.
 * Returns false while loading or if the flag does not exist.
 */
export function useFeatureFlag(key: string): boolean {
  const { flags } = useFeatureFlags();
  return flags[key] ?? false;
}
