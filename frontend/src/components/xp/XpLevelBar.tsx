interface XpLevelBarProps {
  level: number;
  levelTitle: string;
  xpInLevel: number;
  xpForNextLevel: number;
  totalXp: number;
}

export function XpLevelBar({ level, levelTitle, xpInLevel, xpForNextLevel, totalXp }: XpLevelBarProps) {
  const pct = xpForNextLevel > 0 ? Math.min(100, Math.round((xpInLevel / xpForNextLevel) * 100)) : 100;

  return (
    <div className="xp-level-bar">
      <div className="xp-level-info">
        <span className="xp-level-title">
          Level {level}: {levelTitle}
        </span>
        <span className="xp-level-xp">
          {xpInLevel.toLocaleString()} / {xpForNextLevel.toLocaleString()} XP
        </span>
      </div>
      <div
        className="xp-level-progress-track"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Level ${level} progress: ${pct}% — ${totalXp.toLocaleString()} total XP`}
      >
        <div className="xp-level-progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
