/**
 * useChildOverdueCounts (#4022)
 *
 * Parent-scoped hook that returns a `Map<student_id, overdue_count>` derived
 * from the dashboard payload. Surfaced so multiple pages (ParentDashboard,
 * TutorPage drill mode) can display overdue badges on the child selector
 * without duplicating the overdue-computation logic.
 *
 * The computation mirrors `useParentDashboard`'s `childOverdueCounts` memo:
 * iterate `all_tasks`, filter by child user_id + not-completed + not-archived
 * + past due_date. We compute client-side (rather than reusing
 * `child_highlights[*].overdue_count`) so the tab badge agrees with the
 * dashboard's own badge pixel-for-pixel.
 */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { parentApi } from '../api/parent';

export interface UseChildOverdueCountsOptions {
  /** Gate the underlying dashboard fetch (e.g. only when drill mode is active). */
  enabled?: boolean;
}

export function useChildOverdueCounts(
  { enabled = true }: UseChildOverdueCountsOptions = {},
): Map<number, number> {
  const { data } = useQuery({
    queryKey: ['parent-dashboard-overdue-counts'],
    queryFn: () => parentApi.getDashboard(),
    enabled,
    staleTime: 60_000,
  });

  return useMemo(() => {
    const map = new Map<number, number>();
    if (!data) return map;
    const children = data.children ?? [];
    const allTasks = data.all_tasks ?? [];
    if (children.length === 0) return map;
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    for (const child of children) {
      let overdue = 0;
      for (const t of allTasks) {
        const assignedTo = (t as { assigned_to_user_id?: number | null }).assigned_to_user_id;
        const createdBy = (t as { created_by_user_id?: number | null }).created_by_user_id;
        if (assignedTo !== child.user_id && createdBy !== child.user_id) continue;
        if ((t as { is_completed?: boolean }).is_completed) continue;
        if ((t as { archived_at?: string | null }).archived_at) continue;
        const dueDate = (t as { due_date?: string | null }).due_date;
        if (!dueDate) continue;
        const dateStr = dueDate.length === 10 ? `${dueDate}T00:00:00` : dueDate;
        if (new Date(dateStr) < todayStart) overdue += 1;
      }
      if (overdue > 0) map.set(child.student_id, overdue);
    }
    return map;
  }, [data]);
}
