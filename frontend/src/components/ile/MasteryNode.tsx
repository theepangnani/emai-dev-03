/**
 * MasteryNode — Memory Glow visual node for topic mastery (#3210).
 *
 * Displays a topic with a glow effect based on spaced repetition state:
 * - Bright green (1.0): well-reviewed, next review far out
 * - Dim yellow (0.5): due today
 * - Red pulse (0.0): overdue, needs review
 */
import type { ILEMasteryEntry } from '../../api/ile';
import './MasteryNode.css';

interface MasteryNodeProps {
  entry: ILEMasteryEntry;
  onClick?: (entry: ILEMasteryEntry) => void;
}

function getGlowColor(intensity: number): string {
  // 0.0 = red, 0.5 = yellow, 1.0 = green
  if (intensity <= 0.3) {
    // Red range
    return `rgba(239, 68, 68, ${0.4 + intensity})`;
  }
  if (intensity <= 0.6) {
    // Yellow range
    const t = (intensity - 0.3) / 0.3;
    const r = Math.round(239 + (234 - 239) * t);
    const g = Math.round(68 + (179 - 68) * t);
    const b = Math.round(68 + (8 - 68) * t);
    return `rgba(${r}, ${g}, ${b}, ${0.5 + intensity * 0.3})`;
  }
  // Green range
  const t = (intensity - 0.6) / 0.4;
  const r = Math.round(234 - (234 - 34) * t);
  const g = Math.round(179 + (197 - 179) * t);
  const b = Math.round(8 + (94 - 8) * t);
  return `rgba(${r}, ${g}, ${b}, ${0.6 + intensity * 0.3})`;
}

function getStatusLabel(intensity: number, nextReview: string | null): string {
  if (!nextReview) return 'Not yet reviewed';
  if (intensity <= 0.3) return 'Overdue';
  if (intensity <= 0.5) return 'Due today';
  return 'On track';
}

function formatNextReview(nextReview: string | null): string {
  if (!nextReview) return 'Never';
  const date = new Date(nextReview);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / 86400000);

  if (diffDays < -1) return `${Math.abs(diffDays)}d overdue`;
  if (diffDays < 0) return 'Yesterday';
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Tomorrow';
  return `In ${diffDays}d`;
}

export function MasteryNode({ entry, onClick }: MasteryNodeProps) {
  const glowColor = getGlowColor(entry.glow_intensity);
  const isOverdue = entry.glow_intensity <= 0.3 && entry.next_review_at !== null;
  const statusLabel = getStatusLabel(entry.glow_intensity, entry.next_review_at);
  const scorePct = entry.last_score_pct !== null ? Math.round(entry.last_score_pct) : null;

  return (
    <button
      className={`mastery-node ${isOverdue ? 'mastery-node--overdue' : ''}`}
      style={{
        '--glow-color': glowColor,
        '--glow-intensity': entry.glow_intensity,
      } as React.CSSProperties}
      onClick={() => onClick?.(entry)}
      type="button"
    >
      <div className="mastery-node__header">
        <span className="mastery-node__subject">{entry.subject}</span>
        {entry.is_weak_area && <span className="mastery-node__weak">Weak</span>}
      </div>
      <span className="mastery-node__topic">{entry.topic}</span>
      <div className="mastery-node__footer">
        {scorePct !== null && (
          <span className="mastery-node__score">{scorePct}%</span>
        )}
        <span className={`mastery-node__status mastery-node__status--${isOverdue ? 'overdue' : 'ok'}`}>
          {statusLabel}
        </span>
      </div>
      <span className="mastery-node__review">{formatNextReview(entry.next_review_at)}</span>
    </button>
  );
}
