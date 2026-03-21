"""
Tests for the Badge trigger service (#2004).
"""
import pytest
from unittest.mock import patch

from conftest import PASSWORD


@pytest.fixture()
def badge_student(db_session):
    """Create a test student for badge tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)

    student = db_session.query(User).filter(User.email == "badge_student@test.com").first()
    if not student:
        student = User(
            email="badge_student@test.com",
            username="badge_student",
            hashed_password=hashed,
            full_name="Badge Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.flush()

    # Clean up prior badge/xp/notification data
    from app.models.xp import Badge, XpLedger, XpSummary
    from app.models.notification import Notification

    db_session.query(Badge).filter(Badge.student_id == student.id).delete()
    db_session.query(Notification).filter(Notification.user_id == student.id).delete()
    db_session.query(XpLedger).filter(XpLedger.student_id == student.id).delete()
    db_session.query(XpSummary).filter(XpSummary.student_id == student.id).delete()
    db_session.commit()

    return student


def _add_ledger_entries(db_session, student_id: int, action_type: str, count: int):
    """Helper to add multiple xp_ledger entries."""
    from app.models.xp import XpLedger

    for _ in range(count):
        entry = XpLedger(
            student_id=student_id,
            action_type=action_type,
            xp_awarded=10,
            multiplier=1.0,
        )
        db_session.add(entry)
    db_session.flush()


class TestBadgeTriggers:
    """Test each badge trigger condition."""

    def test_first_upload_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "upload", 1)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "upload")
        assert "first_upload" in awarded

    def test_first_guide_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "study_guide", 1)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "study_guide")
        assert "first_guide" in awarded

    def test_streak_7_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.xp import XpSummary

        summary = XpSummary(student_id=badge_student.id, current_streak=7)
        db_session.add(summary)
        db_session.flush()

        # Streak badges check on any action
        _add_ledger_entries(db_session, badge_student.id, "daily_login", 1)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "daily_login")
        assert "streak_7" in awarded

    def test_streak_30_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.xp import XpSummary

        summary = XpSummary(student_id=badge_student.id, current_streak=30)
        db_session.add(summary)
        db_session.flush()

        _add_ledger_entries(db_session, badge_student.id, "daily_login", 1)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "daily_login")
        assert "streak_30" in awarded

    def test_flashcard_fanatic_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "flashcard_review", 60)
        _add_ledger_entries(db_session, badge_student.id, "flashcard_got_it", 40)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "flashcard_review")
        assert "flashcard_fanatic" in awarded

    def test_flashcard_fanatic_not_awarded_below_threshold(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "flashcard_review", 10)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "flashcard_review")
        assert "flashcard_fanatic" not in awarded

    def test_lms_linker_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "upload_lms", 5)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "upload_lms")
        assert "lms_linker" in awarded

    def test_quiz_improver_badge(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "quiz_improvement", 3)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "quiz_improvement")
        assert "quiz_improver" in awarded

    def test_irrelevant_action_does_not_trigger(self, db_session, badge_student):
        """Upload action should not trigger first_guide badge check."""
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "upload", 1)
        awarded = BadgeService.check_and_award(db_session, badge_student.id, "upload")
        assert "first_guide" not in awarded


class TestBadgeUniqueConstraint:
    """Test that badges are not re-awarded."""

    def test_badge_not_re_awarded(self, db_session, badge_student):
        from app.services.badge_service import BadgeService

        _add_ledger_entries(db_session, badge_student.id, "upload", 1)

        first_award = BadgeService.check_and_award(db_session, badge_student.id, "upload")
        assert "first_upload" in first_award

        # Award again — should not re-award
        second_award = BadgeService.check_and_award(db_session, badge_student.id, "upload")
        assert "first_upload" not in second_award

    def test_badge_count_stays_at_one(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.xp import Badge

        _add_ledger_entries(db_session, badge_student.id, "upload", 5)
        BadgeService.check_and_award(db_session, badge_student.id, "upload")
        BadgeService.check_and_award(db_session, badge_student.id, "upload")

        count = (
            db_session.query(Badge)
            .filter(Badge.student_id == badge_student.id, Badge.badge_id == "first_upload")
            .count()
        )
        assert count == 1


class TestBadgeNotification:
    """Test that notifications are created on badge award."""

    def test_notification_created_on_badge_award(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.notification import Notification

        _add_ledger_entries(db_session, badge_student.id, "upload", 1)
        BadgeService.check_and_award(db_session, badge_student.id, "upload")

        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == badge_student.id,
                Notification.title.contains("First Upload"),
            )
            .all()
        )
        assert len(notifs) == 1
        assert "badge" in notifs[0].title.lower()

    def test_no_duplicate_notification(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.notification import Notification

        _add_ledger_entries(db_session, badge_student.id, "upload", 1)
        BadgeService.check_and_award(db_session, badge_student.id, "upload")
        BadgeService.check_and_award(db_session, badge_student.id, "upload")

        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == badge_student.id,
                Notification.title.contains("First Upload"),
            )
            .all()
        )
        assert len(notifs) == 1

    def test_notification_links_to_badges_page(self, db_session, badge_student):
        from app.services.badge_service import BadgeService
        from app.models.notification import Notification

        _add_ledger_entries(db_session, badge_student.id, "study_guide", 1)
        BadgeService.check_and_award(db_session, badge_student.id, "study_guide")

        notif = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == badge_student.id,
                Notification.title.contains("First Study Guide"),
            )
            .first()
        )
        assert notif is not None
        assert notif.link == "/xp/badges"
