import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CalendarAssignment } from '../calendar/types';
import type { TaskItem } from '../../api/tasks';

/* ── Interfaces ──────────────────────────────────────────── */

type UrgencyLevel = 'overdue' | 'today' | 'upcoming' | 'later';

interface TimelineItem {
  id: number;
  title: string;
  type: 'assignment' | 'task';
  courseName?: string;
  courseColor?: string;
  childName?: string;
  dueDate: Date;
  urgency: UrgencyLevel;
  isCompleted?: boolean;
  priority?: string;
  taskId?: number;
}

interface ComingUpTimelineProps {
  calendarAssignments: CalendarAssignment[];
  filteredTasks: TaskItem[];
  selectedChild: number | null;
  onToggleTask: (task: TaskItem) => void;
  onNavigateStudy: (assignment: CalendarAssignment) => void;
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
  filteredTasks,
  selectedChild,
  onToggleTask,
  onNavigateStudy,
}: ComingUpTimelineProps) {
  const navigate = useNavigate();

  // Build a task lookup to quickly find TaskItem by id for toggle
  const taskMap = useMemo(() => {
    const map = new Map<number, TaskItem>();
    for (const t of filteredTasks) {
      map.set(t.id, t);
    }
    return map;
  }, [filteredTasks]);

  const timelineItems = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const sevenDaysOut = new Date(todayStart);
    sevenDaysOut.setDate(sevenDaysOut.getDate() + 8); // end of 7th day

    const items: TimelineItem[] = [];

    // Add assignments (non-task calendar items)
    for (const a of calendarAssignments) {
      if (a.itemType === 'task') continue; // tasks are handled separately below
      const due = a.dueDate;
      // Include overdue items + items within next 7 days
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
        isCompleted: false,
      });
    }

    // Add tasks
    for (const t of filteredTasks) {
      if (t.archived_at) continue;
      if (!t.due_date) continue;
      const due = new Date(t.due_date);
      if (due >= sevenDaysOut) continue;
      // Skip completed tasks that are not overdue
      if (t.is_completed && due >= todayStart) continue;
      items.push({
        id: t.id + 2_000_000, // offset to avoid collision with assignment ids
        title: t.title,
        type: 'task',
        courseName: t.course_name || undefined,
        childName: t.assignee_name || undefined,
        dueDate: due,
        urgency: getUrgency(due),
        isCompleted: t.is_completed,
        priority: t.priority || undefined,
        taskId: t.id,
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
  }, [calendarAssignments, filteredTasks]);

  // Find the original CalendarAssignment for "Study" button navigation
  const assignmentMap = useMemo(() => {
    const map = new Map<number, CalendarAssignment>();
    for (const a of calendarAssignments) {
      if (a.itemType !== 'task') map.set(a.id, a);
    }
    return map;
  }, [calendarAssignments]);

  if (timelineItems.length === 0) {
    return (
      <section className="pd-timeline-section">
        <div className="pd-timeline-header">
          <h3 className="pd-timeline-heading">Coming Up</h3>
        </div>
        <div className="pd-timeline-empty">
          <span className="pd-timeline-empty-icon">&#127774;</span>
          <p>Nothing coming up &mdash; enjoy the break!</p>
        </div>
      </section>
    );
  }

  const displayed = timelineItems.slice(0, 10);

  return (
    <section className="pd-timeline-section">
      <div className="pd-timeline-header">
        <h3 className="pd-timeline-heading">Coming Up</h3>
        <button
          className="pd-timeline-view-all"
          onClick={() => navigate('/tasks')}
        >
          View All Tasks
        </button>
      </div>

      <div className="pd-timeline">
        {displayed.map(item => (
          <div
            key={`${item.type}-${item.id}`}
            className={`pd-timeline-item ${item.urgency}${item.isCompleted ? ' completed' : ''}`}
          >
            <div className="pd-timeline-dot" />
            <div className="pd-timeline-content">
              <div className="pd-timeline-row">
                {item.type === 'task' && (
                  <input
                    type="checkbox"
                    className="pd-timeline-checkbox"
                    checked={item.isCompleted || false}
                    onChange={(e) => {
                      e.stopPropagation();
                      const task = taskMap.get(item.taskId!);
                      if (task) onToggleTask(task);
                    }}
                  />
                )}
                <div className="pd-timeline-info">
                  <span className={`pd-timeline-title${item.isCompleted ? ' completed' : ''}`}>
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
                    <span className={`pd-timeline-type ${item.type}`}>
                      {item.type === 'assignment' ? 'Assignment' : 'Task'}
                    </span>
                    {!selectedChild && item.childName && (
                      <span className="pd-timeline-child">{item.childName}</span>
                    )}
                  </div>
                </div>
                <div className="pd-timeline-actions">
                  {item.type === 'assignment' && (
                    <button
                      className="pd-timeline-study-btn"
                      onClick={() => {
                        const orig = assignmentMap.get(item.id);
                        if (orig) onNavigateStudy(orig);
                      }}
                    >
                      Study
                    </button>
                  )}
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
