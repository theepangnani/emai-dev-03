import { useFeatureFlagEnabled } from './useFeatureToggle';

/**
 * Returns whether the `tutor_chat_enabled` feature flag is on.
 *
 * This gates CB-TUTOR-002 Phase 1 — the chat-first Q&A experience. The flag
 * is paywall-relevant: flipping it on exposes a billing-sensitive surface,
 * so this helper is a thin wrapper around `useFeatureFlagEnabled` to keep
 * call sites self-documenting and greppable.
 *
 * Returns `false` while the `/api/features` query is hydrating and when the
 * flag row is missing or explicitly disabled — matches the kill-switch
 * semantics from #3930.
 */
export function useTutorChatEnabled(): boolean {
  return useFeatureFlagEnabled('tutor_chat_enabled');
}
