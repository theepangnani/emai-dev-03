"""GamificationService — XP awards, badge checks, leaderboard."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.gamification import BadgeCategory, BadgeDefinition, UserBadge, UserXP, XPTransaction
from app.models.user import User

logger = logging.getLogger(__name__)

# XP thresholds that trigger a level-up (cumulative total_xp)
LEVEL_THRESHOLDS = [0, 100, 250, 500, 1000, 2500, 5000, 10000, 20000, 50000]


def _level_for_xp(total_xp: int) -> int:
    """Return the level (1-indexed) for a given total XP."""
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_xp >= threshold:
            level = i + 1
    return level


def _xp_for_next_level(level: int) -> int:
    """Return the XP needed to reach the *next* level."""
    if level >= len(LEVEL_THRESHOLDS):
        return LEVEL_THRESHOLDS[-1]  # max level
    return LEVEL_THRESHOLDS[level]  # LEVEL_THRESHOLDS is 0-indexed, level is 1-indexed


def _xp_progress(total_xp: int, level: int) -> int:
    """Return XP accumulated since the start of the current level."""
    current_threshold = LEVEL_THRESHOLDS[level - 1] if level - 1 < len(LEVEL_THRESHOLDS) else 0
    return max(0, total_xp - current_threshold)


class GamificationService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # XP
    # ------------------------------------------------------------------

    def get_user_xp(self, user_id: int) -> UserXP:
        """Fetch or create the UserXP record for a user."""
        record = self.db.query(UserXP).filter(UserXP.user_id == user_id).first()
        if not record:
            record = UserXP(user_id=user_id, total_xp=0, level=1, xp_this_week=0, leaderboard_opt_in=True)
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
        return record

    def award_xp(self, user_id: int, amount: int, reason: str) -> tuple[XPTransaction, bool]:
        """
        Award XP to a user.
        Returns (transaction, levelled_up).
        """
        # Record transaction
        tx = XPTransaction(user_id=user_id, amount=amount, reason=reason)
        self.db.add(tx)

        # Update aggregate record
        xp_record = self.get_user_xp(user_id)
        old_level = xp_record.level
        xp_record.total_xp += amount
        xp_record.xp_this_week = (xp_record.xp_this_week or 0) + amount
        new_level = _level_for_xp(xp_record.total_xp)
        xp_record.level = new_level
        xp_record.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(tx)

        levelled_up = new_level > old_level
        if levelled_up:
            logger.info("User %s levelled up from %s to %s", user_id, old_level, new_level)
            # Check level-based badges
            self.check_and_award_badges(user_id, "level_up", {"level": new_level})

        return tx, levelled_up

    def xp_response_data(self, xp_record: UserXP) -> dict[str, Any]:
        """Augment a UserXP ORM row with computed fields needed by the schema."""
        next_lvl_xp = _xp_for_next_level(xp_record.level)
        progress = _xp_progress(xp_record.total_xp, xp_record.level)
        return {
            "id": xp_record.id,
            "user_id": xp_record.user_id,
            "total_xp": xp_record.total_xp,
            "level": xp_record.level,
            "xp_this_week": xp_record.xp_this_week,
            "leaderboard_opt_in": xp_record.leaderboard_opt_in,
            "updated_at": xp_record.updated_at,
            "xp_for_next_level": next_lvl_xp,
            "xp_progress": progress,
        }

    # ------------------------------------------------------------------
    # Badges
    # ------------------------------------------------------------------

    def get_user_badges(self, user_id: int) -> list[UserBadge]:
        return (
            self.db.query(UserBadge)
            .filter(UserBadge.user_id == user_id)
            .all()
        )

    def check_and_award_badges(
        self,
        user_id: int,
        event_type: str,
        context: Optional[dict[str, Any]] = None,
    ) -> list[UserBadge]:
        """
        Evaluate active badge criteria for *event_type*.
        Awards any newly-earned badges and creates Notification rows.
        Returns the list of newly-awarded UserBadge instances.
        """
        context = context or {}
        active_badges = (
            self.db.query(BadgeDefinition)
            .filter(BadgeDefinition.is_active.is_(True))
            .all()
        )

        # Build set of already-earned badge IDs for this user
        earned_ids = {
            ub.badge_id
            for ub in self.db.query(UserBadge.badge_id).filter(UserBadge.user_id == user_id).all()
        }

        newly_awarded: list[UserBadge] = []

        for badge in active_badges:
            if badge.id in earned_ids:
                continue
            criteria = badge.criteria_json or {}
            if not self._meets_criteria(user_id, badge.key, criteria, event_type, context):
                continue

            # Award badge
            ub = UserBadge(user_id=user_id, badge_id=badge.id, notified=False)
            self.db.add(ub)
            self.db.flush()

            # Award XP for the badge
            if badge.xp_reward:
                tx = XPTransaction(user_id=user_id, amount=badge.xp_reward, reason=f"Badge: {badge.name}")
                self.db.add(tx)
                xp_record = self.get_user_xp(user_id)
                xp_record.total_xp += badge.xp_reward
                xp_record.xp_this_week = (xp_record.xp_this_week or 0) + badge.xp_reward
                xp_record.level = _level_for_xp(xp_record.total_xp)

            # Create in-app notification
            try:
                from app.models import Notification
                notif = Notification(
                    user_id=user_id,
                    title=f"Badge Earned: {badge.icon_emoji} {badge.name}",
                    message=badge.description,
                    notification_type="badge",
                    is_read=False,
                )
                self.db.add(notif)
            except Exception:
                pass  # Notification creation is best-effort

            newly_awarded.append(ub)
            logger.info("Awarded badge '%s' to user %s", badge.key, user_id)

        if newly_awarded:
            self.db.commit()
            for ub in newly_awarded:
                self.db.refresh(ub)

        return newly_awarded

    def _meets_criteria(
        self,
        user_id: int,
        badge_key: str,
        criteria: dict[str, Any],
        event_type: str,
        context: dict[str, Any],
    ) -> bool:
        """Return True if the badge criteria are satisfied for the current event."""
        criteria_type = criteria.get("type", badge_key)
        threshold = criteria.get("threshold", 1)

        # ------- Level-based -------
        if criteria_type == "level_up":
            return event_type == "level_up" and context.get("level", 0) >= threshold

        # ------- Study guides -------
        if criteria_type == "study_guide_count":
            if event_type not in ("study_guide_created", "study_guide_count"):
                return False
            count = context.get("count", 0)
            return count >= threshold

        if criteria_type == "study_guide_first":
            return event_type == "study_guide_created"

        if criteria_type == "study_guide_night_owl":
            # guide created after 22:00
            return event_type == "study_guide_created" and context.get("hour", 12) >= 22

        if criteria_type == "study_guide_early_bird":
            # guide created before 07:00
            return event_type == "study_guide_created" and context.get("hour", 12) < 7

        if criteria_type == "study_guide_week":
            return event_type == "study_guide_week" and context.get("count", 0) >= threshold

        # ------- Quizzes -------
        if criteria_type == "quiz_count":
            if event_type not in ("quiz_completed", "quiz_count"):
                return False
            return context.get("count", 0) >= threshold

        # ------- Streaks -------
        if criteria_type == "streak_days":
            if event_type != "streak_update":
                return False
            return context.get("streak", 0) >= threshold

        # ------- Notes -------
        if criteria_type == "note_first":
            return event_type == "note_created"

        # ------- Goals -------
        if criteria_type == "goal_first":
            return event_type == "goal_created"

        if criteria_type == "goal_complete":
            return event_type == "goal_completed"

        # ------- Social / forum -------
        if criteria_type == "peer_review_first":
            return event_type == "peer_review_submitted"

        if criteria_type == "forum_post_count":
            if event_type not in ("forum_post_created", "forum_count"):
                return False
            return context.get("count", 0) >= threshold

        if criteria_type == "forum_first":
            return event_type == "forum_post_created"

        # ------- Pomodoro -------
        if criteria_type == "pomodoro_count":
            if event_type not in ("pomodoro_completed", "pomodoro_count"):
                return False
            return context.get("count", 0) >= threshold

        # ------- Writing -------
        if criteria_type == "writing_first":
            return event_type == "writing_analysis_created"

        # ------- i18n -------
        if criteria_type == "polyglot":
            return event_type == "polyglot_achieved"

        return False

    # ------------------------------------------------------------------
    # Leaderboard
    # ------------------------------------------------------------------

    def get_leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return top users by total_xp (opt-in only, public display names)."""
        rows = (
            self.db.query(UserXP, User)
            .join(User, UserXP.user_id == User.id)
            .filter(UserXP.leaderboard_opt_in.is_(True))
            .order_by(UserXP.total_xp.desc())
            .limit(limit)
            .all()
        )

        entries = []
        for rank, (xp_record, user) in enumerate(rows, start=1):
            # Count earned badges
            badge_count = (
                self.db.query(UserBadge)
                .filter(UserBadge.user_id == xp_record.user_id)
                .count()
            )
            # Public display name: first name + last initial
            name = user.full_name or "Student"
            parts = name.split()
            if len(parts) >= 2:
                display = f"{parts[0]} {parts[-1][0]}."
            else:
                display = parts[0] if parts else "Anonymous"

            entries.append({
                "rank": rank,
                "display_name": display,
                "level": xp_record.level,
                "total_xp": xp_record.total_xp,
                "badge_count": badge_count,
            })

        return entries

    # ------------------------------------------------------------------
    # Seed default badges
    # ------------------------------------------------------------------

    def seed_default_badges(self) -> None:
        """Insert the 20 predefined badges if they don't already exist."""
        defaults = [
            {
                "key": "first_step",
                "name": "First Step",
                "description": "Created your first study guide.",
                "icon_emoji": "📖",
                "category": BadgeCategory.STUDY,
                "xp_reward": 20,
                "criteria_json": {"type": "study_guide_first", "threshold": 1},
            },
            {
                "key": "quiz_ace",
                "name": "Quiz Ace",
                "description": "Completed 10 quizzes.",
                "icon_emoji": "🧠",
                "category": BadgeCategory.QUIZ,
                "xp_reward": 50,
                "criteria_json": {"type": "quiz_count", "threshold": 10},
            },
            {
                "key": "streak_starter",
                "name": "Streak Starter",
                "description": "Maintained a 3-day study streak.",
                "icon_emoji": "🔥",
                "category": BadgeCategory.STREAK,
                "xp_reward": 30,
                "criteria_json": {"type": "streak_days", "threshold": 3},
            },
            {
                "key": "streak_master",
                "name": "Streak Master",
                "description": "Maintained a 7-day study streak.",
                "icon_emoji": "🔥",
                "category": BadgeCategory.STREAK,
                "xp_reward": 75,
                "criteria_json": {"type": "streak_days", "threshold": 7},
            },
            {
                "key": "streak_legend",
                "name": "Streak Legend",
                "description": "Maintained a 30-day study streak.",
                "icon_emoji": "🏆",
                "category": BadgeCategory.STREAK,
                "xp_reward": 250,
                "criteria_json": {"type": "streak_days", "threshold": 30},
            },
            {
                "key": "fast_learner",
                "name": "Fast Learner",
                "description": "Created 5 study guides in a single week.",
                "icon_emoji": "⚡",
                "category": BadgeCategory.STUDY,
                "xp_reward": 60,
                "criteria_json": {"type": "study_guide_week", "threshold": 5},
            },
            {
                "key": "note_taker",
                "name": "Note Taker",
                "description": "Created your first note.",
                "icon_emoji": "📝",
                "category": BadgeCategory.STUDY,
                "xp_reward": 15,
                "criteria_json": {"type": "note_first", "threshold": 1},
            },
            {
                "key": "goal_setter",
                "name": "Goal Setter",
                "description": "Set your first learning goal.",
                "icon_emoji": "🎯",
                "category": BadgeCategory.MILESTONE,
                "xp_reward": 20,
                "criteria_json": {"type": "goal_first", "threshold": 1},
            },
            {
                "key": "goal_achiever",
                "name": "Goal Achiever",
                "description": "Completed a learning goal.",
                "icon_emoji": "✅",
                "category": BadgeCategory.MILESTONE,
                "xp_reward": 50,
                "criteria_json": {"type": "goal_complete", "threshold": 1},
            },
            {
                "key": "helper",
                "name": "Helper",
                "description": "Submitted your first peer review.",
                "icon_emoji": "🤝",
                "category": BadgeCategory.SOCIAL,
                "xp_reward": 25,
                "criteria_json": {"type": "peer_review_first", "threshold": 1},
            },
            {
                "key": "overachiever",
                "name": "Overachiever",
                "description": "Created 100 study guides.",
                "icon_emoji": "🌟",
                "category": BadgeCategory.MILESTONE,
                "xp_reward": 500,
                "criteria_json": {"type": "study_guide_count", "threshold": 100},
            },
            {
                "key": "night_owl",
                "name": "Night Owl",
                "description": "Created a study guide after 10 PM.",
                "icon_emoji": "🦉",
                "category": BadgeCategory.SPECIAL,
                "xp_reward": 15,
                "criteria_json": {"type": "study_guide_night_owl", "threshold": 1},
            },
            {
                "key": "early_bird",
                "name": "Early Bird",
                "description": "Created a study guide before 7 AM.",
                "icon_emoji": "🌅",
                "category": BadgeCategory.SPECIAL,
                "xp_reward": 15,
                "criteria_json": {"type": "study_guide_early_bird", "threshold": 1},
            },
            {
                "key": "polyglot",
                "name": "Polyglot",
                "description": "Used ClassBridge in both English and French.",
                "icon_emoji": "🌐",
                "category": BadgeCategory.SPECIAL,
                "xp_reward": 30,
                "criteria_json": {"type": "polyglot", "threshold": 1},
            },
            {
                "key": "timer_pro",
                "name": "Timer Pro",
                "description": "Completed 10 Pomodoro study sessions.",
                "icon_emoji": "⏱️",
                "category": BadgeCategory.STUDY,
                "xp_reward": 40,
                "criteria_json": {"type": "pomodoro_count", "threshold": 10},
            },
            {
                "key": "writing_star",
                "name": "Writing Star",
                "description": "Used the Writing Assistant for your first analysis.",
                "icon_emoji": "✍️",
                "category": BadgeCategory.STUDY,
                "xp_reward": 20,
                "criteria_json": {"type": "writing_first", "threshold": 1},
            },
            {
                "key": "forum_voice",
                "name": "Forum Voice",
                "description": "Made your first forum post.",
                "icon_emoji": "💬",
                "category": BadgeCategory.SOCIAL,
                "xp_reward": 15,
                "criteria_json": {"type": "forum_first", "threshold": 1},
            },
            {
                "key": "social_butterfly",
                "name": "Social Butterfly",
                "description": "Made 5 forum posts.",
                "icon_emoji": "🦋",
                "category": BadgeCategory.SOCIAL,
                "xp_reward": 40,
                "criteria_json": {"type": "forum_post_count", "threshold": 5},
            },
            {
                "key": "scholar",
                "name": "Scholar",
                "description": "Reached level 5.",
                "icon_emoji": "🎓",
                "category": BadgeCategory.MILESTONE,
                "xp_reward": 100,
                "criteria_json": {"type": "level_up", "threshold": 5},
            },
            {
                "key": "legend",
                "name": "Legend",
                "description": "Reached level 10.",
                "icon_emoji": "👑",
                "category": BadgeCategory.MILESTONE,
                "xp_reward": 500,
                "criteria_json": {"type": "level_up", "threshold": 10},
            },
        ]

        existing_keys = {b.key for b in self.db.query(BadgeDefinition.key).all()}
        added = 0
        for badge_data in defaults:
            if badge_data["key"] not in existing_keys:
                badge = BadgeDefinition(**badge_data)
                self.db.add(badge)
                added += 1

        if added:
            self.db.commit()
            logger.info("Seeded %d default badges", added)


def seed_default_badges(db: Session) -> None:
    """Module-level convenience wrapper used at startup."""
    svc = GamificationService(db)
    svc.seed_default_badges()
