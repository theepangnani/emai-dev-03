"""Tests for app.services.notification_service helpers.

Focus on #3884 regressions in _build_notification_email — pre-formatted
HTML content must not be wrapped in <p>, while plain-text content must
still be wrapped in <p> exactly as before.

Also covers #3887 — three-valued per-channel status convention
(True / False / None) in send_multi_channel_notification.
"""
from unittest.mock import patch

import pytest

from app.services.notification_service import (
    _build_notification_email,
    send_multi_channel_notification,
)


def test_build_notification_email_html_content_not_wrapped_in_p():
    """#3884: HTML content starting with a block tag must be wrapped in <div>,
    not <p>, so we don't produce invalid <p><h3>...</h3></p> nesting."""
    html = _build_notification_email(
        title="Email Digest for Alex",
        content="<h3>X</h3><p>Y</p>",
        link=None,
        recipient_role="parent",
    )

    # The real <h3> content is present.
    assert "<h3>X</h3>" in html

    # But the original <p><h3>...</h3> nested-block pattern must NOT appear.
    assert "<p><h3>" not in html
    # And no <p style="..."><h3> either — the digest content must be wrapped
    # in <div>, never <p>, so we never produce <p><h3>...</h3></p>.
    assert '<p style="color:#333;line-height:1.6;margin:0 0 16px 0;"><h3>' not in html


def test_build_notification_email_plain_text_still_uses_p_wrap():
    """#3884: Plain-text content must still render inside <p style="...">...</p>
    so non-digest emails are byte-identical to the pre-fix behaviour."""
    html = _build_notification_email(
        title="New message",
        content="plain text message",
        link=None,
        recipient_role="parent",
    )

    assert (
        '<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">plain text message</p>'
        in html
    )


def test_build_notification_email_html_content_uses_div_wrapper():
    """HTML content should be wrapped in a styled <div> carrying the same
    inline styles we previously applied to the <p> wrapper."""
    html = _build_notification_email(
        title="Weekly digest",
        content="<ul><li>one</li><li>two</li></ul>",
        link=None,
        recipient_role="parent",
    )

    assert (
        '<div style="color:#333;line-height:1.6;margin:0 0 16px 0;">'
        '<ul><li>one</li><li>two</li></ul>'
        '</div>'
    ) in html


def test_build_notification_email_detects_various_block_tags():
    """Regex should match any of the documented block-level openers."""
    for opener in ("<h1>", "<h2>", "<h3>", "<h4>", "<h5>", "<h6>", "<p>", "<ul>", "<ol>", "<div>", "<hr>"):
        content = f"{opener}content</tag>"
        html = _build_notification_email(
            title="T",
            content=content,
            link=None,
            recipient_role="parent",
        )
        # Must not have the outer <p style="..."> wrapper around HTML block content.
        assert f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">{opener}' not in html, (
            f"opener {opener!r} was wrapped in <p> when it should have been <div>"
        )


def test_build_notification_email_leading_whitespace_before_block_tag():
    """Leading whitespace/newlines before an HTML block opener should still be
    detected (regex uses \\s*)."""
    html = _build_notification_email(
        title="T",
        content="\n  <h3>X</h3>",
        link=None,
        recipient_role="parent",
    )
    # Should use <div> wrap, not <p>.
    assert '<div style="color:#333;line-height:1.6;margin:0 0 16px 0;">' in html
    assert '<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">\n' not in html


# ---------------------------------------------------------------------------
# Three-valued per-channel status convention (#3887)
#
# send_multi_channel_notification must return:
#   - True  → channel requested AND delivery succeeded
#   - False → channel requested AND delivery actually failed (exception /
#             underlying helper returned False)
#   - None  → not applicable: channel not requested OR preference-suppressed
#             OR no email on file OR no valid sender (cb_message only)
#
# Crucially: preference-skipped channels must return None, NOT False.
# ---------------------------------------------------------------------------


