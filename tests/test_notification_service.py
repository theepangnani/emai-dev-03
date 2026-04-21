"""Tests for app.services.notification_service helpers.

Focus on #3884 regressions in _build_notification_email — pre-formatted
HTML content must not be wrapped in <p>, while plain-text content must
still be wrapped in <p> exactly as before.
"""
from app.services.notification_service import _build_notification_email


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
