/**
 * Shared overdue-count computation (#4036)
 *
 * Single source of truth used by both `useParentDashboard` (dashboard badges)
 * and `useChildOverdueCounts` (Tutor drill tab badges) so the two surfaces
 * cannot silently drift if the archive/due-date rules change.
 */

export interface OverdueTask {
  assigned_to_user_id?: number | null;
  created_by_user_id?: number | null;
  is_completed: boolean;
  archived_at?: string | null;
  due_date?: string | null;
}

export interface ChildLike {
  student_id: number;
  user_id: number;
}

/** Compute map of child.student_id → overdue count.
 *  Matches dashboard semantics (tasks assigned-to OR created-by the child,
 *  not completed, not archived, due_date before today's midnight). */
export function computeChildOverdueCounts<T extends ChildLike>(
  children: T[],
  allTasks: readonly OverdueTask[],
): Map<number, number> {
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  return children.reduce((acc, child) => {
    const count = allTasks.filter((t) => {
      const matchesChild =
        t.assigned_to_user_id === child.user_id ||
        t.created_by_user_id === child.user_id;
      if (!matchesChild) return false;
      if (t.is_completed) return false;
      if (t.archived_at) return false;
      if (!t.due_date) return false;
      return new Date(t.due_date) < todayStart;
    }).length;
    acc.set(child.student_id, count);
    return acc;
  }, new Map<number, number>());
}
