import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { PageSkeleton } from '../components/Skeleton';
import { xpApi } from '../api/xp';
import type { BadgeResponse } from '../api/xp';
import './BadgesPage.css';

const BADGE_ICONS: Record<string, string> = {
  first_upload: '\uD83D\uDCC4',
  first_guide: '\uD83D\uDCD6',
  streak_7: '\uD83D\uDD25',
  streak_30: '\u2B50',
  flashcard_fanatic: '\uD83C\uDCCF',
  lms_linker: '\uD83D\uDD17',
  exam_ready: '\uD83C\uDF93',
  quiz_improver: '\uD83D\uDCC8',
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function BadgesPage() {
  const { data: badges, isLoading, error } = useQuery({
    queryKey: ['xp-badges'],
    queryFn: xpApi.getBadges,
  });

  const earnedCount = badges?.filter((b: BadgeResponse) => b.earned).length ?? 0;
  const totalCount = badges?.length ?? 0;

  return (
    <DashboardLayout>
      <div className="badges-page">
        <PageNav items={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Badges' }]} />
        <div className="badges-header">
          <h2>Achievement Badges</h2>
          <span className="badges-counter">{earnedCount} / {totalCount} earned</span>
        </div>

        {isLoading && <PageSkeleton />}
        {error && <p className="badges-error">Failed to load badges.</p>}

        {badges && (
          <div className="badges-grid">
            {badges.map((badge: BadgeResponse) => (
              <div
                key={badge.badge_id}
                className={`badge-card${badge.earned ? ' badge-card--earned' : ' badge-card--locked'}`}
              >
                <div className="badge-icon">
                  {BADGE_ICONS[badge.badge_id] || '\uD83C\uDFC5'}
                </div>
                <div className="badge-info">
                  <h3 className="badge-name">{badge.badge_name}</h3>
                  <p className="badge-description">{badge.badge_description}</p>
                  <p className="badge-status">
                    {badge.earned
                      ? `Earned ${formatDate(badge.awarded_at)}`
                      : 'Locked'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
