import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CalendarAssignment } from '../calendar/types';
import type { TaskItem } from '../../api/tasks';
import { tasksApi } from '../../api/tasks';
import EmptyState from '../EmptyState';

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
  currentUserId?: number;
  onToggleTask: (task: TaskItem) => void;
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
  filteredTasks,
  selectedChild,
  currentUserId,
  onToggleTask,
  onNavigateStudy,
  onDismiss,
  onCreateTask,
  onUploadMaterial,
}: ComingUpTimelineProps) {
  const navigate = useNavigate();
  const [remindingTaskId, setRemindingTaskId] = useState<number | null>(null);
  const [reminderToast, setReminderToast] = useState<string | null>(null);
  // Track locally-sent reminders to update UI instantly
  const [localReminders, setLocalReminders] = useState<Map<number, string>>(new Map());

  const handleRemind = async (task: TaskItem) => {
    setRemindingTaskId(task.id);
    try {
      const result = await tasksApi.remind(task.id);
      setLocalReminders(prev => new Map(prev).set(task.id, result.reminded_at));
      setReminderToast(`Reminder sent to ${result.assignee_name}`);
      setTimeout(() => setReminderToast(null), 4000);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to send reminder';
      setReminderToast(detail);
      setTimeout(() => setReminderToast(null), 4000);
    } finally {
      setRemindingTaskId(null);
    }
  };

  const canRemindTask = (task: TaskItem): boolean => {
    const sentAt = localReminders.get(task.id) || task.last_reminder_sent_at;
    if (!sentAt) return true;
    const hoursSince = (Date.now() - new Date(sentAt).getTime()) / (1000 * 60 * 60);
    return hoursSince >= 24;
  };

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

    // Add only overdue tasks (urgent items that shouldn't be missed)
    for (const t of filteredTasks) {
      if (t.archived_at) continue;
      if (!t.due_date) continue;
      if (t.is_completed) continue;
      const due = new Date(t.due_date);
      // Only include overdue tasks — non-overdue tasks live in Student Detail panel
      if (due >= todayStart) continue;
      items.push({
        id: t.id + 2_000_000, // offset to avoid collision with assignment ids
        title: t.title,
        type: 'task',
        courseName: t.course_name || undefined,
        childName: t.assignee_name || undefined,
        dueDate: due,
        urgency: 'overdue' as UrgencyLevel,
        isCompleted: false,
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
    const emptyActions = [];
    if (onUploadMaterial) emptyActions.push({ label: 'Upload Materials', onClick: onUploadMaterial, variant: 'secondary' as const });
    if (onCreateTask) emptyActions.push({ label: 'Create Task', onClick: onCreateTask, variant: 'secondary' as const });
    return (
      <EmptyState
        title="No upcoming assignments"
        description="Assignments from Google Classroom and overdue tasks will appear here."
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
            key={`${item.type}-${item.id}`}
            role="listitem"
            className={`pd-timeline-item ${item.urgency}${item.isCompleted ? ' completed' : ''}`}
          >
            <div className="pd-timeline-dot" aria-hidden="true" />
            <div className="pd-timeline-content">
              <div className="pd-timeline-row">
                {item.type === 'task' && (
                  <input
                    type="checkbox"
                    className="pd-timeline-checkbox"
                    checked={item.isCompleted || false}
                    aria-label={`Mark "${item.title}" as ${item.isCompleted ? 'incomplete' : 'complete'}`}
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
                      aria-label={`Study ${item.title}`}
                      onClick={() => {
                        const orig = assignmentMap.get(item.id);
                        if (orig) onNavigateStudy(orig);
                      }}
                    >
                      Study
                    </button>
                  )}
                  {item.type === 'task' && item.taskId && !item.isCompleted && (() => {
                    const task = taskMap.get(item.taskId);
                    if (!task || !task.assigned_to_user_id || task.created_by_user_id !== currentUserId) return null;
                    const canRemind = canRemindTask(task);
                    return (
                      <button
                        className={`pd-timeline-remind-btn${!canRemind ? ' reminded' : ''}`}
                        onClick={(e) => { e.stopPropagation(); handleRemind(task); }}
                        disabled={!canRemind || remindingTaskId === task.id}
                        aria-label={canRemind ? `Send reminder for ${item.title}` : 'Reminder already sent'}
                        title={canRemind ? 'Send Reminder' : 'Reminded'}
                      >
                        {remindingTaskId === task.id ? <span className="btn-spinner" /> : canRemind ? '\uD83D\uDD14' : '\u2705'}
                      </button>
                    );
                  })()}
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
      {reminderToast && <div className="toast-notification">{reminderToast}</div>}
    </section>
  );
}
