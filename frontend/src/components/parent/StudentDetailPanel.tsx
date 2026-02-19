import { useState, useMemo } from 'react';
import type { TaskItem } from '../../api/tasks';
import './StudentDetailPanel.css';

/* ── Interfaces ────────────────────────────────────────────── */

export type { TaskItem };

export interface CourseInfo {
  id: number;
  name: string;
  google_classroom_id?: string;
}

export interface CourseMaterial {
  id: number;
  title: string;
  guide_type: 'study_guide' | 'quiz' | 'flashcards';
  created_at: string;
}

export interface StudentDetailPanelProps {
  selectedChildName: string | null; // null = "All Children" mode
  courses: CourseInfo[];
  courseMaterials: CourseMaterial[];
  tasks: TaskItem[];
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onGoToCourse: (courseId: number) => void;
  onViewMaterial: (material: CourseMaterial) => void;
  onToggleTask: (task: TaskItem) => void;
  onTaskClick?: (task: TaskItem) => void;
  onViewAllTasks: () => void;
  onViewAllMaterials: () => void;
}

/* ── Constants ─────────────────────────────────────────────── */

const COURSE_COLORS = [
  '#4285f4', '#ea4335', '#34a853', '#fbbc04', '#ff6d01',
  '#46bdc6', '#7baaf7', '#f07b72', '#57bb8a', '#e8710a',
];

const MATERIAL_ICONS: Record<CourseMaterial['guide_type'], string> = {
  study_guide: '\uD83D\uDCD8', // open book
  quiz: '\u2753',               // question mark
  flashcards: '\uD83C\uDCCF',  // joker card
};

const MATERIAL_LABELS: Record<CourseMaterial['guide_type'], string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
};

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const MAX_RECENT_MATERIALS = 5;

/* ── Helpers ───────────────────────────────────────────────── */

interface UrgencyGroups {
  overdue: TaskItem[];
  today: TaskItem[];
  upcoming: TaskItem[];
  other: TaskItem[];
}

function categorizeTasks(tasks: TaskItem[]): UrgencyGroups {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart);
  todayEnd.setDate(todayEnd.getDate() + 1);
  const threeDaysEnd = new Date(todayStart);
  threeDaysEnd.setDate(threeDaysEnd.getDate() + 4);

  const groups: UrgencyGroups = { overdue: [], today: [], upcoming: [], other: [] };

  for (const task of tasks) {
    // Filter out archived tasks
    if (task.archived_at) continue;

    if (!task.due_date) {
      groups.other.push(task);
      continue;
    }

    const due = new Date(task.due_date);

    if (due < todayStart && !task.is_completed) {
      groups.overdue.push(task);
    } else if (due >= todayStart && due < todayEnd) {
      groups.today.push(task);
    } else if (due >= todayEnd && due < threeDaysEnd) {
      groups.upcoming.push(task);
    } else {
      groups.other.push(task);
    }
  }

  return groups;
}

