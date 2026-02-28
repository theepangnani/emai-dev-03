import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CalendarAssignment } from '../calendar/types';
import EmptyState from '../EmptyState';

/* ── Interfaces ──────────────────────────────────────────── */

type UrgencyLevel = 'overdue' | 'today' | 'upcoming' | 'later';

interface TimelineItem {
  id: number;
  title: string;
  type: 'assignment';
  courseName?: string;
  courseColor?: string;
  childName?: string;
  dueDate: Date;
  urgency: UrgencyLevel;
}

interface ComingUpTimelineProps {
  calendarAssignments: CalendarAssignment[];
  selectedChild: number | null;
  onNavigateStudy: (assignment: CalendarAssignment) => void;
  onDismiss?: () => void;
  onCreateTask?: () => void;
  onUploadMaterial?: () => void;
}

/* ── Helpers ─────────────────────────────────────────────── */

function getUrgency(date: Date): UrgencyLevel {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart);
  todayEnd.setDate(todayEnd.getDate() + 1);

  if (date < todayStart) return 'overdue';
  if (date < todayEnd) return 'today';
  return 'upcoming';
}

function formatRelativeDate(date: Date): string {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart);
  tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  const dayAfterTomorrow = new Date(todayStart);
  dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2);

  if (date < todayStart) return 'Overdue';
  if (date < tomorrowStart) {
    const h = date.getHours();
    return h ? `Today at ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : 'Today';
  }
  if (date < dayAfterTomorrow) return 'Tomorrow';
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

/* ── Component ───────────────────────────────────────────── */

export function ComingUpTimeline({
  calendarAssignments,
  selectedChild,
  onNavigateStudy,
  onDismiss,
  onCreateTask,
  onUploadMaterial,
}: ComingUpTimelineProps) {
  const navigate = useNavigate();

  const timelineItems = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const sevenDaysOut = new Date(todayStart);
    sevenDaysOut.setDate(sevenDaysOut.getDate() + 8); // end of 7th day

    const items: TimelineItem[] = [];

    // Only assignments (not tasks) — tasks live exclusively in StudentDetailPanel (#929)
    for (const a of calendarAssignments) {
      if (a.itemType === 'task') continue;
      const due = a.dueDate;
      if (due >= sevenDaysOut) continue;
      items.push({
        id: a.id,
        title: a.title,
        type: 'assignment',
        courseName: a.courseName || undefined,
        courseColor: a.courseColor || undefined,
        childName: a.childName || undefined,
        dueDate: due,
        urgency: getUrgency(due),
      });
    }

    // Sort: overdue first, then today, upcoming. Within tier, nearest first
    const tierOrder: Record<UrgencyLevel, number> = { overdue: 0, today: 1, upcoming: 2, later: 3 };
    items.sort((a, b) => {
      const tierDiff = tierOrder[a.urgency] - tierOrder[b.urgency];
      if (tierDiff !== 0) return tierDiff;
      return a.dueDate.getTime() - b.dueDate.getTime();
    });

    return items;
  }, [calendarAssignments]);

  // Find the original CalendarAssignment for "Study" button navigation
  const assignmentMap = useMemo(() => {
    const map = new Map<number, CalendarAssignment>();
    for (const a of calendarAssignments) {
      if (a.itemType !== 'task') map.set(a.id, a);
    }
    return map;
  }, [calendarAssignments]);

  if (timelineItems.length === 0) {
    const emptyActions = [];
    if (onUploadMaterial) emptyActions.push({ label: 'Upload Materials', onClick: onUploadMaterial, variant: 'secondary' as const });
    if (onCreateTask) emptyActions.push({ label: 'Create Task', onClick: onCreateTask, variant: 'secondary' as const });
    return (
      <EmptyState
        title="No upcoming assignments"
        description="Assignments from Google Classroom will appear here."
        actions={emptyActions}
        variant="compact"
      />
    );
  }

  const displayed = timelineItems.slice(0, 10);

  return (
    <section className="pd-timeline-section" aria-label="Coming up timeline">
      <div className="pd-timeline-header">
        <h3 className="pd-timeline-heading">Coming Up</h3>
        <button
          className="pd-timeline-view-all"
          onClick={() => navigate('/tasks')}
        >
          View All
        </button>
        {onDismiss && (
          <button
            className="pd-timeline-dismiss"
            onClick={onDismiss}
            aria-label="Dismiss coming up section"
          >&times;</button>
        )}
      </div>

      <div className="pd-timeline" role="list">
        {displayed.map(item => (
          <div
            key={`assignment-${item.id}`}
            role="listitem"
            className={`pd-timeline-item ${item.urgency}`}
          >
            <div className="pd-timeline-dot" aria-hidden="true" />
            <div className="pd-timeline-content">
              <div className="pd-timeline-row">
                <div className="pd-timeline-info">
                  <span className="pd-timeline-title">
                    {item.title}
                  </span>
                  <div className="pd-timeline-meta">
                    <span className={`pd-timeline-date ${item.urgency}`}>
                      {formatRelativeDate(item.dueDate)}
                    </span>
                    {item.courseName && (
                      <span
                        className="pd-timeline-course"
                        style={item.courseColor ? { borderColor: item.courseColor } : undefined}
                      >
                        {item.courseName}
                      </span>
                    )}
                    <span className="pd-timeline-type assignment">
                      Assignment
                    </span>
                    {!selectedChild && item.childName && (
                      <span className="pd-timeline-child">{item.childName}</span>
                    )}
                  </div>
                </div>
                <div className="pd-timeline-actions">
                  <button
                    className="pd-timeline-study-btn"
                    aria-label={`Study ${item.title}`}
                    onClick={() => {
                      const orig = assignmentMap.get(item.id);
                      if (orig) onNavigateStudy(orig);
                    }}
                  >
                    Study
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
        {timelineItems.length > 10 && (
          <button
            className="pd-timeline-more"
            onClick={() => navigate('/tasks')}
          >
            +{timelineItems.length - 10} more items
          </button>
        )}
      </div>
    </section>
  );
}
