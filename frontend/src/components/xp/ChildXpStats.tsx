import { useQuery } from '@tanstack/react-query';
import { xpApi } from '../../api/xp';
import { StreakCounter } from './StreakCounter';
import './XpDashboard.css';

interface ChildXpStatsProps {
  studentId: number;
}

export function ChildXpStats({ studentId }: ChildXpStatsProps) {
  const { data } = useQuery({
    queryKey: ['xp-child-summary', studentId],
    queryFn: () => xpApi.getChildSummary(studentId),
    enabled: !!studentId,
  });

  if (!data) return null;

  return (
    <span className="xp-child-stats">
      {data.streak_days > 0 && <StreakCounter days={data.streak_days} compact />}
      {data.level_title && <span className="xp-child-level">{data.level_title}</span>}
      {data.weekly_xp > 0 && <span className="xp-child-weekly">{data.weekly_xp} XP/wk</span>}
    </span>
  );
}
