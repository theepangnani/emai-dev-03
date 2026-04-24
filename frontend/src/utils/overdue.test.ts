/**
 * computeChildOverdueCounts (#4036) — shared util unit tests.
 *
 * Guards the dashboard + Tutor drill tab lockstep. If this file drifts from
 * the util semantics the ChildSelectorTabs badge will silently de-sync from
 * the dashboard's own Today's Focus badge.
 */
import { describe, it, expect } from 'vitest';
import { computeChildOverdueCounts, type OverdueTask, type ChildLike } from './overdue';

const children: ChildLike[] = [
  { student_id: 1, user_id: 100 },
  { student_id: 2, user_id: 200 },
];

function daysFromNow(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString();
}

describe('computeChildOverdueCounts', () => {
  it('counts a task whose due_date is in the past', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: false, archived_at: null, due_date: daysFromNow(-3) },
    ];
    expect(computeChildOverdueCounts(children, tasks).get(1)).toBe(1);
  });

  it('does not count a task whose due_date is in the future', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: false, archived_at: null, due_date: daysFromNow(3) },
    ];
    expect(computeChildOverdueCounts(children, tasks).get(1)).toBe(0);
  });

  it('does not count a completed task', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: true, archived_at: null, due_date: daysFromNow(-3) },
    ];
    expect(computeChildOverdueCounts(children, tasks).get(1)).toBe(0);
  });

  it('does not count an archived task', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: false, archived_at: daysFromNow(-1), due_date: daysFromNow(-3) },
    ];
    expect(computeChildOverdueCounts(children, tasks).get(1)).toBe(0);
  });

  it('does not count a task with no due_date', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: false, archived_at: null, due_date: null },
    ];
    expect(computeChildOverdueCounts(children, tasks).get(1)).toBe(0);
  });

  it('matches on assigned_to_user_id', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: 100, created_by_user_id: null,
        is_completed: false, archived_at: null, due_date: daysFromNow(-3) },
    ];
    const counts = computeChildOverdueCounts(children, tasks);
    expect(counts.get(1)).toBe(1);
    expect(counts.get(2)).toBe(0);
  });

  it('matches on created_by_user_id', () => {
    const tasks: OverdueTask[] = [
      { assigned_to_user_id: null, created_by_user_id: 200,
        is_completed: false, archived_at: null, due_date: daysFromNow(-3) },
    ];
    const counts = computeChildOverdueCounts(children, tasks);
    expect(counts.get(1)).toBe(0);
    expect(counts.get(2)).toBe(1);
  });
});
