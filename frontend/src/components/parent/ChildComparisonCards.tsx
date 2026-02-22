import type { ChildSummary, TaskItem } from '../../api/client';

/* ── Interfaces ──────────────────────────────────────────── */

interface PerChildStats {
  studentId: number;
  userId: number;
  fullName: string;
  gradeLevel: number | null;
  overdue: number;
  dueToday: number;
  totalTasks: number;
  completedTasks: number;
  completionRate: number;
  nextDeadlineTitle: string | null;
  nextDeadlineRelative: string | null;
}

interface ChildComparisonCardsProps {
  children: ChildSummary[];
  allTasks: TaskItem[];
  childColors: string[];
  onSelectChild: (studentId: number) => void;
}

/* ── Helpers ─────────────────────────────────────────────── */

function computePerChildStats(
  children: ChildSummary[],
  allTasks: TaskItem[],
): PerChildStats[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart);
  todayEnd.setDate(todayEnd.getDate() + 1);

  return children.map(child => {
    const childTasks = allTasks.filter(
      t => t.assigned_to_user_id === child.user_id || t.created_by_user_id === child.user_id
    );

    const activeTasks = childTasks.filter(t => !t.archived_at);
    const completedTasks = activeTasks.filter(t => t.is_completed).length;
    const totalTasks = activeTasks.length;

    let overdue = 0;
    let dueToday = 0;

    for (const t of activeTasks) {
      if (t.is_completed || !t.due_date) continue;
      const due = new Date(t.due_date);
      if (due < todayStart) overdue++;
      else if (due < todayEnd) dueToday++;
    }

    // Find next upcoming deadline (earliest non-completed task with due date >= today)
    let nextDeadlineTitle: string | null = null;
    let nextDeadlineRelative: string | null = null;
    let nextDeadlineDate: Date | null = null;

    for (const t of activeTasks) {
      if (t.is_completed || !t.due_date) continue;
      const due = new Date(t.due_date);
      if (due < todayStart) continue; // skip overdue
      if (!nextDeadlineDate || due < nextDeadlineDate) {
        nextDeadlineDate = due;
        nextDeadlineTitle = t.title;
      }
    }

    if (nextDeadlineDate) {
      nextDeadlineRelative = formatRelative(nextDeadlineDate, todayStart, todayEnd);
    }

    return {
      studentId: child.student_id,
      userId: child.user_id,
      fullName: child.full_name,
      gradeLevel: child.grade_level,
      overdue,
      dueToday,
      totalTasks,
      completedTasks,
      completionRate: totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 100,
      nextDeadlineTitle,
      nextDeadlineRelative,
    };
  });
}

function formatRelative(date: Date, todayStart: Date, todayEnd: Date): string {
  const tomorrowEnd = new Date(todayEnd);
  tomorrowEnd.setDate(tomorrowEnd.getDate() + 1);

  if (date < todayEnd) return 'Today';
  if (date < tomorrowEnd) return 'Tomorrow';
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

function getInitial(name: string): string {
  return name.charAt(0).toUpperCase();
}

/* ── Component ───────────────────────────────────────────── */

export function ChildComparisonCards({
  children,
  allTasks,
  childColors,
  onSelectChild,
}: ChildComparisonCardsProps) {
  const stats = computePerChildStats(children, allTasks);

  return (
    <section className="pd-compare-section">
      <div className="pd-compare-row">
        {stats.map((child, index) => {
          const color = childColors[index % childColors.length];
          const hasOverdue = child.overdue > 0;
          const allClear = child.overdue === 0 && child.dueToday === 0;

          return (
            <div
              key={child.studentId}
              className={`pd-compare-card${hasOverdue ? ' has-overdue' : ''}`}
            >
              {/* Avatar */}
              <div className="pd-compare-avatar" style={{ backgroundColor: color }}>
                {getInitial(child.fullName)}
              </div>

              {/* Name + grade */}
              <div className="pd-compare-name">{child.fullName}</div>
              {child.gradeLevel != null && (
                <div className="pd-compare-grade">Grade {child.gradeLevel}</div>
              )}

              {/* Stats */}
              <div className="pd-compare-stats">
                {hasOverdue && (
                  <span className="pd-compare-stat overdue">
                    {child.overdue} overdue
                  </span>
                )}
                {child.dueToday > 0 && (
                  <span className="pd-compare-stat today">
                    {child.dueToday} due today
                  </span>
                )}
                {allClear && (
                  <span className="pd-compare-stat clear">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: '-2px' }}>
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    {' '}All clear
                  </span>
                )}
              </div>

              {/* Progress bar */}
              <div className="pd-compare-progress-wrap">
                <div className="pd-compare-progress-bar">
                  <div
                    className="pd-compare-progress-fill"
                    style={{ width: `${child.completionRate}%`, backgroundColor: color }}
                  />
                </div>
                <span className="pd-compare-progress-label">{child.completionRate}% done</span>
              </div>

              {/* Next deadline */}
              {child.nextDeadlineTitle && (
                <div className="pd-compare-next">
                  <span className="pd-compare-next-label">Next:</span>
                  <span className="pd-compare-next-title">{child.nextDeadlineTitle}</span>
                  <span className="pd-compare-next-when">{child.nextDeadlineRelative}</span>
                </div>
              )}

              {/* View button */}
              <button
                className="pd-compare-view-btn"
                onClick={() => onSelectChild(child.studentId)}
              >
                View
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
