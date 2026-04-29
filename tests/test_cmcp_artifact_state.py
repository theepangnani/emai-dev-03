"""Tests for CB-CMCP-001 M1-A 1A-3 — ContentArtifact state machine (#4459).

Pure-logic tests, no DB fixtures. Verifies:

- Every legal transition listed in DD §6.1 + D3=C SELF_STUDY is allowed.
- Every illegal transition raises :class:`ArtifactStateError`.
- ``transitions_from`` returns the expected fan-out per state.
- ``is_terminal`` is true only for ``APPROVED_VERIFIED`` and ``ARCHIVED``.
- ``is_user_visible_self_study`` is true only for ``SELF_STUDY``.
"""
from __future__ import annotations

import pytest

from app.services.cmcp.artifact_state import (
    ArtifactState,
    ArtifactStateError,
    ArtifactStateMachine,
)


# ---- Source-of-truth fixtures ------------------------------------------------

# Mirrors the adjacency list in artifact_state.py. Any drift here means
# the machine and the test contract have diverged — fix one or the other.
LEGAL_TRANSITIONS: list[tuple[str, str]] = [
    (ArtifactState.GENERATING, ArtifactState.DRAFT),
    (ArtifactState.DRAFT, ArtifactState.PENDING_REVIEW),
    (ArtifactState.DRAFT, ArtifactState.SELF_STUDY),
    (ArtifactState.DRAFT, ArtifactState.ARCHIVED),
    (ArtifactState.PENDING_REVIEW, ArtifactState.IN_REVIEW),
    (ArtifactState.IN_REVIEW, ArtifactState.APPROVED),
    (ArtifactState.IN_REVIEW, ArtifactState.REJECTED),
    (ArtifactState.REJECTED, ArtifactState.DRAFT),
    (ArtifactState.APPROVED, ArtifactState.APPROVED_VERIFIED),
    (ArtifactState.APPROVED, ArtifactState.ARCHIVED),
    (ArtifactState.SELF_STUDY, ArtifactState.ARCHIVED),
]

ALL_STATES: list[str] = [
    ArtifactState.GENERATING,
    ArtifactState.DRAFT,
    ArtifactState.PENDING_REVIEW,
    ArtifactState.IN_REVIEW,
    ArtifactState.APPROVED,
    ArtifactState.APPROVED_VERIFIED,
    ArtifactState.REJECTED,
    ArtifactState.SELF_STUDY,
    ArtifactState.ARCHIVED,
]


# ---- can_transition ----------------------------------------------------------


@pytest.mark.parametrize("from_state,to_state", LEGAL_TRANSITIONS)
def test_can_transition_allows_legal(from_state: str, to_state: str) -> None:
    assert ArtifactStateMachine.can_transition(from_state, to_state) is True


def test_can_transition_rejects_every_non_legal_pair() -> None:
    """Exhaustive: every (from, to) not in LEGAL_TRANSITIONS must be False."""
    legal = set(LEGAL_TRANSITIONS)
    for from_state in ALL_STATES:
        for to_state in ALL_STATES:
            if (from_state, to_state) in legal:
                continue
            assert ArtifactStateMachine.can_transition(from_state, to_state) is False, (
                f"Expected {from_state} → {to_state} to be illegal"
            )


def test_can_transition_rejects_self_loop_for_every_state() -> None:
    """No state may transition to itself — self-loops are not legal."""
    for state in ALL_STATES:
        assert ArtifactStateMachine.can_transition(state, state) is False


def test_can_transition_unknown_source_state_returns_false() -> None:
    assert (
        ArtifactStateMachine.can_transition("NOT_A_STATE", ArtifactState.DRAFT) is False
    )


def test_can_transition_unknown_target_state_returns_false() -> None:
    assert (
        ArtifactStateMachine.can_transition(ArtifactState.DRAFT, "NOT_A_STATE") is False
    )


# ---- transitions_from --------------------------------------------------------


def test_transitions_from_draft() -> None:
    # D3=C: DRAFT branches to either review queue, self-study, or trash.
    assert ArtifactStateMachine.transitions_from(ArtifactState.DRAFT) == sorted(
        [
            ArtifactState.PENDING_REVIEW,
            ArtifactState.SELF_STUDY,
            ArtifactState.ARCHIVED,
        ]
    )


def test_transitions_from_generating() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.GENERATING) == [
        ArtifactState.DRAFT
    ]


def test_transitions_from_pending_review() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.PENDING_REVIEW) == [
        ArtifactState.IN_REVIEW
    ]


def test_transitions_from_in_review() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.IN_REVIEW) == sorted(
        [ArtifactState.APPROVED, ArtifactState.REJECTED]
    )


def test_transitions_from_approved() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.APPROVED) == sorted(
        [ArtifactState.APPROVED_VERIFIED, ArtifactState.ARCHIVED]
    )


def test_transitions_from_rejected() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.REJECTED) == [
        ArtifactState.DRAFT
    ]


def test_transitions_from_self_study() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.SELF_STUDY) == [
        ArtifactState.ARCHIVED
    ]


def test_transitions_from_terminal_states_is_empty() -> None:
    assert ArtifactStateMachine.transitions_from(ArtifactState.APPROVED_VERIFIED) == []
    assert ArtifactStateMachine.transitions_from(ArtifactState.ARCHIVED) == []


def test_transitions_from_unknown_state_is_empty() -> None:
    assert ArtifactStateMachine.transitions_from("NOT_A_STATE") == []


