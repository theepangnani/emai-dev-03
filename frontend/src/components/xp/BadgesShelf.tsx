import type { XpBadge } from '../../api/xp';

interface BadgesShelfProps {
  badges: XpBadge[];
  maxVisible?: number;
}

export function BadgesShelf({ badges, maxVisible = 3 }: BadgesShelfProps) {
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
          {badge.icon || '\uD83C\uDFC5'}
        </span>
      ))}
      {remaining > 0 && (
        <button className="xp-badges-more" type="button" title="View all badges">
          +{remaining}
        </button>
      )}
    </div>
  );
}
