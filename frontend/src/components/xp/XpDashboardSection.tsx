import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { xpApi } from '../../api/xp';
import { StreakCounter } from './StreakCounter';
import { XpLevelBar } from './XpLevelBar';
import { TodayXpWidget } from './TodayXpWidget';
import { BadgesShelf } from './BadgesShelf';
import './XpDashboard.css';

export function XpDashboardSection() {
  const { data, isLoading } = useQuery({
    queryKey: ['xp-summary'],
    queryFn: xpApi.getSummary,
  });

  if (isLoading) {
    return (
      <div className="xp-dashboard-section xp-dashboard-section--loading" aria-busy="true" aria-label="Loading XP data">
        <div className="skeleton" style={{ width: 80, height: 24, borderRadius: 8 }} />
        <div className="skeleton" style={{ height: 32, borderRadius: 8 }} />
        <div className="skeleton" style={{ width: 60, height: 32, borderRadius: 8 }} />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="xp-dashboard-section">
      <StreakCounter days={data.streak_days} />
      <XpLevelBar
        level={data.level}
        levelTitle={data.level_title}
        xpInLevel={data.xp_in_level}
        xpForNextLevel={data.xp_for_next_level}
        totalXp={data.total_xp}
      />
      <TodayXpWidget todayXp={data.today_xp} todayMaxXp={data.today_max_xp} />
      {data.recent_badges?.length > 0 && <BadgesShelf badges={data.recent_badges} />}
      <div className="xp-dashboard-links">
        <Link to="/xp/history" className="xp-badges-more">View Full History</Link>
        <Link to="/activity/timeline" className="xp-badges-more">Study Timeline</Link>
      </div>
    </div>
  );
}
