/**
 * CB-EDIGEST-002 Stripe E2 (#4590) — TodaySection.
 *
 * Vertical-stack "Urgent today, by kid" section for the email-digest
 * dashboard. Per PRD §F1 + §F6:
 *   - Kids ordered by urgent_items.length DESC, ties by id ASC.
 *   - Per-kid: ≤ 3 items rendered + "And N more →" CTA when overflow.
 *   - Kids with all_clear=true render "All clear ✓" panel.
 *   - Click an item → onItemClick(kid_id, item).
 *   - Click "And N more" → onItemClick(kid_id, null).
 *
 * Types are defined locally; Stripe E6 reconciles into shared API types.
 */
import type { JSX } from 'react';
import './TodaySection.css';

export interface UrgentItem {
  id: string;
  title: string;
  due_date: string | null;
  course_or_context: string | null;
  source_email_id: string;
}

export interface KidSection {
  id: number;
  first_name: string;
  urgent_items: UrgentItem[];
  all_clear: boolean;
}

export interface TodaySectionProps {
  kids: KidSection[];
  onItemClick: (kid_id: number, item: UrgentItem | null) => void;
}

const MAX_ITEMS_PER_KID = 3;

const WEEKDAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

/**
 * Compute a relative due-date label for the pill. Returns "Due today",
 * "Due tomorrow", or "Due {weekday}". Returns null when due_date is null
 * or unparseable so callers can omit the pill.
 *
 * Comparison is done at calendar-day granularity in the local timezone.
 */
function relativeDueLabel(dueIso: string | null, now: Date = new Date()): string | null {
  if (!dueIso) return null;
  const due = new Date(dueIso);
  if (Number.isNaN(due.getTime())) return null;

  const startOfDay = (d: Date) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

  const diffDays = Math.round(
    (startOfDay(due) - startOfDay(now)) / (24 * 60 * 60 * 1000),
  );

  if (diffDays === 0) return 'Due today';
  if (diffDays === 1) return 'Due tomorrow';
  if (diffDays > 1 && diffDays < 7) {
    return `Due ${WEEKDAY_NAMES[due.getDay()]}`;
  }
  if (diffDays < 0) return 'Overdue';
  return `Due ${WEEKDAY_NAMES[due.getDay()]}`;
}

/** Stable sort: urgent_items.length DESC, id ASC. */
function sortKids(kids: KidSection[]): KidSection[] {
  return [...kids].sort((a, b) => {
    const lenDiff = b.urgent_items.length - a.urgent_items.length;
    if (lenDiff !== 0) return lenDiff;
    return a.id - b.id;
  });
}

export function TodaySection({ kids, onItemClick }: TodaySectionProps): JSX.Element {
  const ordered = sortKids(kids);

  return (
    <section className="bridge-page today-section" aria-label="Urgent today">
      {ordered.map((kid) => {
        if (kid.all_clear) {
          return (
            <article
              key={kid.id}
              className="bridge-card today-section__kid today-section__kid--clear"
              data-testid={`today-kid-${kid.id}`}
            >
              <h3 className="today-section__kid-name">{kid.first_name}</h3>
              <div
                className="today-section__all-clear"
                data-testid={`today-kid-${kid.id}-all-clear`}
              >
                <span className="today-section__all-clear-icon" aria-hidden="true">
                  ✓
                </span>
                <span className="today-section__all-clear-text">All clear</span>
              </div>
            </article>
          );
        }

        const visible = kid.urgent_items.slice(0, MAX_ITEMS_PER_KID);
        const overflow = kid.urgent_items.length - visible.length;

        return (
          <article
            key={kid.id}
            className="bridge-card today-section__kid"
            data-testid={`today-kid-${kid.id}`}
          >
            <h3 className="today-section__kid-name">{kid.first_name}</h3>
            <ul
              className="bridge-item-list today-section__items"
              role="list"
              data-testid={`today-kid-${kid.id}-items`}
            >
              {visible.map((item) => {
                const due = relativeDueLabel(item.due_date);
                return (
                  <li
                    key={item.id}
                    className="is-clickable today-section__item"
                    data-testid={`today-item-${item.id}`}
                  >
                    <button
                      type="button"
                      className="today-section__item-button"
                      onClick={() => onItemClick(kid.id, item)}
                    >
                      <span className="bridge-item-title today-section__item-title">
                        {item.title}
                      </span>
                      <span className="today-section__item-meta">
                        {due && (
                          <span className="today-section__due-pill">{due}</span>
                        )}
                        {item.course_or_context && (
                          <span className="today-section__course-tag">
                            {item.course_or_context}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {overflow > 0 && (
              <button
                type="button"
                className="bridge-head-action today-section__more"
                onClick={() => onItemClick(kid.id, null)}
                data-testid={`today-kid-${kid.id}-more`}
              >
                And {overflow} more →
              </button>
            )}
          </article>
        );
      })}
    </section>
  );
}
