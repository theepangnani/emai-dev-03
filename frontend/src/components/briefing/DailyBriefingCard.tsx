import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { briefingApi } from '../../api/briefing';
import type { BriefingChildSection, BriefingTask, BriefingAssignment, HelpMyKidRequest } from '../../api/briefing';
import { useToast } from '../Toast';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { briefingApi } from '../../api/briefing';
import type { BriefingChildSection, BriefingTask, BriefingAssignment } from '../../api/briefing';
import { HelpStudyMenu } from '../study/HelpStudyMenu';
import './DailyBriefingCard.css';

function BriefingSkeleton() {
  return (
    <div className="briefing-card briefing-skeleton" aria-busy="true" aria-label="Loading daily briefing">
      <div className="skeleton briefing-skeleton-greeting" />
      <div className="skeleton briefing-skeleton-date" />
      {[1, 2].map((i) => (
        <div key={i} className="briefing-skeleton-child">
          <div className="skeleton briefing-skeleton-child-name" />
          <div className="skeleton briefing-skeleton-row" style={{ width: '75%' }} />
          <div className="skeleton briefing-skeleton-row" style={{ width: '55%' }} />
        </div>
      ))}
    </div>
  );
}

function HelpMyKidMenu({
  child,
  onClose,
}: {
  child: BriefingChildSection;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const menuRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: briefingApi.helpMyKid,
    onSuccess: () => {
      toast(`Study guide created for ${child.full_name.split(' ')[0]}!`, 'success');
      onClose();
    },
    onError: () => {
      toast('Failed to create study guide. Please try again.', 'error');
    },
  });

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  const items: { label: string; req: HelpMyKidRequest }[] = [];

  for (const task of child.overdue_tasks) {
    items.push({
      label: `\u26a0 ${task.title}`,
      req: { student_id: child.student_id, item_type: 'task', item_id: task.id },
    });
  }
  for (const task of child.due_today_tasks) {
    items.push({
      label: `\u23f0 ${task.title}`,
      req: { student_id: child.student_id, item_type: 'task', item_id: task.id },
    });
  }
  for (const a of child.upcoming_assignments) {
    items.push({
      label: `\ud83d\udcda ${a.title}`,
      req: { student_id: child.student_id, item_type: 'assignment', item_id: a.id },
    });
  }

  if (items.length === 0) {
    return (
      <div className="help-my-kid-menu" ref={menuRef}>
        <div className="help-my-kid-empty">No items to create a study guide for.</div>
      </div>
    );
  }

  return (
    <div className="help-my-kid-menu" ref={menuRef}>
      <div className="help-my-kid-header">Generate study guide for:</div>
      {items.map((item, idx) => (
        <button
          key={idx}
          className="help-my-kid-item"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(item.req)}
        >
          {item.label}
          {mutation.isPending && mutation.variables === item.req && (
            <span className="help-my-kid-spinner" />
          )}
        </button>
      ))}
    </div>
  );
}

function ChildSection({ child }: { child: BriefingChildSection }) {
  const [showMenu, setShowMenu] = useState(false);
  const [showHelpMenu, setShowHelpMenu] = useState(false);
  const hasOverdue = child.overdue_tasks.length > 0;
  const hasDueToday = child.due_today_tasks.length > 0;
  const hasUpcoming = child.upcoming_assignments.length > 0;
  const allClear = !hasOverdue && !hasDueToday && !hasUpcoming;

  return (
    <div className="briefing-child-section">
      <div className="briefing-child-header">
        <span className="briefing-child-name">
          {child.needs_attention && <span className="briefing-attention-dot" />}
          {child.full_name.split(' ')[0]}
        </span>
        <div className="briefing-help-wrapper">
          <button
            className="briefing-help-btn"
            type="button"
            onClick={() => setShowMenu((v) => !v)}
          >
            Help My Kid
          </button>
          {showMenu && (
            <HelpMyKidMenu child={child} onClose={() => setShowMenu(false)} />
          )}
        </div>
        <button className="briefing-help-btn" type="button" onClick={() => setShowHelpMenu(true)}>
          Help My Kid
        </button>
      </div>
      {showHelpMenu && (
        <HelpStudyMenu
          studentId={child.student_id}
          onClose={() => setShowHelpMenu(false)}
        />
      )}

      {allClear ? (
        <div className="briefing-child-clear">All caught up!</div>
      ) : (
        <>
          {hasOverdue && (
            <TaskGroup label="Overdue" type="overdue" items={child.overdue_tasks} />
          )}
          {hasDueToday && (
            <TaskGroup label="Due Today" type="due-today" items={child.due_today_tasks} />
          )}
          {hasUpcoming && (
            <AssignmentGroup items={child.upcoming_assignments} />
          )}
        </>
      )}

      {child.recent_study_count > 0 && (
        <div className="briefing-study-activity">
          {child.recent_study_count} study session{child.recent_study_count !== 1 ? 's' : ''} recently
        </div>
      )}
    </div>
  );
}

function TaskGroup({
  label,
  type,
  items,
}: {
  label: string;
  type: 'overdue' | 'due-today';
  items: BriefingTask[];
}) {
  return (
    <div className="briefing-task-group">
      <div className={`briefing-task-label ${type}`}>
        <span className={`briefing-badge ${type}`}>{items.length}</span>
        {label}
      </div>
      {items.slice(0, 3).map((item) => (
        <div key={item.id} className="briefing-task-item">
          {item.title}
          {item.course_name && <span className="briefing-task-item-course">{item.course_name}</span>}
        </div>
      ))}
      {items.length > 3 && (
        <div className="briefing-task-item briefing-more">+{items.length - 3} more</div>
      )}
    </div>
  );
}

function AssignmentGroup({ items }: { items: BriefingAssignment[] }) {
  return (
    <div className="briefing-task-group">
      <div className="briefing-task-label upcoming">
        <span className="briefing-badge upcoming">{items.length}</span>
        Upcoming
      </div>
      {items.slice(0, 3).map((item) => (
        <div key={item.id} className="briefing-task-item">
          {item.title}
          <span className="briefing-task-item-course">{item.course_name}</span>
        </div>
      ))}
      {items.length > 3 && (
        <div className="briefing-task-item briefing-more">+{items.length - 3} more</div>
      )}
    </div>
  );
}

export function DailyBriefingCard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['briefing', 'daily'],
    queryFn: briefingApi.getDaily,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  if (isLoading) {
    return <BriefingSkeleton />;
  }

  if (isError || !data) {
    return null; // Fail silently — TodaysFocusHeader still shows as fallback
  }

  const allClear = data.children.every(
    (c) =>
      c.overdue_tasks.length === 0 &&
      c.due_today_tasks.length === 0 &&
      c.upcoming_assignments.length === 0
  );

  return (
    <div className="briefing-card">
      <h2 className="briefing-greeting">{data.greeting}</h2>
      <p className="briefing-date">{data.date}</p>

      {data.attention_needed && (
        <div className="briefing-attention-banner">
          <span>!</span>
          Some items need your attention
        </div>
      )}

      {data.children.length === 0 || allClear ? (
        <div className="briefing-all-clear">
          <span className="briefing-all-clear-icon">&#10003;</span>
          All caught up! No urgent items today.
        </div>
      ) : (
        data.children.map((child) => (
          <ChildSection key={child.student_id} child={child} />
        ))
      )}
    </div>
  );
}
