/**
 * CB-BRIDGE-003 — kid switcher rail (#4115).
 *
 * Replaces the legacy `pd-child-selector`. Per-child management used to
 * live in a per-chip "···" dropdown — that surface is gone now; all
 * per-child actions live in the hero kebab (KidActionsMenu) so we have
 * exactly one place to manage a kid.
 */
import type { ChildSummary } from '../../api/client';
import { getInitial } from './util';

interface KidRailProps {
  children: ChildSummary[];
  selectedChild: number | null;
  onSelect: (studentId: number | null) => void;
  onAddChild: () => void;
  colors: readonly string[];
}

export function KidRail({ children, selectedChild, onSelect, onAddChild, colors }: KidRailProps) {
  return (
    <nav className="bridge-rail-wrap" aria-label="Select a child">
      <div className="bridge-rail-label">Choose a bridge</div>
      <div className="bridge-rail">
        {children.length > 1 && (
          <button
            type="button"
            className={`bridge-chip bridge-chip--all ${selectedChild === null ? 'is-active' : ''}`}
            onClick={() => onSelect(null)}
            aria-pressed={selectedChild === null}
          >
            <span className="bridge-chip-dot bridge-chip-dot--all" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            All kids
          </button>
        )}
        {children.map((child, index) => {
          const color = colors[index % colors.length];
          const isActive = selectedChild === child.student_id;
          return (
            <button
              key={child.student_id}
              type="button"
              className={`bridge-chip ${isActive ? 'is-active' : ''}`}
              onClick={() => onSelect(isActive ? null : child.student_id)}
              aria-pressed={isActive}
            >
              <span className="bridge-chip-dot" style={{ background: color }} aria-hidden="true">
                {getInitial(child.full_name)}
              </span>
              <span className="bridge-chip-name">{child.full_name}</span>
              {child.grade_level != null && (
                <span className="bridge-chip-grade">Grade {child.grade_level}</span>
              )}
              {child.invite_status === 'pending' && (
                <span className="bridge-chip-status bridge-chip-status--pending">Pending</span>
              )}
              {child.invite_status === 'email_unverified' && (
                <span className="bridge-chip-status bridge-chip-status--unverified">Unverified</span>
              )}
            </button>
          );
        })}
        <button
          type="button"
          className="bridge-chip bridge-chip--ghost"
          onClick={onAddChild}
        >
          + Add child
        </button>
      </div>
    </nav>
  );
}