function daysOverdue(dueDateStr: string): number {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const due = new Date(dueDateStr);
  const diff = todayStart.getTime() - due.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function dayLabel(dueDateStr: string): string {
  const due = new Date(dueDateStr);
  return DAY_NAMES[due.getDay()];
}

/* ── Chevron sub-component ─────────────────────────────────── */

function Chevron({ expanded }: { expanded: boolean }) {
  return (
    <span className={`sdp-chevron${expanded ? ' expanded' : ''}`}>
      {'\u25B6'}
    </span>
  );
}

/* ── Component ─────────────────────────────────────────────── */

export function StudentDetailPanel({
  selectedChildName,
  courses,
  courseMaterials,
  tasks,
  collapsed,
  onToggleCollapsed,
  onGoToCourse,
  onViewMaterial,
  onToggleTask,
  onTaskClick,
  onViewAllTasks,
  onViewAllMaterials,
}: StudentDetailPanelProps) {
  const [coursesExpanded, setCoursesExpanded] = useState(false);
  const [materialsExpanded, setMaterialsExpanded] = useState(false);
  const [tasksExpanded, setTasksExpanded] = useState(true);
  const [showOtherTasks, setShowOtherTasks] = useState(false);

  const isAllChildren = selectedChildName === null;

  const recentMaterials = useMemo(
    () =>
      [...courseMaterials]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, MAX_RECENT_MATERIALS),
    [courseMaterials],
  );

  const urgencyGroups = useMemo(() => categorizeTasks(tasks), [tasks]);

  const totalActive = tasks.filter(t => !t.archived_at).length;

  /* ── Render ──────────────────────────────────────────────── */

  return (
    <div className="student-detail-panel">
      {/* Collapse/expand header */}
      <div
        className="sdp-panel-header"
        onClick={onToggleCollapsed}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleCollapsed();
          }
        }}
      >
        <Chevron expanded={!collapsed} />
        <span className="sdp-panel-title">
          {selectedChildName ? `${selectedChildName}'s Details` : 'All Children Overview'}
        </span>
        <span className="sdp-panel-summary">
          {courses.length} course{courses.length !== 1 ? 's' : ''}
          {' \u00B7 '}
          {totalActive} task{totalActive !== 1 ? 's' : ''}
          {urgencyGroups.overdue.length > 0 && (
            <span className="sdp-panel-overdue"> \u00B7 {urgencyGroups.overdue.length} overdue</span>
          )}
        </span>
      </div>

      {!collapsed && (
      <>
      {/* ── Tasks by Urgency Section (first) ─────────────── */}
      <div className="sdp-section">
        <div
          className="sdp-section-header"
          onClick={() => setTasksExpanded((v) => !v)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setTasksExpanded((v) => !v);
            }
          }}
        >
          <span>
            Tasks
            <span className="sdp-count-badge">{totalActive}</span>
          </span>
          <Chevron expanded={tasksExpanded} />
        </div>

        {tasksExpanded && (
        <div className="sdp-section-body">
          {/* Overdue */}
          {urgencyGroups.overdue.length > 0 && (
            <div className="sdp-urgency-group" data-urgency="overdue">
              <div className="sdp-urgency-header overdue">
                Overdue ({urgencyGroups.overdue.length})
              </div>
              {urgencyGroups.overdue.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  urgency="overdue"
                  badge={`${daysOverdue(task.due_date!)} days overdue`}
                  showChildName={isAllChildren}
                  onToggle={onToggleTask}
                  onClick={onTaskClick}
                />
              ))}
            </div>
          )}

          {/* Due Today */}
          {urgencyGroups.today.length > 0 && (
            <div className="sdp-urgency-group" data-urgency="today">
              <div className="sdp-urgency-header today">
                Due Today ({urgencyGroups.today.length})
              </div>
              {urgencyGroups.today.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  urgency="today"
                  badge="Today"
                  showChildName={isAllChildren}
                  onToggle={onToggleTask}
                  onClick={onTaskClick}
                />
              ))}
            </div>
          )}

          {/* Next 3 Days */}
          {urgencyGroups.upcoming.length > 0 && (
            <div className="sdp-urgency-group" data-urgency="upcoming">
              <div className="sdp-urgency-header upcoming">
                Next 3 Days ({urgencyGroups.upcoming.length})
              </div>
              {urgencyGroups.upcoming.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  urgency="upcoming"
                  badge={task.due_date ? dayLabel(task.due_date) : ''}
                  showChildName={isAllChildren}
                  onToggle={onToggleTask}
                  onClick={onTaskClick}
                />
              ))}
            </div>
          )}

          {/* Other */}
          {urgencyGroups.other.length > 0 && (
            <div className="sdp-urgency-group">
              {!showOtherTasks ? (
                <button
                  className="sdp-show-more"
                  onClick={() => setShowOtherTasks(true)}
                  type="button"
                >
                  Show {urgencyGroups.other.length} more
                </button>
              ) : (
                <>
                  {urgencyGroups.other.map((task) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      urgency={null}
                      badge={null}
                      showChildName={isAllChildren}
                      onToggle={onToggleTask}
                    />
                  ))}
                  <button
                    className="sdp-show-more"
                    onClick={() => setShowOtherTasks(false)}
                    type="button"
                  >
                    Show less
                  </button>
                </>
              )}
            </div>
          )}

          {/* Empty state — no tasks at all */}
          {urgencyGroups.overdue.length === 0 &&
            urgencyGroups.today.length === 0 &&
            urgencyGroups.upcoming.length === 0 &&
            urgencyGroups.other.length === 0 && (
              <div className="sdp-empty">No tasks</div>
            )}

          <button
            className="sdp-view-all"
            onClick={onViewAllTasks}
            type="button"
          >
            View All Tasks
          </button>
        </div>
        )}
      </div>

      {/* ── Course Materials Section ──────────────────────── */}
      <div className="sdp-section">
        <div
          className="sdp-section-header"
          onClick={() => setMaterialsExpanded((v) => !v)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setMaterialsExpanded((v) => !v);
            }
          }}
        >
          <span>
            Course Materials
            <span className="sdp-count-badge">{courseMaterials.length}</span>
          </span>
          <Chevron expanded={materialsExpanded} />
        </div>

        {materialsExpanded && (
          <div className="sdp-section-body">
            {courseMaterials.length === 0 ? (
              <div className="sdp-empty">No course materials yet</div>
            ) : (
              <>
                {recentMaterials.map((mat) => (
                  <div
                    key={mat.id}
                    className="sdp-material-item"
                    onClick={() => onViewMaterial(mat)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onViewMaterial(mat);
                      }
                    }}
                  >
                    <span className="sdp-material-icon">
                      {MATERIAL_ICONS[mat.guide_type]}
                    </span>
                    <span className="sdp-material-title">{mat.title}</span>
                    <span className="sdp-material-type-badge">
                      {MATERIAL_LABELS[mat.guide_type]}
                    </span>
                  </div>
                ))}
                <button
                  className="sdp-view-all"
                  onClick={onViewAllMaterials}
                  type="button"
                >
                  View All
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Courses Section ───────────────────────────────── */}
      <div className="sdp-section">
        <div
          className="sdp-section-header"
          onClick={() => setCoursesExpanded((v) => !v)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setCoursesExpanded((v) => !v);
            }
          }}
        >
          <span>
            Courses
            <span className="sdp-count-badge">{courses.length}</span>
          </span>
          <Chevron expanded={coursesExpanded} />
        </div>

        {coursesExpanded && (
          <div className="sdp-section-body">
            {courses.length === 0 ? (
              <div className="sdp-empty">No courses enrolled</div>
            ) : (
              courses.map((course, idx) => (
                <div
                  key={course.id}
                  className="sdp-course-item"
                  onClick={() => onGoToCourse(course.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onGoToCourse(course.id);
                    }
                  }}
                >
                  <span
                    className="sdp-course-dot"
                    style={{ backgroundColor: COURSE_COLORS[idx % COURSE_COLORS.length] }}
                  />
                  <span>{course.name}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
}

/* ── TaskRow sub-component ─────────────────────────────────── */

interface TaskRowProps {
  task: TaskItem;
  urgency: 'overdue' | 'today' | 'upcoming' | null;
  badge: string | null;
  showChildName: boolean;
  onToggle: (task: TaskItem) => void;
  onClick?: (task: TaskItem) => void;
}

function TaskRow({ task, urgency, badge, showChildName, onToggle, onClick }: TaskRowProps) {
  return (
    <div
      className={`sdp-task-item${onClick ? ' clickable' : ''}${task.is_completed ? ' completed' : ''}`}
      onClick={onClick ? () => onClick(task) : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(task); } } : undefined}
    >
      <input
        type="checkbox"
        className="sdp-task-checkbox"
        checked={task.is_completed}
        onChange={(e) => { e.stopPropagation(); onToggle(task); }}
        aria-label={`Mark "${task.title}" as ${task.is_completed ? 'incomplete' : 'complete'}`}
      />
      <span className={`sdp-task-title${task.is_completed ? ' completed' : ''}`}>
        {task.title}
      </span>
      {showChildName && task.assignee_name && (
        <span className="sdp-child-label">{task.assignee_name}</span>
      )}
      {badge && urgency && (
        <span className={`sdp-task-badge ${urgency}`}>{badge}</span>
      )}
    </div>
  );
}
