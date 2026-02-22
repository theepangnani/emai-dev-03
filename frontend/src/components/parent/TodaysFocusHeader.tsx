import type { ChildSummary } from '../../api/client';
import type { InspirationData } from '../DashboardLayout';

interface TodaysFocusHeaderProps {
  children: ChildSummary[];
  selectedChild: number | null;
  selectedChildFirstName: string | null;
  taskCounts: { overdue: number; dueToday: number; upcoming: number };
  pendingInviteCount: number;
  perChildOverdue: { name: string; overdue: number }[];
  focusDismissed: boolean;
  onDismiss: () => void;
  onNavigate: (path: string) => void;
}

export function TodaysFocusHeader({
  children: childList,
  selectedChild,
  selectedChildFirstName,
  taskCounts,
  pendingInviteCount,
  perChildOverdue,
  focusDismissed,
  onDismiss,
  onNavigate,
}: TodaysFocusHeaderProps) {
  return (inspiration: InspirationData | null) => {
    if (focusDismissed) return null;

    const { overdue, dueToday, upcoming } = taskCounts;
    const inviteCount = pendingInviteCount;
    const allClear = overdue === 0 && dueToday === 0 && upcoming === 0 && inviteCount === 0;
    const childLabel = selectedChildFirstName ?? (childList.length === 1 ? childList[0]?.full_name?.split(' ')[0] : null);

    const allChildNames = childList.map(c => c.full_name.split(' ')[0]);
    let heroHeadline: React.ReactNode;
    let heroClass = 'pd-hero-headline';

    if (allClear) {
      heroClass += ' pd-hero-clear';
      if (childLabel) {
        heroHeadline = `All caught up! ${childLabel} is on track.`;
      } else if (allChildNames.length > 0) {
        heroHeadline = `All caught up! ${allChildNames.join(' and ')} are on track.`;
      } else {
        heroHeadline = 'All caught up!';
      }
    } else if (overdue > 0) {
      heroClass += ' pd-hero-overdue';
      if (childLabel) {
        heroHeadline = <>{childLabel} has <span className="pd-hero-count">{overdue}</span> overdue task{overdue !== 1 ? 's' : ''}.</>;
      } else {
        heroHeadline = <>Your kids have <span className="pd-hero-count">{overdue}</span> overdue task{overdue !== 1 ? 's' : ''}.</>;
      }
    } else {
      if (childLabel) {
        heroHeadline = `${childLabel}'s Focus`;
      } else {
        heroHeadline = "Today's Focus";
      }
    }

    return (
      <div className="pd-today-focus-header">
        <div className="pd-today-focus-main">
          <div className="pd-today-focus-status">
            <div>
              <div className={heroClass}>{heroHeadline}</div>
              {!selectedChild && childList.length > 1 && perChildOverdue.length > 0 && (
                <div className="pd-hero-breakdown">
                  {perChildOverdue.map((c, i) => (
                    <span key={c.name}>
                      {i > 0 && ' \u00B7 '}
                      {c.name}: {c.overdue}
                    </span>
                  ))}
                </div>
              )}
              <div className="pd-today-focus-items">
                {overdue > 0 && (
                  <button type="button" className="pd-focus-tag overdue" onClick={() => onNavigate('/tasks?due=overdue')}>{overdue} overdue</button>
                )}
                {dueToday > 0 && (
                  <button type="button" className="pd-focus-tag today" onClick={() => onNavigate('/tasks?due=today')}>{dueToday} due today</button>
                )}
                {upcoming > 0 && (
                  <button type="button" className="pd-focus-tag upcoming" onClick={() => onNavigate('/tasks?due=week')}>{upcoming} next 3 days</button>
                )}
                {inviteCount > 0 && (
                  <button type="button" className="pd-focus-tag invites" onClick={() => onNavigate('/my-kids')}>{inviteCount} pending invite{inviteCount !== 1 ? 's' : ''}</button>
                )}
              </div>
            </div>
          </div>
        </div>
        {inspiration && (
          <div className="pd-today-focus-inspiration">
            <span className="pd-today-focus-quote">"{inspiration.text}"</span>
            {inspiration.author && (
              <span className="pd-today-focus-author"> — {inspiration.author}</span>
            )}
          </div>
        )}
        <button
          className="pd-today-focus-close"
          onClick={onDismiss}
          aria-label="Close Today's Focus"
        >
          {'\u00D7'}
        </button>
      </div>
    );
  };
}
