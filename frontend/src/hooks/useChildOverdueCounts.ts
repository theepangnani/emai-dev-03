/**
 * useChildOverdueCounts (#4022)
 *
 * Parent-scoped hook that returns a `Map<student_id, overdue_count>` derived
 * from the dashboard payload. Surfaced so multiple pages (ParentDashboard,
 * TutorPage drill mode) can display overdue badges on the child selector
 * without duplicating the overdue-computation logic.
 *
 * The computation is delegated to the shared `computeChildOverdueCounts` util
 * so the Tutor drill tab and the dashboard itself cannot silently drift when
 * the archive/due-date rules change (#4036).
 */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { parentApi } from '../api/parent';
import { computeChildOverdueCounts, type OverdueTask } from '../utils/overdue';

export interface UseChildOverdueCountsOptions {
  /** Gate the underlying dashboard fetch (e.g. only when drill mode is active). */
  enabled?: boolean;
}

export function useChildOverdueCounts(
  { enabled = true }: UseChildOverdueCountsOptions = {},
): Map<number, number> {
  const { data } = useQuery({
    // #4036: queryKey is reserved for a future React Query migration of
    // useParentDashboard so the two surfaces can dedupe their fetch. Today
    // useParentDashboard uses useState/useEffect and does NOT share this
    // cache entry — the util below is what keeps the two computations in
    // lockstep.
    queryKey: ['parent-dashboard'],
    queryFn: () => parentApi.getDashboard(),
    enabled,
    staleTime: 60_000,
  });

  return useMemo(() => {
    if (!data) return new Map<number, number>();
    const children = data.children ?? [];
    const allTasks = (data.all_tasks ?? []) as unknown as OverdueTask[];
    if (children.length === 0) return new Map<number, number>();
    const full = computeChildOverdueCounts(children, allTasks);
    // Preserve historical consumer contract: only surface children with > 0
    // overdue tasks so ChildSelectorTabs can rely on `.get(id) ?? 0` as a
    // truthy badge test.
    const trimmed = new Map<number, number>();
    for (const [studentId, count] of full) {
      if (count > 0) trimmed.set(studentId, count);
    }
    return trimmed;
  }, [data]);
}
