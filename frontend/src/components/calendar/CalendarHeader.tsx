import type { CalendarViewMode } from './useCalendarNav';

interface CalendarHeaderProps {
  headerLabel: string;
  viewMode: CalendarViewMode;
  onViewModeChange: (mode: CalendarViewMode) => void;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
}

const VIEW_MODES: { key: CalendarViewMode; label: string }[] = [
  { key: 'day', label: 'Day' },
  { key: '3day', label: '3-Day' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
];

export function CalendarHeader({ headerLabel, viewMode, onViewModeChange, onPrev, onNext, onToday }: CalendarHeaderProps) {
  return (
    <div className="cal-header">
      <div className="cal-nav">
        <button className="cal-nav-btn" onClick={onPrev} title="Previous">&lsaquo;</button>
        <button className="cal-today-btn" onClick={onToday}>Today</button>
        <button className="cal-nav-btn" onClick={onNext} title="Next">&rsaquo;</button>
      </div>
      <h2 className="cal-title">{headerLabel}</h2>
      <div className="cal-view-toggle">
        {VIEW_MODES.map(m => (
          <button
            key={m.key}
            className={`cal-view-btn${viewMode === m.key ? ' active' : ''}`}
            onClick={() => onViewModeChange(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
    </div>
  );
}
