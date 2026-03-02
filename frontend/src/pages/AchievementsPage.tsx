import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  getAllBadges,
  getMyBadges,
  getMyXP,
  getXPHistory,
  getLeaderboard,
  setLeaderboardOptIn,
  getNewBadgeNotifications,
  type BadgeCategory,
  type BadgeDefinition,
  type UserBadge,
  type NewBadgeNotification,
} from '../api/gamification';
import './AchievementsPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<BadgeCategory, string> = {
  study: 'Study',
  quiz: 'Quiz',
  streak: 'Streak',
  social: 'Social',
  milestone: 'Milestone',
  special: 'Special',
};

const ALL_CATEGORIES: Array<BadgeCategory | 'all'> = [
  'all',
  'study',
  'quiz',
  'streak',
  'social',
  'milestone',
  'special',
];

function XPBar({ xp_progress, xp_for_next_level, level }: { xp_progress: number; xp_for_next_level: number; level: number }) {
  const pct = xp_for_next_level > 0 ? Math.min(100, (xp_progress / xp_for_next_level) * 100) : 100;
  return (
    <div className="xp-bar-container" aria-label={`Level ${level}: ${xp_progress} / ${xp_for_next_level} XP`}>
      <div className="xp-bar-track">
        <div className="xp-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="xp-bar-label">{xp_progress} / {xp_for_next_level} XP</span>
    </div>
  );
}

