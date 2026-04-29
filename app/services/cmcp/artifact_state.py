"""ContentArtifact state machine — pure logic, no DB or I/O.

CB-CMCP-001 M1-A 1A-3 (#4459). Per locked decisions D2=B (extended
``study_guides`` is the artifact table) and D3=C (hybrid self-study +
class-distribute paths). The actual ``state`` column was added by stripe
0A-2 (#4413); this module only encodes the legal-transition graph and a
few invariants used by upstream callers (workers, API routes, review queue).

State graph (per DD §6.1 + D3=C SELF_STUDY)::

    GENERATING → DRAFT → PENDING_REVIEW → IN_REVIEW → APPROVED → [ARCHIVED]
                                                    → REJECTED → DRAFT (regenerate)
                                                    → APPROVED_VERIFIED (admin spot-check)
    DRAFT → SELF_STUDY (D3=C: student/parent self-initiated, no review queue)

Transitions::

    GENERATING       → DRAFT              (CGP completes generation)
    DRAFT            → PENDING_REVIEW     (auto for class-distribute, or teacher submit)
    DRAFT            → SELF_STUDY         (student/parent self-initiated; D3=C)
    DRAFT            → ARCHIVED           (admin discards)
    PENDING_REVIEW   → IN_REVIEW          (teacher opens artifact in portal)
    IN_REVIEW        → APPROVED           (teacher approves)
    IN_REVIEW        → REJECTED           (teacher rejects)
    REJECTED         → DRAFT              (regenerate)
    APPROVED         → APPROVED_VERIFIED  (curriculum admin verifies)
    APPROVED         → ARCHIVED           (admin removes)
    SELF_STUDY       → ARCHIVED           (user deletes)

Out of scope (per #4459):
- DB persistence of the state column (already on ``study_guides``).
- API endpoints driving transitions (M3-A teacher review queue).
- Domain events on transitions (M3-C surface dispatcher).
"""
from __future__ import annotations


class ArtifactStateError(Exception):
    """Raised on an illegal artifact state transition."""


class ArtifactState:
    """String constants for the legal artifact states."""

    GENERATING: str = "GENERATING"
    DRAFT: str = "DRAFT"
    PENDING_REVIEW: str = "PENDING_REVIEW"
    IN_REVIEW: str = "IN_REVIEW"
    APPROVED: str = "APPROVED"
    APPROVED_VERIFIED: str = "APPROVED_VERIFIED"
    REJECTED: str = "REJECTED"
    SELF_STUDY: str = "SELF_STUDY"
    ARCHIVED: str = "ARCHIVED"


# Adjacency list of legal transitions.
# Frozensets prevent accidental mutation by callers and make membership cheap.
_TRANSITIONS: dict[str, frozenset[str]] = {
    ArtifactState.GENERATING: frozenset({ArtifactState.DRAFT}),
    ArtifactState.DRAFT: frozenset(
        {
            ArtifactState.PENDING_REVIEW,
            ArtifactState.SELF_STUDY,
            ArtifactState.ARCHIVED,
        }
    ),
    ArtifactState.PENDING_REVIEW: frozenset({ArtifactState.IN_REVIEW}),
    ArtifactState.IN_REVIEW: frozenset(
        {ArtifactState.APPROVED, ArtifactState.REJECTED}
    ),
    ArtifactState.REJECTED: frozenset({ArtifactState.DRAFT}),
    ArtifactState.APPROVED: frozenset(
        {ArtifactState.APPROVED_VERIFIED, ArtifactState.ARCHIVED}
    ),
    ArtifactState.SELF_STUDY: frozenset({ArtifactState.ARCHIVED}),
    # Terminal states — no outgoing transitions.
    ArtifactState.APPROVED_VERIFIED: frozenset(),
    ArtifactState.ARCHIVED: frozenset(),
}

_TERMINAL_STATES: frozenset[str] = frozenset(
    {ArtifactState.APPROVED_VERIFIED, ArtifactState.ARCHIVED}
)


class ArtifactStateMachine:
    """Pure-logic state machine for ``study_guides.state``.

    All methods are static — the machine has no per-instance state. Use it
    as ``ArtifactStateMachine.validate_transition(...)`` from any caller
    (workers, API, tests) without constructing an instance.
    """

    @staticmethod
    def can_transition(from_state: str, to_state: str) -> bool:
        """Return ``True`` iff ``from_state → to_state`` is a legal transition.

        Unknown source states return ``False`` (rather than raising) so that
        defensive callers can branch without try/except.
        """
        allowed = _TRANSITIONS.get(from_state)
        if allowed is None:
            return False
        return to_state in allowed

    @staticmethod
    def transitions_from(state: str) -> list[str]:
        """Return a sorted list of legal next states from ``state``.

        Returns ``[]`` for terminal states or unknown states. Sorted output
        is intentional for deterministic UI rendering and stable test
        assertions; do not rely on insertion order.
        """
        allowed = _TRANSITIONS.get(state)
        if not allowed:
            return []
        return sorted(allowed)

    @staticmethod
    def validate_transition(from_state: str, to_state: str) -> None:
        """Raise :class:`ArtifactStateError` if the transition is illegal.

        Intended as a guard at the start of any service-layer transition
        method (e.g. ``approve_artifact``). The error message names both
        states so it is useful in logs without needing extra context.
        """
        if not ArtifactStateMachine.can_transition(from_state, to_state):
            raise ArtifactStateError(
                f"Illegal artifact state transition: {from_state!r} → {to_state!r}"
            )

    @staticmethod
    def is_terminal(state: str) -> bool:
        """Return ``True`` iff ``state`` is terminal (APPROVED_VERIFIED or ARCHIVED).

        Unknown states return ``False``.
        """
        return state in _TERMINAL_STATES

    @staticmethod
    def is_user_visible_self_study(state: str) -> bool:
        """Return ``True`` iff the artifact is in user-visible self-study mode.

        Per D3=C, only ``SELF_STUDY`` artifacts are surfaced to a parent or
        student outside of the teacher review queue. Approved class-distribute
        artifacts have their own visibility rules layered on top of this and
        are deliberately *not* covered here (see M3-E board-scoped surface).
        """
        return state == ArtifactState.SELF_STUDY
