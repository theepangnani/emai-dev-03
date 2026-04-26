// CB-DCI-001 M0-11 — useDciConsent hook (#4148)
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dciConsentApi, type DciConsent, type DciConsentUpdate } from '../api/dciConsent';

const KEY_LIST = ['dciConsent', 'list'] as const;
const KEY_ONE = (kidId: number) => ['dciConsent', 'kid', kidId] as const;

/** List consent rows for every kid linked to the current parent. */
export function useDciConsentList(enabled: boolean = true) {
  return useQuery<DciConsent[]>({
    queryKey: KEY_LIST,
    queryFn: dciConsentApi.list,
    enabled,
    // Consent is parent-controlled and rarely changes — keep cache fresh
    // for 30s to avoid hammering the API while the parent toggles fields.
    staleTime: 30_000,
  });
}

/**
 * Read consent for a single kid.
 *
 * #4267: A 404 from `/api/dci/consent/{kid_id}` is the legitimate
 * "no consent row yet" state — the most common first-visit case for a
 * new parent. We retry only on 5xx server errors so the redirect
 * decision fires in a single roundtrip instead of waiting for the
 * global `retry: 1` to chew through a deterministic 404. 4xx errors
 * (404 / 403) are propagated immediately as `isError=true` so the
 * consumer can route to /dci/consent without a 1-2s blank state.
 */
export function useDciConsent(kidId: number | null | undefined) {
  return useQuery<DciConsent>({
    queryKey: kidId ? KEY_ONE(kidId) : ['dciConsent', 'kid', 'none'],
    queryFn: () => dciConsentApi.get(kidId as number),
    enabled: !!kidId,
    staleTime: 30_000,
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      // Retry only on transient 5xx; deterministic 4xx (404 = no consent
      // yet, 403 = wrong role) should never retry.
      if (typeof status === 'number' && status < 500) return false;
      return failureCount < 1;
    },
  });
}

/** Mutation to upsert consent fields. */
export function useUpsertDciConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: DciConsentUpdate) => dciConsentApi.upsert(update),
    onSuccess: (data: DciConsent) => {
      queryClient.invalidateQueries({ queryKey: KEY_LIST });
      queryClient.invalidateQueries({ queryKey: KEY_ONE(data.kid_id) });
    },
  });
}
