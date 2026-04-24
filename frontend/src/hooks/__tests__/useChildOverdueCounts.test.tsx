/**
 * useChildOverdueCounts (#4028 → revised under #4036).
 *
 * Verifies that the hook computes the overdue map correctly from the
 * dashboard payload (no fields are lost when the Task type is tightened
 * upstream).
 *
 * NOTE: the original #4028 test asserted a shared `['parent-dashboard']`
 * queryKey for React Query dedupe with `useParentDashboard`. That dedupe
 * never actually fires today — `useParentDashboard` uses useState + a
 * `loadDashboard()` imperative fetch, not React Query — so the assertion
 * was false reassurance. Investigation under #4036 downgraded the key to
 * "reserved for a future migration" and removed the cache-key-sharing
 * assertion. The lockstep guarantee now comes from the shared
 * `computeChildOverdueCounts` util (see `utils/overdue.ts`).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useChildOverdueCounts } from '../useChildOverdueCounts';
import { parentApi } from '../../api/parent';

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }
  return { Wrapper, queryClient };
}

describe('useChildOverdueCounts (#4036)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('computes overdue counts per child from dashboard payload', async () => {
    // Far-enough-past date that any local-time date parsing difference still
    // registers as overdue.
    const past = new Date();
    past.setDate(past.getDate() - 5);
    const pastStr = past.toISOString().slice(0, 10);
    const future = new Date();
    future.setDate(future.getDate() + 5);
    const futureStr = future.toISOString().slice(0, 10);

    const payload = {
      children: [
        { student_id: 1, user_id: 100, full_name: 'Kid A' },
        { student_id: 2, user_id: 200, full_name: 'Kid B' },
      ],
      google_connected: false,
      unread_messages: 0,
      total_overdue: 0,
      total_due_today: 0,
      total_tasks: 0,
      child_highlights: [],
      all_assignments: [],
      all_tasks: [
        // Kid A: overdue (counts)
        { id: 1, title: 't1', assigned_to_user_id: 100, created_by_user_id: null,
          is_completed: false, archived_at: null, due_date: pastStr },
        // Kid A: not due yet (skip)
        { id: 2, title: 't2', assigned_to_user_id: 100, created_by_user_id: null,
          is_completed: false, archived_at: null, due_date: futureStr },
        // Kid A: completed (skip)
        { id: 3, title: 't3', assigned_to_user_id: 100, created_by_user_id: null,
          is_completed: true, archived_at: null, due_date: pastStr },
        // Kid B: overdue (counts)
        { id: 4, title: 't4', assigned_to_user_id: 200, created_by_user_id: null,
          is_completed: false, archived_at: null, due_date: pastStr },
      ],
    };
    vi.spyOn(parentApi, 'getDashboard').mockResolvedValue(payload as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useChildOverdueCounts(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.size).toBeGreaterThan(0), { timeout: 3000 });
    expect(result.current.get(1)).toBe(1);
    expect(result.current.get(2)).toBe(1);
  });
});
