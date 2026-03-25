import { useRef, useState, useCallback, useEffect } from 'react';
import type { ChildSummary } from '../api/client';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import { OnTrackBadge } from './OnTrackBadge';
import './ChildSelectorTabs.css';

export interface ChildSelectorTabsProps {
  children: ChildSummary[];
  selectedChild: number | null;
  onSelectChild: (studentId: number | null) => void;
  /** Map from student_id to overdue count */
  childOverdueCounts: Map<number, number>;
}

export function ChildSelectorTabs({
  children,
  selectedChild,
  onSelectChild,
  childOverdueCounts,
}: ChildSelectorTabsProps) {
  const tabsRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollIndicators = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 2);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateScrollIndicators();
    el.addEventListener('scroll', updateScrollIndicators, { passive: true });
    const ro = new ResizeObserver(updateScrollIndicators);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', updateScrollIndicators);
      ro.disconnect();
    };
  }, [updateScrollIndicators, children.length]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      const tabs = tabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
      if (!tabs || tabs.length === 0) return;
      let nextIndex = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        nextIndex = (index + 1) % tabs.length;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        nextIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (e.key === 'Home') {
        e.preventDefault();
        nextIndex = 0;
      } else if (e.key === 'End') {
        e.preventDefault();
        nextIndex = tabs.length - 1;
      }
      if (nextIndex >= 0) {
        tabs[nextIndex].focus();
        if (children.length > 1 && nextIndex === 0) {
          onSelectChild(null);
        } else {
          const childIndex = children.length > 1 ? nextIndex - 1 : nextIndex;
          onSelectChild(children[childIndex].student_id);
        }
      }
    },
    [children, onSelectChild],
  );

  return (
    <div
      className={`pd-child-selector-wrapper${canScrollLeft ? ' can-scroll-left' : ''}${canScrollRight ? ' can-scroll-right' : ''}`}
    >
      <div
        className="pd-child-selector"
        role="tablist"
        aria-label="Select child"
        ref={(el) => {
          (tabsRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
          (scrollRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
        }}
      >
        {children.length > 1 && (
          <button
            role="tab"
            aria-selected={selectedChild === null}
            tabIndex={selectedChild === null ? 0 : -1}
            className={`pd-child-tab pd-child-tab-all ${selectedChild === null ? 'active' : ''}`}
            onClick={() => onSelectChild(null)}
            onKeyDown={(e) => handleKeyDown(e, 0)}
            title="All children"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </button>
        )}
        {children.map((child, index) => {
          const isSelected = selectedChild === child.student_id;
          const overdueCount = childOverdueCounts.get(child.student_id) ?? 0;
          const tabKeyIndex = children.length > 1 ? index + 1 : index;
          return (
            <button
              key={child.student_id}
              role="tab"
              aria-selected={isSelected}
              tabIndex={
                isSelected || (selectedChild === null && children.length <= 1 && index === 0)
                  ? 0
                  : -1
              }
              className={`pd-child-tab ${isSelected ? 'active' : ''}`}
              onClick={() => onSelectChild(child.student_id)}
              onKeyDown={(e) => handleKeyDown(e, tabKeyIndex)}
            >
              <span
                className="pd-child-color-dot"
                aria-hidden="true"
                style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }}
              />
              {child.full_name}
              {child.grade_level != null && (
                <span className="pd-grade-badge">Grade {child.grade_level}</span>
              )}
              {overdueCount > 0 && (
                <span className="pd-overdue-badge" aria-label={`${overdueCount} overdue`}>
                  {overdueCount}
                </span>
              )}
              <OnTrackBadge studentId={child.student_id} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