def _make_user(db_session, **overrides):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    defaults = dict(
        email=f"notif_test_{overrides.pop('suffix', 'a')}@test.com",
        full_name="Test Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("Password123!"),
        email_notifications=True,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


def test_multi_channel_preference_suppressed_in_app_returns_none(db_session):
    """#3887 — should_notify=False for in-app must yield in_app=None, not False."""
    from app.models.notification import NotificationType

    recipient = _make_user(db_session, suffix="in_app_pref_off")

    # Force should_notify to return False for in-app channel (preference-suppressed).
    original = recipient.__class__.should_notify

    def fake_should_notify(self, notif_type, channel):
        if channel == "in_app":
            return False
        return True

    with patch.object(recipient.__class__, "should_notify", new=fake_should_notify):
        result = send_multi_channel_notification(
            db=db_session,
            recipient=recipient,
            sender=None,
            title="T",
            content="C",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link=None,
            channels=["app_notification"],
        )

    # Restore just in case (patch.object handles this, but defensive).
    recipient.__class__.should_notify = original

    assert result is not None
    assert result["in_app"] is None, (
        "preference-suppressed in-app must return None (not applicable), not False (#3887)"
    )


def test_multi_channel_no_email_on_file_returns_none(db_session):
    """#3887 — recipient has no email address → email=None, not False."""
    from app.models.notification import NotificationType

    recipient = _make_user(
        db_session, suffix="no_email", email=None
    )

    result = send_multi_channel_notification(
        db=db_session,
        recipient=recipient,
        sender=None,
        title="T",
        content="C",
        notification_type=NotificationType.PARENT_EMAIL_DIGEST,
        link=None,
        channels=["email"],
    )

    assert result is not None
    assert result["email"] is None, (
        "No email on file must return None (not applicable), not False (#3887)"
    )


def test_multi_channel_email_notifications_disabled_returns_none(db_session):
    """#3887 — email_notifications=False → email=None, not False."""
    from app.models.notification import NotificationType

    recipient = _make_user(
        db_session, suffix="email_off", email_notifications=False
    )

    result = send_multi_channel_notification(
        db=db_session,
        recipient=recipient,
        sender=None,
        title="T",
        content="C",
        notification_type=NotificationType.PARENT_EMAIL_DIGEST,
        link=None,
        channels=["email"],
    )

    assert result is not None
    assert result["email"] is None


def test_multi_channel_cb_message_no_sender_returns_none(db_session):
    """#3887 — classbridge_message channel without a sender → cb_message=None, not False."""
    from app.models.notification import NotificationType

    recipient = _make_user(db_session, suffix="cb_no_sender")

    result = send_multi_channel_notification(
        db=db_session,
        recipient=recipient,
        sender=None,  # system notification — no sender
        title="T",
        content="C",
        notification_type=NotificationType.PARENT_EMAIL_DIGEST,
        link=None,
        channels=["classbridge_message"],
    )

    assert result is not None
    assert result["classbridge_message"] is None, (
        "System notification (no sender) must return None for cb_message, not False (#3887)"
    )


def test_multi_channel_cb_message_self_send_returns_none(db_session):
    """#3887 — sender is the recipient (self-send) → cb_message=None, not False."""
    from app.models.notification import NotificationType

    user = _make_user(db_session, suffix="cb_self")

    result = send_multi_channel_notification(
        db=db_session,
        recipient=user,
        sender=user,  # self-send
        title="T",
        content="C",
        notification_type=NotificationType.PARENT_EMAIL_DIGEST,
        link=None,
        channels=["classbridge_message"],
    )

    assert result is not None
    assert result["classbridge_message"] is None


def test_multi_channel_email_send_exception_returns_false(db_session):
    """#3887 — actual send_email_sync exception → email=False (real failure)."""
    from app.models.notification import NotificationType

    recipient = _make_user(db_session, suffix="email_raise")

    def raise_err(*args, **kwargs):
        raise RuntimeError("SendGrid exploded")

    with patch(
        "app.services.notification_service.send_email_sync",
        side_effect=raise_err,
    ):
        result = send_multi_channel_notification(
            db=db_session,
            recipient=recipient,
            sender=None,
            title="T",
            content="C",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link=None,
            channels=["email"],
        )

    assert result is not None
    assert result["email"] is False, (
        "Actual send_email_sync exception must return False (#3887)"
    )


def test_multi_channel_email_send_returns_false(db_session):
    """#3887 — send_email_sync returns False → email=False."""
    from app.models.notification import NotificationType

    recipient = _make_user(db_session, suffix="email_false")

    with patch(
        "app.services.notification_service.send_email_sync",
        return_value=False,
    ):
        result = send_multi_channel_notification(
            db=db_session,
            recipient=recipient,
            sender=None,
            title="T",
            content="C",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link=None,
            channels=["email"],
        )

    assert result is not None
    assert result["email"] is False


def test_multi_channel_cb_message_exception_returns_false(db_session):
    """#3887 — _send_as_classbridge_message exception → cb_message=False."""
    from app.models.notification import NotificationType

    recipient = _make_user(db_session, suffix="cb_raise_recv")
    sender = _make_user(db_session, suffix="cb_raise_send")

    def raise_err(*args, **kwargs):
        raise RuntimeError("CB message send exploded")

    with patch(
        "app.services.notification_service._send_as_classbridge_message",
        side_effect=raise_err,
    ):
        result = send_multi_channel_notification(
            db=db_session,
            recipient=recipient,
            sender=sender,
            title="T",
            content="C",
            notification_type=NotificationType.PARENT_EMAIL_DIGEST,
            link=None,
            channels=["classbridge_message"],
        )

    assert result is not None
    assert result["classbridge_message"] is False, (
        "Actual _send_as_classbridge_message exception must return False (#3887)"
    )
