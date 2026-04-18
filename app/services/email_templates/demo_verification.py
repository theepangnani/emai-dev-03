"""Demo verification email template (CB-DEMO-001 F3, #3602).

Builds the branded HTML for the demo verification email that carries both
a magic-link CTA and a 6-digit fallback code.
"""
from __future__ import annotations

from html import escape as _html_escape

from app.services.email_service import wrap_branded_email

SUBJECT = "Verify your ClassBridge demo"


def build_demo_verification_email(
    full_name: str | None,
    email: str,
    magic_link_url: str,
    fallback_code: str,
) -> tuple[str, str]:
    """Build the (subject, html_body) pair for the demo verification email.

    Args:
        full_name: Display name captured at demo signup. May be None/empty.
        email: Recipient's email address (used in greeting fallback only).
        magic_link_url: Fully-qualified URL (with raw token) for the CTA.
        fallback_code: 6-digit numeric code (zero-padded).

    Returns:
        Tuple of (subject, html_body). html_body is the fully wrapped,
        branded HTML ready to pass to send_email_sync.

    Security: every user-supplied or server-supplied value that is
    interpolated into the HTML body is escaped via ``html.escape`` with
    ``quote=True`` so a crafted ``full_name`` cannot inject script tags,
    arbitrary links, or break out of the href attribute.
    """
    raw_greeting = (full_name or "").strip() or email
    greeting_name = _html_escape(raw_greeting, quote=True)
    safe_url = _html_escape(magic_link_url, quote=True)
    safe_code = _html_escape(fallback_code, quote=True)
    body = (
        f'<h2 style="color:#1a1a2e;margin:0 0 16px 0;">Verify your demo</h2>'
        f'<p style="color:#333;line-height:1.6;margin:0 0 16px 0;">Hi {greeting_name},</p>'
        f'<p style="color:#333;line-height:1.6;margin:0 0 24px 0;">'
        f'You started a ClassBridge demo. Confirm your email to save your '
        f'progress and keep exploring.</p>'
        f'<p style="margin:0 0 24px 0;text-align:center;">'
        f'<a href="{safe_url}" '
        f'style="display:inline-block;background:#4f46e5;color:#ffffff;'
        f'text-decoration:none;font-weight:600;padding:14px 28px;'
        f'border-radius:8px;font-size:16px;">Verify my email</a>'
        f'</p>'
        f'<p style="color:#333;line-height:1.6;margin:0 0 8px 0;">'
        f'Or enter this 6-digit code: '
        f'<strong style="font-size:20px;letter-spacing:3px;color:#1a1a2e;">'
        f'{safe_code}</strong></p>'
        f'<p style="color:#6b7280;line-height:1.6;margin:16px 0 0 0;font-size:14px;">'
        f'This link and code expire in 72 hours.</p>'
        f'<p style="color:#9ca3af;line-height:1.6;margin:24px 0 0 0;font-size:12px;">'
        f"If you didn't start this demo, you can ignore this email.</p>"
    )
    html_body = wrap_branded_email(body)
    return SUBJECT, html_body
