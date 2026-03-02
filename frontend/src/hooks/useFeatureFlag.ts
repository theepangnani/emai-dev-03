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

// Phase 1 Core
export const FLAG_GOOGLE_CLASSROOM = 'google_classroom';
export const FLAG_AI_STUDY_TOOLS = 'ai_study_tools';
export const FLAG_MESSAGING = 'messaging';
export const FLAG_TEACHER_EMAIL_MONITORING = 'teacher_email_monitoring';
export const FLAG_NOTIFICATION_SYSTEM = 'notification_system';
export const FLAG_INSPIRATION_MESSAGES = 'inspiration_messages';

// Phase 1.5-2
export const FLAG_GOOGLE_CALENDAR = 'google_calendar';
export const FLAG_DOCUMENT_REPOSITORY = 'document_repository';
export const FLAG_GRADE_TRACKING = 'grade_tracking';
export const FLAG_PWA_OFFLINE = 'pwa_offline';
export const FLAG_NOTES_PROJECTS = 'notes_projects';
export const FLAG_FAQ_KNOWLEDGE_BASE = 'faq_knowledge_base';

// Phase 2+
export const FLAG_PUSH_NOTIFICATIONS = 'push_notifications';
export const FLAG_MULTI_LMS = 'multi_lms';

// Phase 3
export const FLAG_SCHOOL_BOARD_INTEGRATION = 'school_board_integration';
export const FLAG_COURSE_PLANNING = 'course_planning';
export const FLAG_AI_WRITING_ASSISTANT = 'ai_writing_assistant';
export const FLAG_AI_MOCK_EXAMS = 'ai_mock_exams';
export const FLAG_PARENT_FORUM = 'parent_forum';
export const FLAG_TEACHER_RESOURCES = 'teacher_resources';
export const FLAG_STUDENT_ENGAGEMENT = 'student_engagement';

// Phase 4+ (original flags)
export const FLAG_AI_EMAIL_AGENT = 'ai_email_agent';
export const FLAG_TUTOR_MARKETPLACE = 'tutor_marketplace';
export const FLAG_LESSON_PLANNER = 'lesson_planner';
export const FLAG_AI_PERSONALIZATION = 'ai_personalization';
export const FLAG_BRIGHTSPACE_LMS = 'brightspace_lms';
export const FLAG_STRIPE_BILLING = 'stripe_billing';
export const FLAG_MCP_TOOLS = 'mcp_tools';
export const FLAG_BETA_FEATURES = 'beta_features';

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
