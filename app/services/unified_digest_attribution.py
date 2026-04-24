"""Kid-attribution algorithm for unified digest v2 (#4012, #4015).

Given the headers of a single email pulled from a parent's Gmail, decide
which kid(s) the email should be attributed to. Attribution happens in
three stages:

1. Match the ``To:`` / ``Delivered-To:`` recipient addresses against
   ``ParentChildSchoolEmail`` rows scoped to this parent. Each match
   stamps ``forwarding_seen_at = now()`` on the matched row so the UI
   can surface whether forwarding has been observed.
2. If step 1 produced nothing, fall back to
   ``ParentDigestMonitoredSender`` lookup on
   (parent_id, email_address == From: address).
3. If the sender exists and has ``applies_to_all=True``, attribute the
   email to ALL of the parent's child profiles. If it has specific
   ``SenderChildAssignment`` rows, attribute to those profiles.
4. If neither step matched, the email is unattributed.

The return shape is a plain dict so callers can serialize it cleanly
into the digest structure without depending on ORM objects:

    {
        "kid_ids": list[int],   # ParentChildProfile.id values
        "source": str,          # "school_email" | "sender_tag" |
                                # "applies_to_all" | "unattributed"
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

def _normalize_address(raw: str) -> str:
    """Lower-case and strip an RFC-5322 address, peeling any display name.

    Accepts both ``"Name <x@y.com>"`` and bare ``x@y.com``. Returns the
    lower-cased email portion with surrounding whitespace stripped.
    Returns an empty string when no usable address can be extracted.
    """
    if not raw:
        return ""
    s = raw.strip()
    if "<" in s and ">" in s:
        try:
            s = s.split("<", 1)[1].split(">", 1)[0]
        except IndexError:
            pass
    return s.strip().lower()


def _split_address_header(value: str | None) -> list[str]:
    """Split a comma-separated ``To:`` / ``Delivered-To:`` header value.

    Gmail returns these fields as comma-separated strings even when
    multiple recipients are present. We split on ``,`` and normalize each
    chunk. Empty chunks are discarded.
    """
    if not value:
        return []
    parts = [_normalize_address(p) for p in value.split(",")]
    return [p for p in parts if p]


def extract_recipient_addresses(headers: dict) -> list[str]:
    """Collect normalized recipient addresses from ``To:`` + ``Delivered-To:``.

    Accepts a dict whose keys may be upper- or lower-case. Values may be
    either a single string OR a list of strings (Gmail occasionally
    emits multiple ``Delivered-To:`` headers). Duplicates are removed
    while preserving first-seen order.
    """
    lowered = {str(k).lower(): v for k, v in (headers or {}).items()}
    collected: list[str] = []

    for key in ("to", "delivered-to"):
        raw = lowered.get(key)
        if raw is None:
            continue
        values = raw if isinstance(raw, list) else [raw]
        for v in values:
            for addr in _split_address_header(v):
                if addr and addr not in collected:
                    collected.append(addr)
    return collected


def extract_from_address(headers: dict) -> str:
    """Return the normalized ``From:`` address or ``""`` if absent."""
    lowered = {str(k).lower(): v for k, v in (headers or {}).items()}
    raw = lowered.get("from")
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return _normalize_address(raw or "")


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

ATTR_SOURCE_SCHOOL_EMAIL = "school_email"
ATTR_SOURCE_SENDER_TAG = "sender_tag"
ATTR_SOURCE_APPLIES_TO_ALL = "applies_to_all"
ATTR_SOURCE_UNATTRIBUTED = "unattributed"


def attribute_email(
    headers: dict,
    parent_id: int,
    db: Session,
    *,
    now: datetime | None = None,
) -> dict:
    """Decide which kid profile(s) an email belongs to.

    Parameters
    ----------
    headers:
        Lower- or upper-cased header dict. Must supply ``To`` and/or
        ``Delivered-To`` for the school-email match, and ``From`` for
        the sender-tag fallback. Values may be strings or lists of
        strings (multiple ``Delivered-To:`` lines).
    parent_id:
        Owning parent's ``User.id``. All matches are scoped to this
        parent — a sender that matches a different parent's row does
        NOT leak across accounts.
    db:
        Open SQLAlchemy session; the function flushes ``forwarding_seen_at``
        stamps when school-email matches are found. The outer caller is
        responsible for committing the session (see #4051).
    now:
        Optional clock override for deterministic tests.

    Returns
    -------
    dict with keys:
        ``kid_ids``: list of ``ParentChildProfile.id`` values
            (empty list iff ``source == "unattributed"``).
        ``source``: one of ``school_email``, ``sender_tag``,
            ``applies_to_all``, ``unattributed``.
    """
    # Lazy imports — tests reload models between runs and a module-level
    # import would pin the stale class object.
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestMonitoredSender,
        SenderChildAssignment,
    )

    recipients = extract_recipient_addresses(headers)
    from_address = extract_from_address(headers)
    stamp_time = now or datetime.now(timezone.utc)

    # --- Stage 1: school-email match (To / Delivered-To) ----------------
    if recipients:
        matches = (
            db.query(ParentChildSchoolEmail)
            .join(
                ParentChildProfile,
                ParentChildProfile.id == ParentChildSchoolEmail.child_profile_id,
            )
            .filter(ParentChildProfile.parent_id == parent_id)
            .filter(ParentChildSchoolEmail.email_address.in_(recipients))
            .all()
        )
        if matches:
            kid_ids: list[int] = []
            for row in matches:
                if row.child_profile_id not in kid_ids:
                    kid_ids.append(row.child_profile_id)
                row.forwarding_seen_at = stamp_time
            # #4051 — flush stamps into the session without committing so
            # the outer worker transaction stays atomic. The worker commits
            # once all emails for the parent are attributed.
            try:
                db.flush()
            except Exception:
                logger.exception(
                    "attribute_email: failed to flush forwarding_seen_at "
                    "| parent_id=%s recipients=%s",
                    parent_id,
                    recipients,
                )
            return {
                "kid_ids": kid_ids,
                "source": ATTR_SOURCE_SCHOOL_EMAIL,
            }

    # --- Stage 2: sender-tag fallback (From address) --------------------
    if from_address:
        sender = (
            db.query(ParentDigestMonitoredSender)
            .filter(
                ParentDigestMonitoredSender.parent_id == parent_id,
                ParentDigestMonitoredSender.email_address == from_address,
            )
            .first()
        )
        if sender is not None:
            if sender.applies_to_all:
                all_profile_ids = [
                    pid
                    for (pid,) in (
                        db.query(ParentChildProfile.id)
                        .filter(ParentChildProfile.parent_id == parent_id)
                        .all()
                    )
                ]
                return {
                    "kid_ids": all_profile_ids,
                    "source": ATTR_SOURCE_APPLIES_TO_ALL,
                }
            assignment_ids = [
                pid
                for (pid,) in (
                    db.query(SenderChildAssignment.child_profile_id)
                    .filter(SenderChildAssignment.sender_id == sender.id)
                    .all()
                )
            ]
            # Preserve input order + dedupe (tests expect stable output).
            seen: set[int] = set()
            deduped: list[int] = []
            for pid in assignment_ids:
                if pid not in seen:
                    seen.add(pid)
                    deduped.append(pid)
            return {
                "kid_ids": deduped,
                "source": ATTR_SOURCE_SENDER_TAG,
            }

    # --- Stage 3: unattributed -----------------------------------------
    return {"kid_ids": [], "source": ATTR_SOURCE_UNATTRIBUTED}


# ---------------------------------------------------------------------------
# Sectioning helper — used by the single-digest-per-parent worker path
# ---------------------------------------------------------------------------

def build_sectioned_digest(
    attributed: Iterable[tuple[dict, dict]],
) -> dict:
    """Group attributed emails into the unified-digest section shape.

    Input: iterable of ``(email, attribution)`` tuples where
    ``attribution`` is the dict returned by :func:`attribute_email`.

    Output:
        {
            "for_all_kids": [email, ...],
            "per_kid": { kid_id: [email, ...] },
            "unattributed": [email, ...],
        }

    Rules:
    - ``applies_to_all`` → "for_all_kids".
    - ``school_email`` matching MULTIPLE kids → "for_all_kids" (the same
      email is relevant to every kid on the match list, so it belongs in
      the shared banner rather than duplicated in each per-kid section).
    - ``school_email`` or ``sender_tag`` matching EXACTLY one kid →
      ``per_kid[kid_id]``.
    - Anything else (including ``sender_tag`` with zero matches, which
      indicates a malformed sender row) → "unattributed".
    """
    for_all_kids: list[dict] = []
    per_kid: dict[int, list[dict]] = {}
    unattributed: list[dict] = []

    for email, attribution in attributed:
        source = attribution.get("source")
        kid_ids = attribution.get("kid_ids") or []

        if source == ATTR_SOURCE_APPLIES_TO_ALL:
            for_all_kids.append(email)
            continue
        if source == ATTR_SOURCE_SCHOOL_EMAIL and len(kid_ids) > 1:
            for_all_kids.append(email)
            continue
        if source in (ATTR_SOURCE_SCHOOL_EMAIL, ATTR_SOURCE_SENDER_TAG) and len(kid_ids) == 1:
            kid_id = kid_ids[0]
            per_kid.setdefault(kid_id, []).append(email)
            continue
        unattributed.append(email)

    return {
        "for_all_kids": for_all_kids,
        "per_kid": per_kid,
        "unattributed": unattributed,
    }
