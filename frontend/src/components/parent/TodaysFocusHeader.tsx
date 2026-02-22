import type { ChildSummary } from '../../api/client';
import type { InspirationData } from '../DashboardLayout';

interface TodaysFocusHeaderProps {
  children: ChildSummary[];
  selectedChild: number | null;
  selectedChildFirstName: string | null;
  taskCounts: { overdue: number; dueToday: number; upcoming: number };
  pendingInviteCount: number;
  perChildOverdue: { name: string; overdue: number }[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNavigate: (path: string) => void;
}

export function TodaysFocusHeader({
  children: childList,
  selectedChild,
  selectedChildFirstName,
  taskCounts,
  pendingInviteCount,
  perChildOverdue,
  collapsed,
  onToggleCollapse,
  onNavigate,
}: TodaysFocusHeaderProps) {
  return (inspiration: InspirationData | null) => {
    const { overdue, dueToday, upcoming } = taskCounts;
    const inviteCount = pendingInviteCount;
    const allClear = overdue === 0 && dueToday === 0 && upcoming === 0 && inviteCount === 0;

    // Collapsed state: thin summary bar
    if (collapsed) {
      const counts: React.ReactNode[] = [];
      if (overdue > 0) counts.push(<span key="o" className="pd-focus-count-item overdue">{overdue} overdue</span>);
      if (dueToday > 0) counts.push(<span key="t" className="pd-focus-count-item today">{dueToday} due today</span>);
      if (upcoming > 0) counts.push(<span key="u" className="pd-focus-count-item upcoming">{upcoming} upcoming</span>);
      if (inviteCount > 0) counts.push(<span key="i" className="pd-focus-count-item">{inviteCount} invite{inviteCount !== 1 ? 's' : ''}</span>);
      if (allClear) counts.push(<span key="c" className="pd-focus-count-item">All clear</span>);

      return (
        <div className="pd-today-focus-header pd-focus-collapsed" onClick={onToggleCollapse} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleCollapse(); } }}>
          <div className="pd-focus-collapsed-content">
            <span className="pd-focus-collapsed-label">Today's Focus</span>
            <div className="pd-focus-collapsed-counts">
              {counts.map((node, i) => (
                <span key={i}>
                  {i > 0 && <span className="pd-focus-separator"> {'\u00B7'} </span>}
                  {node}
                </span>
              ))}
            </div>
          </div>
          <button className="pd-focus-expand-btn" aria-label="Expand Today's Focus">{'\u25BC'}</button>
        </div>
      );
    }

    // Expanded state: full header
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
          onClick={onToggleCollapse}
          aria-label="Collapse Today's Focus"
        >
          {'\u25B2'}
        </button>
      </div>
    );
  };
}
