"""Tests for role-based deep linking in email notifications."""
import pytest
from unittest.mock import patch, MagicMock


class TestGetRoleAwareLink:
    """Test the get_role_aware_link helper."""

    def test_none_link_returns_none(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link(None, UserRole.PARENT) is None

    def test_none_role_returns_original_link(self):
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/messages", None) == "/messages"

    def test_messages_link_parent(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/messages", UserRole.PARENT) == "/messages"

    def test_messages_link_student(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/messages", UserRole.STUDENT) == "/messages"

    def test_messages_link_teacher(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/messages", UserRole.TEACHER) == "/messages"

    def test_messages_link_admin(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/messages", UserRole.ADMIN) == "/messages"

    def test_dashboard_link_parent(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/dashboard", UserRole.PARENT) == "/dashboard"

    def test_dashboard_link_student(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/dashboard", UserRole.STUDENT) == "/dashboard"

    def test_dashboard_link_teacher(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/dashboard", UserRole.TEACHER) == "/teacher-communications"

    def test_dashboard_link_admin(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/dashboard", UserRole.ADMIN) == "/admin/waitlist"

    def test_link_requests_link_parent(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/link-requests", UserRole.PARENT) == "/link-requests"

    def test_link_requests_link_student(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/link-requests", UserRole.STUDENT) == "/dashboard"

    def test_unknown_link_returns_original(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/some-page", UserRole.PARENT) == "/some-page"

    def test_task_link_returns_original(self):
        from app.models.user import UserRole
        from app.services.notification_service import get_role_aware_link
        assert get_role_aware_link("/tasks/42", UserRole.STUDENT) == "/tasks/42"


class TestBuildNotificationEmailDeepLink:
    """Test that _build_notification_email generates role-aware URLs."""

    @patch("app.services.email_service.wrap_branded_email", side_effect=lambda x: x)
    @patch("app.core.config.settings")
    def test_email_contains_role_aware_link(self, mock_settings, mock_wrap):
        from app.models.user import UserRole
        from app.services.notification_service import _build_notification_email
        mock_settings.frontend_url = "https://www.classbridge.ca"
        html = _build_notification_email(
            "Test", "Content", "/dashboard", UserRole.TEACHER
        )
        assert "https://www.classbridge.ca/teacher-communications" in html

    @patch("app.services.email_service.wrap_branded_email", side_effect=lambda x: x)
    @patch("app.core.config.settings")
    def test_email_without_role_uses_original_link(self, mock_settings, mock_wrap):
        from app.services.notification_service import _build_notification_email
        mock_settings.frontend_url = "https://www.classbridge.ca"
        html = _build_notification_email(
            "Test", "Content", "/dashboard"
        )
        assert "https://www.classbridge.ca/dashboard" in html

    @patch("app.services.email_service.wrap_branded_email", side_effect=lambda x: x)
    @patch("app.core.config.settings")
    def test_email_no_link_no_button(self, mock_settings, mock_wrap):
        from app.models.user import UserRole
        from app.services.notification_service import _build_notification_email
        mock_settings.frontend_url = "https://www.classbridge.ca"
        html = _build_notification_email("Test", "Content", None, UserRole.PARENT)
        assert "View in ClassBridge" not in html
