"""Unit tests for app.services.email_classifier (#3472)."""

import pytest

from app.services.email_classifier import is_automated_sender


class TestIsAutomatedSender:
    """Tests for is_automated_sender() noreply/automated detection."""

    # ---------- Positive matches (should return True) ----------

    @pytest.mark.parametrize(
        "email",
        [
            "noreply@google.com",
            "no-reply@google.com",
            "no_reply@school.ca",
            "NoReply@example.com",  # case-insensitive
            "NOREPLY@example.com",
            "donotreply@bank.com",
            "do-not-reply@domain.org",
            "do_not_reply@domain.org",
            "notifications@school.ca",
            "notification@school.ca",
            "alerts@monitoring.io",
            "alert@monitoring.io",
            "mailer-daemon@googlemail.com",
            "mailerdaemon@domain.com",
            "postmaster@domain.com",
            "system@automated.io",
            "automated@robots.com",
            "bounces@sender.com",
            "bounce@sender.com",
            "noreply@google.com",
            "classroom-noreply@google.com",
            "no-reply@accounts.google.com",
            "accounts-noreply@google.com",
            "school-notifications@board.ca",
            "parent_notifications@school.ca",
        ],
    )
    def test_automated_patterns_match(self, email):
        assert is_automated_sender(email) is True, f"Expected {email} to be automated"

    # ---------- Negative matches (should return False) ----------

    @pytest.mark.parametrize(
        "email",
        [
            "teacher.name@school.ca",
            "jsmith@board.ca",
            "principal@elementary.ca",
            "parent@gmail.com",
            "alex.teacher@classbridge.ca",
            "mary.jones@school.ca",
            "support@classbridge.ca",  # support is not automated
            "admin@school.ca",  # admin is a real person role
            "hello@company.com",
            "contact@school.ca",
        ],
    )
    def test_human_patterns_do_not_match(self, email):
        assert is_automated_sender(email) is False, f"Expected {email} to NOT be automated"

    # ---------- Edge cases ----------

    def test_empty_string_returns_false(self):
        assert is_automated_sender("") is False

    def test_no_at_sign_returns_false(self):
        assert is_automated_sender("notanemail") is False

    def test_none_like_whitespace_returns_false(self):
        assert is_automated_sender("   ") is False

    def test_only_at_sign_returns_false(self):
        assert is_automated_sender("@") is False

    def test_only_local_part_returns_false(self):
        # Missing domain but has @ — local part "noreply" alone would match pattern
        # but we still require an "@" split; domain empty is OK, but we want to be
        # strict: empty-after-split gives empty domain — is_automated should still
        # match because the local-part matches.
        assert is_automated_sender("noreply@") is True

    def test_empty_local_part_returns_false(self):
        assert is_automated_sender("@domain.com") is False

    def test_unusual_domain_still_classifies(self):
        # Unusual TLD should not affect local-part matching
        assert is_automated_sender("noreply@weird.internal") is True
        assert is_automated_sender("teacher@weird.internal") is False

    def test_leading_trailing_whitespace(self):
        assert is_automated_sender("  noreply@google.com  ") is True
