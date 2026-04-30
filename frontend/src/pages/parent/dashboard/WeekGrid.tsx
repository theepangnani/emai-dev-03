/**
 * CB-EDIGEST-002 E3 (#4591) — WeekGrid.
 *
 * Renders this-week's deadlines as a Mon-Sun grid with one row per kid.
 * Desktop (>= 768px): 7-column grid, kid first_name on the left.
 * Mobile (< 768px): collapses to a vertical day-list (Mon..Sun) with
 * each populated day showing per-kid items underneath; empty days
 * are hidden on mobile.
 *
 * Past days are visually de-emphasised (greyed + strike on count).
 *
 * NOTE: types defined locally for E3. E6 will reconcile shared types.
 */
import { useEffect, useState, type ReactElement } from 'react';
import './WeekGrid.css';

export interface WeekDeadline {
  id: string;
  title: string;
  course_or_context: string | null;
  source_email_id: string;
}

export interface DayBucket {
  day: string;        // ISO date "2026-04-29"
  weekday: string;    // "Mon" | "Tue" | ... computed locally if missing
  items: WeekDeadline[];
  is_past: boolean;
}

export interface KidWeekRow {
  id: number;
  first_name: string;
  days: DayBucket[];  // exactly 7 entries Mon-Sun
}

export interface WeekGridProps {
  kids: KidWeekRow[];
  onCellClick: (kid_id: number, day: DayBucket) => void;
}

const MOBILE_BREAKPOINT_PX = 768;
const WEEKDAY_FALLBACK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function computeWeekdayLabel(day: DayBucket, columnIndex: number): string {
  if (day.weekday && day.weekday.trim()) return day.weekday;
  // Fallback: trust the column index. The contract says days[] is exactly
  // Mon..Sun in order, so we don't parse day.day with `new Date(...)` —
  // that's TZ-sensitive (UTC-parsed ISO dates can land on the previous
  // weekday in negative-UTC locales).
  return WEEKDAY_FALLBACK[columnIndex] ?? '';
}

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    // Some legacy implementations don't have addEventListener on MQL.
    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    }
    const legacy = mq as unknown as {
      addListener: (h: (e: MediaQueryListEvent) => void) => void;
      removeListener: (h: (e: MediaQueryListEvent) => void) => void;
    };
    legacy.addListener(handler);
    return () => legacy.removeListener(handler);
  }, []);

  return isMobile;
}

function CellContents({ day }: { day: DayBucket }) {
  const count = day.items.length;
  const visible = day.items.slice(0, 2);
  const overflow = count - visible.length;

  if (count === 0) {
    return <span className="weekgrid-cell-empty" aria-hidden="true">·</span>;
  }
  return (
    <>
      <span
        className={`weekgrid-cell-count${day.is_past ? ' weekgrid-cell-count-past' : ''}`}
      >
        {count}
      </span>
      <ul className="weekgrid-cell-items">
        {visible.map((item) => (
          <li key={item.id} className="weekgrid-cell-item" title={item.title}>
            {item.title}
          </li>
        ))}
        {overflow > 0 && (
          <li className="weekgrid-cell-item weekgrid-cell-overflow">…</li>
        )}
      </ul>
    </>
  );
}

export function WeekGrid({ kids, onCellClick }: WeekGridProps): ReactElement {
  const isMobile = useIsMobile();

  const allEmpty =
    kids.length === 0 ||
    kids.every((kid) => kid.days.every((d) => d.items.length === 0));

  if (allEmpty) {
    return (
      <div className="weekgrid-empty" data-testid="weekgrid-empty">
        No deadlines this week
      </div>
    );
  }

  if (isMobile) {
    // Mobile: vertical day list. For each weekday column index 0..6, gather
    // populated rows across kids. Hide days where every kid has 0 items.
    const columnCount = kids[0]?.days.length ?? 7;
    const columns = Array.from({ length: columnCount }, (_, columnIndex) => {
      const rows = kids
        .map((kid) => ({ kid, day: kid.days[columnIndex] }))
        .filter((r) => r.day && r.day.items.length > 0);
      // weekday label drawn from the first kid's matching day, falls back gracefully.
      const firstDay = kids[0]?.days[columnIndex];
      const weekday = firstDay
        ? computeWeekdayLabel(firstDay, columnIndex)
        : (WEEKDAY_FALLBACK[columnIndex] ?? '');
      return { columnIndex, weekday, rows };
    }).filter((col) => col.rows.length > 0);

    return (
      <section
        className="weekgrid weekgrid-mobile"
        aria-label="This week's deadlines"
        data-testid="weekgrid-mobile"
      >
        {columns.map(({ columnIndex, weekday, rows }) => (
          <div key={columnIndex} className="weekgrid-mobile-day">
            <h3 className="weekgrid-mobile-day-heading">{weekday}</h3>
            <ul className="weekgrid-mobile-kid-list">
              {rows.map(({ kid, day }) => (
                <li key={kid.id} className="weekgrid-mobile-kid">
                  <button
                    type="button"
                    className={`weekgrid-mobile-kid-button${day.is_past ? ' weekgrid-mobile-kid-button-past' : ''}`}
                    onClick={() => onCellClick(kid.id, day)}
                  >
                    <span className="weekgrid-mobile-kid-name">{kid.first_name}</span>
                    <CellContents day={day} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    );
  }

  // Desktop: 7-col grid, one row per kid.
  return (
    <section
      className="weekgrid weekgrid-desktop"
      aria-label="This week's deadlines"
      data-testid="weekgrid-desktop"
    >
      <div className="weekgrid-header" role="row">
        <div className="weekgrid-header-name" role="columnheader" aria-label="Kid" />
        {(kids[0]?.days ?? []).map((day, columnIndex) => (
          <div
            key={day.day || columnIndex}
            className="weekgrid-header-day"
            role="columnheader"
          >
            {computeWeekdayLabel(day, columnIndex)}
          </div>
        ))}
      </div>

      {kids.map((kid) => (
        <div key={kid.id} className="weekgrid-row" role="row">
          <div className="weekgrid-row-name" role="rowheader">
            {kid.first_name}
          </div>
          {kid.days.map((day, columnIndex) => {
            const cellLabel = `${kid.first_name} — ${computeWeekdayLabel(day, columnIndex)} — ${day.items.length} ${day.items.length === 1 ? 'item' : 'items'}`;
            return (
              <button
                key={day.day || columnIndex}
                type="button"
                className={`weekgrid-cell${day.is_past ? ' weekgrid-cell-past' : ''}`}
                onClick={() => onCellClick(kid.id, day)}
                aria-label={cellLabel}
                data-testid={`weekgrid-cell-${kid.id}-${columnIndex}`}
              >
                <CellContents day={day} />
              </button>
            );
          })}
        </div>
      ))}
    </section>
  );
}
