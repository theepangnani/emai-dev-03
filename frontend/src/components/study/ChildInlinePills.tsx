import { useEffect, useRef } from 'react';
import './ChildInlinePills.css';

export interface Child {
  id: number;
  name: string;
  grade?: string;
}

export interface ChildInlinePillsProps {
  childList: Child[];
  selectedChildId: number | null;
  suggestedChildId: number | null;
  courseId: number;
  onSelect: (childId: number) => void;
}

function getStorageKey(courseId: number): string {
  return `classbridge:utdf-last-child:${courseId}`;
}

export function detectGradeConflict(
  childList: Child[],
  detectedGrade: string | null,
): { suggestedChildId: number | null; isConflict: boolean } {
  if (!detectedGrade || childList.length <= 1) {
    return { suggestedChildId: null, isConflict: false };
  }
  const matches = childList.filter(
    (c) => c.grade && c.grade.includes(detectedGrade),
  );
  if (matches.length === 1) {
    return { suggestedChildId: matches[0].id, isConflict: false };
  }
  if (matches.length === 0) {
    return { suggestedChildId: null, isConflict: true };
  }
  return { suggestedChildId: null, isConflict: false };
}

export function ChildInlinePills({
  childList,
  selectedChildId,
  suggestedChildId,
  courseId,
  onSelect,
}: ChildInlinePillsProps) {
  // Stable ref for onSelect to avoid re-triggering the restore effect
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // On mount, restore last selection from localStorage
  useEffect(() => {
    if (selectedChildId !== null) return;
    const stored = localStorage.getItem(getStorageKey(courseId));
    if (stored) {
      const storedId = parseInt(stored, 10);
      if (childList.some((c) => c.id === storedId)) {
        onSelectRef.current(storedId);
      }
    }
  }, [courseId, selectedChildId, childList]);

  // Persist selection to localStorage
  useEffect(() => {
    if (selectedChildId !== null) {
      localStorage.setItem(getStorageKey(courseId), String(selectedChildId));
    }
  }, [selectedChildId, courseId]);

  // Empty or single child: render nothing
  if (childList.length <= 1) return null;

  return (
    <div className="child-inline-pills">
      <span className="child-inline-pills__label">
        Which child is this for?
      </span>
      <div className="child-inline-pills__list" role="group" aria-label="Select child">
        {childList.map((child) => {
          const isSelected = selectedChildId === child.id;
          const isSuggested =
            !isSelected && suggestedChildId === child.id;

          let className = 'child-inline-pill';
          if (isSelected) className += ' child-inline-pill--selected';
          if (isSuggested) className += ' child-inline-pill--suggested';

          return (
            <button
              key={child.id}
              type="button"
              className={className}
              onClick={() => onSelect(child.id)}
              aria-pressed={isSelected}
            >
              {child.name}
              {child.grade && (
                <span className="child-inline-pill__grade">
                  {' '}
                  &middot; Grade {child.grade}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
