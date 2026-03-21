interface TodayXpWidgetProps {
  todayXp: number;
  todayMaxXp: number;
}

export function TodayXpWidget({ todayXp, todayMaxXp }: TodayXpWidgetProps) {
  const pct = todayMaxXp > 0 ? Math.min(100, Math.round((todayXp / todayMaxXp) * 100)) : 0;

  return (
    <div className="xp-today">
      <span className="xp-today-value">{todayXp} / {todayMaxXp}</span>
      <span className="xp-today-label">XP today</span>
      <div className="xp-today-bar-track">
        <div className="xp-today-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
