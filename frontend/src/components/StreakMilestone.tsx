import { useState, useMemo, useCallback } from 'react';
import './StreakMilestone.css';

interface MilestoneDef {
  days: number;
  icon: string;
  label: string;
}

const MILESTONES: MilestoneDef[] = [
  { days: 3, icon: '\u{1F31F}', label: '3-Day Streak!' },
  { days: 7, icon: '\u{1F3C6}', label: '7-Day Streak!' },
  { days: 14, icon: '\u{1F525}', label: '14-Day Streak!' },
  { days: 30, icon: '\u2B50', label: '30-Day Streak!' },
  { days: 100, icon: '\u{1F48E}', label: '100-Day Streak!' },
];

interface StreakMilestoneProps {
  streak: number;
}

export function StreakMilestone({ streak }: StreakMilestoneProps) {
  const [dismissed, setDismissed] = useState<number[]>([]);

  const visibleMilestones = useMemo(() => {
    return MILESTONES.filter(m => {
      if (streak < m.days) return false;
      if (dismissed.includes(m.days)) return false;
      const key = `streak_milestone_${m.days}_dismissed`;
      return localStorage.getItem(key) !== 'true';
    });
  }, [streak, dismissed]);

  const handleDismiss = useCallback((days: number) => {
    localStorage.setItem(`streak_milestone_${days}_dismissed`, 'true');
    setDismissed(prev => [...prev, days]);
  }, []);

  if (visibleMilestones.length === 0) return null;

  // Show the highest achieved milestone that hasn't been dismissed
  const milestone = visibleMilestones[visibleMilestones.length - 1];

  return (
    <div className="streak-milestone" role="status" aria-label={`Milestone: ${milestone.label}`}>
      <span className="streak-milestone-icon">{milestone.icon}</span>
      <span className="streak-milestone-text">{milestone.label}</span>
      <button
        className="streak-milestone-dismiss"
        onClick={() => handleDismiss(milestone.days)}
        aria-label="Dismiss milestone"
      >
        {'\u00D7'}
      </button>
    </div>
  );
}
