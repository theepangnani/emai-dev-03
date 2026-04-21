import { DEMO_GAME_XP_MAX, type DemoLevel } from './useDemoGameState';

export interface DemoXPBarProps {
  xp: number;
  level: DemoLevel;
}

/**
 * Gamification primitive — XP progress bar (CB-DEMO-001 foundation).
 *
 * Scaffold only: Wave 2 feature streams will polish the transitions,
 * level-up overlay, and XP pop animations. Colors come from brand tokens
 * (`--color-accent*`) — no new palette.
 */
export function DemoXPBar({ xp, level }: DemoXPBarProps) {
  const pct = Math.min(100, Math.max(0, (xp / DEMO_GAME_XP_MAX) * 100));
  return (
    <div
      className="demo-xp-bar"
      role="progressbar"
      aria-label="Demo experience progress"
      aria-valuenow={xp}
      aria-valuemin={0}
      aria-valuemax={DEMO_GAME_XP_MAX}
    >
      <span className="demo-xp-bar__level" aria-label={`Level ${level}`}>
        L{level}
      </span>
      <span className="demo-xp-bar__track" aria-hidden="true">
        <span className="demo-xp-bar__fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="demo-xp-bar__count" aria-hidden="true">
        {xp}/{DEMO_GAME_XP_MAX}
      </span>
    </div>
  );
}

export default DemoXPBar;