def test_transitions_from_returns_sorted_list() -> None:
    """transitions_from must return a deterministic sorted list (UI/test stability)."""
    for state in ALL_STATES:
        result = ArtifactStateMachine.transitions_from(state)
        assert result == sorted(result), (
            f"transitions_from({state!r}) must be sorted, got {result!r}"
        )


def test_transitions_from_returns_a_list_not_a_frozenset() -> None:
    """The public API contract is ``list[str]`` — not a set. Callers may
    serialize it to JSON or index into it."""
    result = ArtifactStateMachine.transitions_from(ArtifactState.DRAFT)
    assert isinstance(result, list)


# ---- validate_transition -----------------------------------------------------


@pytest.mark.parametrize("from_state,to_state", LEGAL_TRANSITIONS)
def test_validate_transition_allows_legal(from_state: str, to_state: str) -> None:
    # Should not raise.
    ArtifactStateMachine.validate_transition(from_state, to_state)


def test_validate_transition_raises_on_illegal() -> None:
    with pytest.raises(ArtifactStateError) as exc_info:
        ArtifactStateMachine.validate_transition(
            ArtifactState.DRAFT, ArtifactState.APPROVED
        )
    # Error message must name both states for log usefulness.
    msg = str(exc_info.value)
    assert ArtifactState.DRAFT in msg
    assert ArtifactState.APPROVED in msg


def test_validate_transition_raises_on_terminal_outbound() -> None:
    with pytest.raises(ArtifactStateError):
        ArtifactStateMachine.validate_transition(
            ArtifactState.APPROVED_VERIFIED, ArtifactState.ARCHIVED
        )
    with pytest.raises(ArtifactStateError):
        ArtifactStateMachine.validate_transition(
            ArtifactState.ARCHIVED, ArtifactState.DRAFT
        )


def test_validate_transition_raises_on_self_loop() -> None:
    with pytest.raises(ArtifactStateError):
        ArtifactStateMachine.validate_transition(
            ArtifactState.DRAFT, ArtifactState.DRAFT
        )


def test_validate_transition_raises_on_unknown_state() -> None:
    with pytest.raises(ArtifactStateError):
        ArtifactStateMachine.validate_transition("NOT_A_STATE", ArtifactState.DRAFT)


# ---- is_terminal -------------------------------------------------------------


def test_is_terminal_true_for_approved_verified() -> None:
    assert ArtifactStateMachine.is_terminal(ArtifactState.APPROVED_VERIFIED) is True


def test_is_terminal_true_for_archived() -> None:
    assert ArtifactStateMachine.is_terminal(ArtifactState.ARCHIVED) is True


@pytest.mark.parametrize(
    "state",
    [
        ArtifactState.GENERATING,
        ArtifactState.DRAFT,
        ArtifactState.PENDING_REVIEW,
        ArtifactState.IN_REVIEW,
        ArtifactState.APPROVED,
        ArtifactState.REJECTED,
        ArtifactState.SELF_STUDY,
    ],
)
def test_is_terminal_false_for_non_terminal_states(state: str) -> None:
    assert ArtifactStateMachine.is_terminal(state) is False


def test_is_terminal_false_for_unknown_state() -> None:
    assert ArtifactStateMachine.is_terminal("NOT_A_STATE") is False


# ---- is_user_visible_self_study ---------------------------------------------


def test_is_user_visible_self_study_true_only_for_self_study() -> None:
    assert (
        ArtifactStateMachine.is_user_visible_self_study(ArtifactState.SELF_STUDY)
        is True
    )


@pytest.mark.parametrize(
    "state",
    [
        ArtifactState.GENERATING,
        ArtifactState.DRAFT,
        ArtifactState.PENDING_REVIEW,
        ArtifactState.IN_REVIEW,
        ArtifactState.APPROVED,
        ArtifactState.APPROVED_VERIFIED,
        ArtifactState.REJECTED,
        ArtifactState.ARCHIVED,
    ],
)
def test_is_user_visible_self_study_false_for_other_states(state: str) -> None:
    assert ArtifactStateMachine.is_user_visible_self_study(state) is False


def test_is_user_visible_self_study_false_for_unknown_state() -> None:
    assert ArtifactStateMachine.is_user_visible_self_study("NOT_A_STATE") is False


# ---- State constants are bare strings ---------------------------------------


def test_state_constants_are_strings() -> None:
    """The DB column is ``String(30)`` — constants must be plain strings so
    they can be assigned directly without an Enum-to-value conversion."""
    for state in ALL_STATES:
        assert isinstance(state, str)


def test_state_constant_values_match_their_names() -> None:
    """Constants are self-named (``DRAFT == 'DRAFT'``) so DB rows are
    human-readable. Guard against a future rename drift."""
    assert ArtifactState.GENERATING == "GENERATING"
    assert ArtifactState.DRAFT == "DRAFT"
    assert ArtifactState.PENDING_REVIEW == "PENDING_REVIEW"
    assert ArtifactState.IN_REVIEW == "IN_REVIEW"
    assert ArtifactState.APPROVED == "APPROVED"
    assert ArtifactState.APPROVED_VERIFIED == "APPROVED_VERIFIED"
    assert ArtifactState.REJECTED == "REJECTED"
    assert ArtifactState.SELF_STUDY == "SELF_STUDY"
    assert ArtifactState.ARCHIVED == "ARCHIVED"
