import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  dciSummaryApi,
  type DciSummaryResponse,
  type ConversationStarterFeedback,
  type ConversationStarterFeedbackResponse,
} from '../api/dciSummary';

/**
 * CB-DCI-001 M0-10 — TanStack Query hooks for the parent evening summary.
 *
 * Keeps the cache key stable as `['dci-summary', kidId, date]` so refetches
 * from the feedback mutation can invalidate the right entry.
 */

export function dciSummaryKey(kidId: number | null, date: string) {
  return ['dci-summary', kidId, date] as const;
}

export function useDciSummary(kidId: number | null, date: string) {
  return useQuery<DciSummaryResponse>({
    queryKey: dciSummaryKey(kidId, date),
    queryFn: () => {
      if (kidId == null) {
        return Promise.reject(new Error('kidId is required'));
      }
      return dciSummaryApi.getSummary(kidId, date);
    },
    enabled: kidId != null && !!date,
    // The summary is regenerated daily — stale-time 5 min is plenty for
    // a single page session and avoids hammering the AI pipeline.
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

interface FeedbackVars {
  starterId: number;
  feedback: ConversationStarterFeedback;
  /** Used to invalidate the right summary cache after the write */
  kidId: number;
  date: string;
}

export function useConversationStarterFeedback() {
  const qc = useQueryClient();
  return useMutation<ConversationStarterFeedbackResponse, unknown, FeedbackVars>({
    mutationFn: ({ starterId, feedback }) =>
      dciSummaryApi.submitStarterFeedback(starterId, feedback),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: dciSummaryKey(vars.kidId, vars.date) });
    },
  });
}
