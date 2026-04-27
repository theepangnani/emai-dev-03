"""Kid-attribution algorithm for unified digest v2 (#4012, #4015).

Given the headers of a single email pulled from a parent's Gmail, decide
which kid(s) the email should be attributed to. Attribution happens in
four stages (#4329):

1. Match the ``To:`` / ``Delivered-To:`` recipient addresses against
   ``ParentChildSchoolEmail`` rows scoped to this parent. Each match
   stamps ``forwarding_seen_at = now()`` on the matched row so the UI
   can surface whether forwarding has been observed.
2. If the recipient list contains NO school-looking addresses (i.e.
   email was sent directly to the parent's Gmail, not forwarded from
   any school account), short-circuit as ``parent_direct``. Skipping
   the sender-tag fallback here prevents mis-attribution when the
   parent's own school correspondence (school-from-the-parent's-own-
   account) lands in the digest stream.
3. If recipients include unregistered school-looking addresses AND the
   ``From:`` address matches a ``ParentDigestMonitoredSender``,
   attribute via ``applies_to_all`` OR — for strict-subset assignments —
   downgrade to ``sender_tag_ambiguous`` (all kids) because we can't be
   sure which kid this was actually for.
4. Otherwise → ``unattributed``.

Layer A (#4329) also adds :func:`record_discovery` which the worker
calls per email after attribution to surface unregistered school-
looking To: addresses for the parent to assign to a kid.

The return shape is a plain dict so callers can serialize it cleanly
into the digest structure without depending on ORM objects:

    {
        "kid_ids": list[int],   # ParentChildProfile.id values
        "source": str,          # "school_email" | "sender_tag" |
                                # "applies_to_all" | "parent_direct" |
                                # "sender_tag_ambiguous" | "unattributed"
    }
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.school_boards import KNOWN_SCHOOL_BOARD_DOMAINS

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
# School-looking address heuristic (#4329)
# ---------------------------------------------------------------------------

# Why: localparts that always represent automated infrastructure, not real
# students. Bare-token match (split on ``@``) so we don't over-match longer
# names that happen to contain "support" etc.
_NON_PERSON_LOCAL_PARTS = frozenset({
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "support",
    "info",
})


def is_school_looking_address(addr: str) -> bool:
    """Heuristic: does this address look like a forwarded student inbox?

    True iff the domain matches a school-ish pattern AND the local-part
    is not a known infrastructure mailbox. Used both to filter Stage 2
    (parent-direct vs. forwarded) and to gate auto-discovery.
    """
    if not addr or "@" not in addr:
        return False
    local, _, domain = addr.lower().partition("@")
    if not local or not domain:
        return False
    if local in _NON_PERSON_LOCAL_PARTS:
        return False
    # Why: school domains in our user base end in .edu (US) or include
    # gapps.* (Google Workspace for Education) or .k12.* (US K-12 districts).
    if "gapps." in domain:
        return True
    if domain.endswith(".edu") or ".edu." in domain:
        return True
    if ".k12." in domain or domain.endswith(".k12"):
        return True
    # #4346 — match exact apex domain OR any subdomain (e.g. student.ocdsb.ca).
    if any(domain == d or domain.endswith("." + d) for d in KNOWN_SCHOOL_BOARD_DOMAINS):
        return True
    return False


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

ATTR_SOURCE_SCHOOL_EMAIL = "school_email"
ATTR_SOURCE_SENDER_TAG = "sender_tag"
ATTR_SOURCE_APPLIES_TO_ALL = "applies_to_all"
ATTR_SOURCE_UNATTRIBUTED = "unattributed"
ATTR_SOURCE_PARENT_DIRECT = "parent_direct"
ATTR_SOURCE_SENDER_TAG_AMBIGUOUS = "sender_tag_ambiguous"


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
            (empty list iff ``source in {unattributed, parent_direct}``).
        ``source``: one of ``school_email``, ``sender_tag``,
            ``applies_to_all``, ``parent_direct``,
            ``sender_tag_ambiguous``, ``unattributed``.
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
                    "| parent_id=%s recipient_count=%d",
                    parent_id,
                    len(recipients),
                )
            return {
                "kid_ids": kid_ids,
                "source": ATTR_SOURCE_SCHOOL_EMAIL,
            }

    # --- Stage 2: parent-direct short-circuit (#4329) -------------------
    # If none of the recipients look like a school address, the email
    # was sent directly to the parent's Gmail (not forwarded from any
    # school account). Don't fall through to sender-tag — that would
    # mis-attribute parent-direct mail to a kid.
    school_looking_recipients = [r for r in recipients if is_school_looking_address(r)]
    if not school_looking_recipients:
        return {"kid_ids": [], "source": ATTR_SOURCE_PARENT_DIRECT}

    # --- Stage 3: sender-tag fallback (From address) --------------------
    # We only get here when at least one recipient is a school-looking
    # address that isn't registered for any of this parent's kids.
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
            # Strict-subset case — downgrade to all-kids ambiguous because
            # the recipient is a school address we don't recognize, so we
            # can't be sure which kid this was actually for (#4329).
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
                "source": ATTR_SOURCE_SENDER_TAG_AMBIGUOUS,
            }

    # --- Stage 4: unattributed -----------------------------------------
    return {"kid_ids": [], "source": ATTR_SOURCE_UNATTRIBUTED}


# ---------------------------------------------------------------------------
# Auto-discovery (#4329)
# ---------------------------------------------------------------------------


def record_discovery(
    headers: dict,
    parent_id: int,
    db: Session,
    *,
    registered_addresses: set[str] | None = None,
) -> None:
    """Surface unregistered school-looking To: addresses for the parent.

    Called by the digest worker after :func:`attribute_email`. For each
    school-looking recipient that isn't already registered in
    ``parent_child_school_emails`` for any of the parent's kids, upsert a
    row in ``parent_discovered_school_emails`` (incrementing ``occurrences``
    + refreshing ``last_seen_at`` + replacing ``sample_sender``).

    ``registered_addresses`` is an optional pre-fetched set of already-
    registered school addresses (lower-cased) for this parent. The worker
    fetches once per parent batch and passes it through to avoid an
    O(N-emails) query (#4341). When omitted, falls back to a per-call
    query for back-compat with direct callers / tests.

    Uses ``db.flush()`` only — the worker commits at the end (per #4051).
    """
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDiscoveredSchoolEmail,
    )

    recipients = extract_recipient_addresses(headers)
    if not recipients:
        return

    candidates = [r for r in recipients if is_school_looking_address(r)]
    if not candidates:
        return

    # Drop addresses already registered for any of this parent's kids.
    if registered_addresses is None:
        registered_rows = (
            db.query(ParentChildSchoolEmail.email_address)
            .join(
                ParentChildProfile,
                ParentChildProfile.id == ParentChildSchoolEmail.child_profile_id,
            )
            .filter(ParentChildProfile.parent_id == parent_id)
            .filter(ParentChildSchoolEmail.email_address.in_(candidates))
            .all()
        )
        registered = {addr.lower() for (addr,) in registered_rows if addr}
    else:
        registered = registered_addresses
    unregistered = [c for c in candidates if c not in registered]
    if not unregistered:
        return

    sample_sender = extract_from_address(headers) or None
    stamp_time = datetime.now(timezone.utc)

    for addr in unregistered:
        existing = (
            db.query(ParentDiscoveredSchoolEmail)
            .filter(
                ParentDiscoveredSchoolEmail.parent_id == parent_id,
                ParentDiscoveredSchoolEmail.email_address == addr,
            )
            .first()
        )
        if existing is None:
            db.add(ParentDiscoveredSchoolEmail(
                parent_id=parent_id,
                email_address=addr,
                sample_sender=sample_sender,
                occurrences=1,
                first_seen_at=stamp_time,
                last_seen_at=stamp_time,
            ))
        else:
            existing.occurrences = (existing.occurrences or 0) + 1
            existing.last_seen_at = stamp_time
            if sample_sender:
                existing.sample_sender = sample_sender

    try:
        db.flush()
    except Exception:
        logger.exception(
            "record_discovery: failed to flush discovery rows | parent_id=%s candidates=%d",
            parent_id,
            len(unregistered),
        )


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
            "parent_direct": [email, ...],
            "unattributed": [email, ...],
        }

    Rules:
    - ``applies_to_all`` → "for_all_kids".
    - ``school_email`` matching MULTIPLE kids → "for_all_kids" (the same
      email is relevant to every kid on the match list, so it belongs in
      the shared banner rather than duplicated in each per-kid section).
    - ``school_email`` or ``sender_tag`` matching EXACTLY one kid →
      ``per_kid[kid_id]``.
    - ``sender_tag_ambiguous`` → "for_all_kids" (we can't pin to a single
      kid, so render under the shared banner alongside applies_to_all).
    - ``parent_direct`` → "parent_direct" (rendered as a top section,
      "Sent directly to you").
    - Anything else → "unattributed".
    """
    for_all_kids: list[dict] = []
    per_kid: dict[int, list[dict]] = {}
    parent_direct: list[dict] = []
    unattributed: list[dict] = []

    for email, attribution in attributed:
        source = attribution.get("source")
        kid_ids = attribution.get("kid_ids") or []

        if source == ATTR_SOURCE_APPLIES_TO_ALL:
            for_all_kids.append(email)
            continue
        if source == ATTR_SOURCE_SENDER_TAG_AMBIGUOUS:
            for_all_kids.append(email)
            continue
        if source == ATTR_SOURCE_SCHOOL_EMAIL and len(kid_ids) > 1:
            for_all_kids.append(email)
            continue
        if source in (ATTR_SOURCE_SCHOOL_EMAIL, ATTR_SOURCE_SENDER_TAG) and len(kid_ids) == 1:
            kid_id = kid_ids[0]
            per_kid.setdefault(kid_id, []).append(email)
            continue
        if source == ATTR_SOURCE_PARENT_DIRECT:
            parent_direct.append(email)
            continue
        unattributed.append(email)

    return {
        "for_all_kids": for_all_kids,
        "per_kid": per_kid,
        "parent_direct": parent_direct,
        "unattributed": unattributed,
    }