function BadgeToast({ notifications, onDismiss }: { notifications: NewBadgeNotification[]; onDismiss: () => void }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 400); // allow fade-out
    }, 5000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  if (!notifications.length) return null;

  return (
    <div className={`badge-toast-stack${visible ? ' visible' : ' fading'}`}>
      {notifications.map((n, i) => (
        <div key={i} className="badge-toast">
          <span className="badge-toast-emoji">{n.badge.icon_emoji}</span>
          <div className="badge-toast-body">
            <strong>Badge Earned!</strong>
            <span>{n.badge.name}</span>
            <span className="badge-toast-xp">+{n.xp_awarded} XP</span>
          </div>
          <button className="badge-toast-close" onClick={() => { setVisible(false); setTimeout(onDismiss, 400); }}>
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}

function BadgeCard({ badge, earned }: { badge: BadgeDefinition; earned?: UserBadge }) {
  return (
    <div className={`badge-card${earned ? ' badge-card--earned' : ' badge-card--locked'}`} title={badge.description}>
      <div className="badge-card-emoji">{badge.icon_emoji}</div>
      <div className="badge-card-name">{badge.name}</div>
      <div className="badge-card-desc">{badge.description}</div>
      {earned && (
        <div className="badge-card-date">
          Earned {new Date(earned.earned_at).toLocaleDateString()}
        </div>
      )}
      {!earned && (
        <div className="badge-card-locked-label">Locked</div>
      )}
      <div className="badge-card-xp">+{badge.xp_reward} XP</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type ActiveTab = 'badges' | 'history' | 'leaderboard';

export function AchievementsPage() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>('badges');
  const [categoryFilter, setCategoryFilter] = useState<BadgeCategory | 'all'>('all');
  const [newBadges, setNewBadges] = useState<NewBadgeNotification[]>([]);

  // Queries
  const { data: allBadges = [] } = useQuery({ queryKey: ['badges', 'all'], queryFn: getAllBadges });
  const { data: myBadges = [] } = useQuery({ queryKey: ['badges', 'mine'], queryFn: getMyBadges });
  const { data: xpData } = useQuery({ queryKey: ['xp', 'me'], queryFn: getMyXP });
  const { data: history = [] } = useQuery({
    queryKey: ['xp', 'history'],
    queryFn: () => getXPHistory(50),
    enabled: activeTab === 'history',
  });
  const { data: leaderboard } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: () => getLeaderboard(20),
    enabled: activeTab === 'leaderboard',
  });

  // Check for unread badge notifications on page load
  useEffect(() => {
    getNewBadgeNotifications().then((notes) => {
      if (notes.length > 0) {
        setNewBadges(notes);
        qc.invalidateQueries({ queryKey: ['badges', 'mine'] });
        qc.invalidateQueries({ queryKey: ['xp', 'me'] });
      }
    }).catch(() => {});
  }, [qc]);

  // Opt-in toggle mutation
  const optInMutation = useMutation({
    mutationFn: (optIn: boolean) => setLeaderboardOptIn(optIn),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['xp', 'me'] });
      qc.invalidateQueries({ queryKey: ['leaderboard'] });
    },
  });

  // Build earned map for quick lookup
  const earnedMap = new Map<number, UserBadge>(myBadges.map((ub) => [ub.badge_id, ub]));

  const filteredBadges = categoryFilter === 'all'
    ? allBadges
    : allBadges.filter((b) => b.category === categoryFilter);

  const handleDismissToast = useCallback(() => setNewBadges([]), []);

  return (
    <DashboardLayout welcomeSubtitle="Your achievements and XP progress">
      {newBadges.length > 0 && (
        <BadgeToast notifications={newBadges} onDismiss={handleDismissToast} />
      )}

      <div className="achievements-page">
        {/* XP Header Card */}
        {xpData && (
          <div className="achievements-xp-card">
            <div className="achievements-xp-level">
              <span className="level-badge">Lvl {xpData.level}</span>
              <div className="achievements-xp-info">
                <span className="xp-total">{xpData.total_xp.toLocaleString()} XP</span>
                <span className="xp-week">+{xpData.xp_this_week} this week</span>
              </div>
            </div>
            <XPBar
              xp_progress={xpData.xp_progress}
              xp_for_next_level={xpData.xp_for_next_level}
              level={xpData.level}
            />
            <div className="achievements-badge-count">
              <span>{myBadges.length} / {allBadges.length} badges earned</span>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="achievements-tabs" role="tablist">
          {(['badges', 'history', 'leaderboard'] as ActiveTab[]).map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={activeTab === tab}
              className={`achievements-tab${activeTab === tab ? ' active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'badges' ? 'Badges' : tab === 'history' ? 'XP History' : 'Leaderboard'}
            </button>
          ))}
        </div>

        {/* Badges Tab */}
        {activeTab === 'badges' && (
          <div className="achievements-badges-panel">
            {/* Category filter */}
            <div className="badge-category-filter" role="group" aria-label="Filter badges by category">
              {ALL_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  className={`badge-cat-btn${categoryFilter === cat ? ' active' : ''}`}
                  onClick={() => setCategoryFilter(cat)}
                >
                  {cat === 'all' ? 'All' : CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>

            {/* Badge grid */}
            <div className="badge-grid">
              {filteredBadges.map((badge) => (
                <BadgeCard
                  key={badge.id}
                  badge={badge}
                  earned={earnedMap.get(badge.id)}
                />
              ))}
              {filteredBadges.length === 0 && (
                <p className="achievements-empty">No badges in this category yet.</p>
              )}
            </div>
          </div>
        )}

        {/* XP History Tab */}
        {activeTab === 'history' && (
          <div className="achievements-history-panel">
            {history.length === 0 ? (
              <p className="achievements-empty">No XP earned yet. Start studying to earn your first XP!</p>
            ) : (
              <ul className="xp-history-list">
                {history.map((tx) => (
                  <li key={tx.id} className="xp-history-item">
                    <span className={`xp-history-amount${tx.amount >= 0 ? ' positive' : ' negative'}`}>
                      {tx.amount >= 0 ? '+' : ''}{tx.amount} XP
                    </span>
                    <span className="xp-history-reason">{tx.reason}</span>
                    <span className="xp-history-date">
                      {new Date(tx.created_at).toLocaleDateString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Leaderboard Tab */}
        {activeTab === 'leaderboard' && (
          <div className="achievements-leaderboard-panel">
            {xpData && (
              <div className="leaderboard-opt-in-row">
                <label className="opt-in-toggle">
                  <input
                    type="checkbox"
                    checked={xpData.leaderboard_opt_in}
                    onChange={(e) => optInMutation.mutate(e.target.checked)}
                    disabled={optInMutation.isPending}
                  />
                  <span>Show me on the leaderboard</span>
                </label>
              </div>
            )}

            {!leaderboard || leaderboard.entries.length === 0 ? (
              <p className="achievements-empty">No leaderboard data yet.</p>
            ) : (
              <>
                {/* Podium for top 3 */}
                {leaderboard.entries.length >= 3 && (
                  <div className="leaderboard-podium">
                    {/* 2nd place */}
                    <div className="podium-slot podium-2nd">
                      <div className="podium-name">{leaderboard.entries[1].display_name}</div>
                      <div className="podium-level">Lvl {leaderboard.entries[1].level}</div>
                      <div className="podium-block">2</div>
                      <div className="podium-xp">{leaderboard.entries[1].total_xp.toLocaleString()} XP</div>
                    </div>
                    {/* 1st place */}
                    <div className="podium-slot podium-1st">
                      <div className="podium-crown">👑</div>
                      <div className="podium-name">{leaderboard.entries[0].display_name}</div>
                      <div className="podium-level">Lvl {leaderboard.entries[0].level}</div>
                      <div className="podium-block">1</div>
                      <div className="podium-xp">{leaderboard.entries[0].total_xp.toLocaleString()} XP</div>
                    </div>
                    {/* 3rd place */}
                    <div className="podium-slot podium-3rd">
                      <div className="podium-name">{leaderboard.entries[2].display_name}</div>
                      <div className="podium-level">Lvl {leaderboard.entries[2].level}</div>
                      <div className="podium-block">3</div>
                      <div className="podium-xp">{leaderboard.entries[2].total_xp.toLocaleString()} XP</div>
                    </div>
                  </div>
                )}

                {/* Rest of leaderboard */}
                <table className="leaderboard-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Name</th>
                      <th>Level</th>
                      <th>XP</th>
                      <th>Badges</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.entries.map((entry) => (
                      <tr key={entry.rank} className={entry.rank <= 3 ? 'leaderboard-top3' : ''}>
                        <td className="leaderboard-rank">
                          {entry.rank === 1 ? '🥇' : entry.rank === 2 ? '🥈' : entry.rank === 3 ? '🥉' : entry.rank}
                        </td>
                        <td className="leaderboard-name">{entry.display_name}</td>
                        <td className="leaderboard-level">
                          <span className="level-badge level-badge--sm">Lvl {entry.level}</span>
                        </td>
                        <td className="leaderboard-xp">{entry.total_xp.toLocaleString()}</td>
                        <td className="leaderboard-badges">{entry.badge_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
