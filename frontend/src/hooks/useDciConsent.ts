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

/** Read consent for a single kid. */
export function useDciConsent(kidId: number | null | undefined) {
  return useQuery<DciConsent>({
    queryKey: kidId ? KEY_ONE(kidId) : ['dciConsent', 'kid', 'none'],
    queryFn: () => dciConsentApi.get(kidId as number),
    enabled: !!kidId,
    staleTime: 30_000,
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
