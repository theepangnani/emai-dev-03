"""Utilities for classifying email senders (automated/noreply detection)."""

import re

# Patterns matched against the local-part (before "@") of the sender address.
# All matching is case-insensitive.
_LOCAL_PART_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^no[-_.]?reply(\+.*)?$", re.IGNORECASE),
    re.compile(r"^do[-_.]?not[-_.]?reply(\+.*)?$", re.IGNORECASE),
    re.compile(r"^donotreply(\+.*)?$", re.IGNORECASE),
    re.compile(r"^notifications?(\+.*)?$", re.IGNORECASE),
    re.compile(r"^alerts?(\+.*)?$", re.IGNORECASE),
    re.compile(r"^mailer[-_.]?daemon(\+.*)?$", re.IGNORECASE),
    re.compile(r"^postmaster(\+.*)?$", re.IGNORECASE),
    re.compile(r"^system(\+.*)?$", re.IGNORECASE),
    re.compile(r"^automated(\+.*)?$", re.IGNORECASE),
    re.compile(r"^bounce[-_.s]*(\+.*)?$", re.IGNORECASE),
    re.compile(r".*[-_.]no[-_.]?reply$", re.IGNORECASE),
    re.compile(r".*[-_.]notifications?$", re.IGNORECASE),
]


def is_automated_sender(sender_email: str) -> bool:
    """Return True if the sender email matches known automated/noreply patterns.

    Matches common patterns on the local-part of the email address:
    - noreply@, no-reply@, no_reply@, donotreply@, do-not-reply@
    - notifications@, notification@, alerts@, alert@
    - mailer-daemon@, postmaster@, system@, automated@, bounces@
    - Compound local-parts like classroom-noreply@, accounts-noreply@
    """
    if not sender_email or "@" not in sender_email:
        return False

    local_part, _, domain = sender_email.strip().partition("@")
    local_part = local_part.lower()
    if not local_part or not domain.strip():
        return False

    for pattern in _LOCAL_PART_PATTERNS:
        if pattern.match(local_part):
            return True
    return False
