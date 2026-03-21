"""XP / Gamification service — stub for parallel stream integration.

This module provides the XpService class with method signatures that the
XP API routes and endpoint hooks call.  The parallel stream that creates
the XP models (xp_ledger, xp_summary, badges, streak_log) will flesh out
the implementations.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class XpService:
    """Gamification service: XP awards, streaks, badges, brownie points."""

    @staticmethod
    def award_xp(db: Session, user_id: int, action: str) -> None:
        """Award XP for a user action (non-blocking, feature-flagged).

        Args:
            db: Database session.
            user_id: The user earning XP.
            action: Action slug (e.g. "study_guide", "quiz_complete",
                    "flashcard_deck", "upload").
        """
        if not settings.xp_enabled:
            return None
        # TODO: implement when XP models are available
        logger.debug("XP award stub: user_id=%s action=%s", user_id, action)

    @staticmethod
    def get_summary(db: Session, user_id: int) -> dict:
        """Return XP summary for a user."""
        return {
            "user_id": user_id,
            "total_xp": 0,
            "level": 1,
            "current_level_xp": 0,
            "next_level_xp": 100,
            "streak_days": 0,
            "longest_streak": 0,
        }

    @staticmethod
    def get_history(db: Session, user_id: int, *, limit: int = 50, offset: int = 0) -> dict:
        """Return paginated XP history for a user."""
        return {
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def get_badges(db: Session, user_id: int) -> list[dict]:
        """Return all badges (earned and unearned) for a user."""
        return []

    @staticmethod
    def get_streak(db: Session, user_id: int) -> dict:
        """Return streak info for a user."""
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None,
        }

    @staticmethod
    def award_brownie_points(
        db: Session,
        student_user_id: int,
        points: int,
        awarder_id: int,
        reason: Optional[str] = None,
    ) -> dict:
        """Award brownie points from parent/teacher to student."""
        if not settings.xp_enabled:
            return {
                "awarded": 0,
                "student_user_id": student_user_id,
                "new_total_xp": 0,
                "message": "XP system is disabled",
            }
        # TODO: implement when XP models are available
        logger.debug(
            "Brownie points stub: student=%s points=%s awarder=%s",
            student_user_id, points, awarder_id,
        )
        return {
            "awarded": points,
            "student_user_id": student_user_id,
            "new_total_xp": points,
            "message": f"Awarded {points} brownie points!",
        }
