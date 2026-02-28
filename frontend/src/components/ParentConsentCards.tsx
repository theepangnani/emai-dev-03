import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { ParentConsentCard } from './ParentConsentCard';

interface ChildSummary {
  student_id: number;
  full_name: string;
}

interface ConsentInfo {
  student_id: number;
  full_name: string;
  consent_status: string;
  requires_parent_consent: boolean;
  parent_consent_given: boolean;
}

interface Props {
  children: ChildSummary[];
}

async function fetchConsentStatuses(children: ChildSummary[]): Promise<ConsentInfo[]> {
  if (!children.length) return [];
  const results = await Promise.allSettled(
    children.map(async (child) => {
      const resp = await api.get(`/api/consent/status/${child.student_id}`);
      return { ...resp.data, full_name: child.full_name } as ConsentInfo;
    })
  );
  const pending: ConsentInfo[] = [];
  for (const result of results) {
    if (result.status === 'fulfilled') {
      if (result.value.requires_parent_consent && !result.value.parent_consent_given) {
        pending.push(result.value);
      }
    }
  }
  return pending;
}

/**
 * Fetches consent status for all linked children and renders ParentConsentCard
 * for each child that needs parent consent (#783).
 */
export function ParentConsentCards({ children }: Props) {
  const queryClient = useQueryClient();
  const childIds = children.map(c => c.student_id).sort().join(',');

  const { data: needsConsent = [] } = useQuery({
    queryKey: ['parent-consent-status', childIds],
    queryFn: () => fetchConsentStatuses(children),
    enabled: children.length > 0,
    staleTime: 60_000,
  });

  const handleConsentGiven = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['parent-consent-status'] });
  }, [queryClient]);

  if (needsConsent.length === 0) return null;

  return (
    <>
      {needsConsent.map((child) => (
        <ParentConsentCard
          key={child.student_id}
          child={child}
          onConsentGiven={handleConsentGiven}
        />
      ))}
    </>
  );
}
