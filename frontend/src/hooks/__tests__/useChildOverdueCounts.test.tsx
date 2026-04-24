/**
 * useChildOverdueCounts — #4028 query-cache dedupe guard.
 *
 * Verifies that the hook:
 *  1. Uses the shared ['parent-dashboard'] queryKey so React Query
 *     dedupes its fetch with any co-located parent-dashboard consumer.
 *  2. Computes the overdue map correctly from the dashboard payload
 *     (no fields are lost when the Task type is tightened upstream).
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

describe('useChildOverdueCounts (#4028)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("uses the shared ['parent-dashboard'] queryKey for dedupe", async () => {
    const spy = vi.spyOn(parentApi, 'getDashboard').mockResolvedValue({
      children: [],
      google_connected: false,
      unread_messages: 0,
      total_overdue: 0,
      total_due_today: 0,
      total_tasks: 0,
      child_highlights: [],
      all_assignments: [],
      all_tasks: [],
    } as never);

    const { Wrapper, queryClient } = makeWrapper();
    renderHook(() => useChildOverdueCounts(), { wrapper: Wrapper });

    await waitFor(() => expect(spy).toHaveBeenCalled());
    const cached = queryClient.getQueryCache().find({ queryKey: ['parent-dashboard'] });
    expect(cached).toBeDefined();
    // Guard against regression to the old per-hook key.
    const stale = queryClient.getQueryCache().find({
      queryKey: ['parent-dashboard-overdue-counts'],
    });
    expect(stale).toBeUndefined();
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
