"""Disposable / throwaway email domain blocklist (CB-DEMO-001, #3605).

Used by the Demo flow (FR-054) to reject signups from well-known
disposable mailbox providers. Pure in-memory check — no I/O.
"""
from __future__ import annotations


BLOCKED_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "10minutemail.com",
        "guerrillamail.com",
        "tempmail.io",
        "throwaway.email",
        "yopmail.com",
        "trashmail.com",
        "fakeinbox.com",
        "getnada.com",
        "sharklasers.com",
        "maildrop.cc",
        "mintemail.com",
        "dispostable.com",
        "inboxbear.com",
        "mailnesia.com",
    }
)


def is_disposable(email: str) -> bool:
    """Return True if `email`'s domain is in the disposable blocklist.

    Case-insensitive. Returns False for malformed input (no '@').
    """
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].strip().lower()
    return domain in BLOCKED_DOMAINS
