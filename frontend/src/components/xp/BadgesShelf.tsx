import { useNavigate } from 'react-router-dom';
import type { XpBadge } from '../../api/xp';

function isEmoji(str: string): boolean {
  if (!str) return false;
  // Slug/ID strings contain only ASCII letters, digits, underscores, hyphens
  return !/^[a-zA-Z0-9_-]+$/.test(str);
}

interface BadgesShelfProps {
  badges: XpBadge[];
  maxVisible?: number;
}

export function BadgesShelf({ badges, maxVisible = 3 }: BadgesShelfProps) {
  const navigate = useNavigate();

  if (!badges || badges.length === 0) return null;

  const visible = badges.slice(0, maxVisible);
  const remaining = badges.length - maxVisible;

  return (
    <div className="xp-badges">
      {visible.map(badge => (
        <span
          key={badge.id}
          className={`xp-badge-chip${badge.earned_at ? '' : ' xp-badge-chip--locked'}`}
          title={`${badge.name}${badge.earned_at ? '' : ' (Locked)'}`}
        >
          {badge.icon && isEmoji(badge.icon) ? badge.icon : '\uD83C\uDFC5'}
          <span className="xp-badge-label">{badge.name}</span>
        </span>
      ))}
      {remaining > 0 && (
        <button
          className="xp-badges-more"
          type="button"
          title="View all badges"
          onClick={() => navigate('/xp/badges')}
        >
          +{remaining}
        </button>
      )}
    </div>
  );
}
