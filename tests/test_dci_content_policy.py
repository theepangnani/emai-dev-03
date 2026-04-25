"""Tests for DCI content-policy v0 (CB-DCI-001 M0-7, issue #4144).

Coverage requirement from spec:
- 1 case per block rule (PII × 4, named-other-kid, medical, legal) MUST block
- 1 clean case MUST pass
- 1 redaction case MUST redact AND remain allowed (PII-only)

Audit-service integration is exercised via a unittest.mock patch — the
real ``audit_service.log_action`` writes to the DB through SQLAlchemy and
is covered by ``tests/test_audit.py``. We only need to verify the policy
module calls it with the right shape.

TODO(#4149): Replace these regex/keyword tests with the ML-classifier
test suite once the fast-follow ships.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.services import dci_content_policy
from app.services.dci_content_policy import check


# ---------------------------------------------------------------------------
# Clean case (must pass)
# ---------------------------------------------------------------------------

def test_clean_summary_passes() -> None:
    text = (
        "Today Aanya worked on multiplication tables and read a chapter of "
        "her library book. She mentioned a science handout about plant "
        "life cycles is due Friday."
    )
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert result["blocked_rules"] == []
    assert result["redacted_text"] is None


def test_empty_text_passes() -> None:
    result = check("", family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert result["blocked_rules"] == []
    assert result["redacted_text"] is None


def test_none_text_passes() -> None:
    # type: ignore[arg-type] — defensive: callers may pass None.
    result = check(None, family_kid_names=["Aanya"])  # type: ignore[arg-type]
    assert result["allowed"] is True
    assert result["blocked_rules"] == []


# ---------------------------------------------------------------------------
# PII rules — must redact (PII-only stays allowed)
# ---------------------------------------------------------------------------

def test_pii_sin_is_redacted_and_allowed() -> None:
    text = "Aanya's SIN is 123-456-789 in case the school asks."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "pii_sin" in result["blocked_rules"]
    assert result["redacted_text"] is not None
    assert "123-456-789" not in result["redacted_text"]
    assert "[REDACTED_SIN]" in result["redacted_text"]


def test_pii_phone_is_redacted_and_allowed() -> None:
    text = "Call the teacher at 416-555-1234 to discuss next steps."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "pii_phone" in result["blocked_rules"]
    assert result["redacted_text"] is not None
    assert "416-555-1234" not in result["redacted_text"]
    assert "[REDACTED_PHONE]" in result["redacted_text"]


def test_pii_email_is_redacted_and_allowed() -> None:
    text = "The teacher said you can reach her at j.smith@school.ca tomorrow."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "pii_email" in result["blocked_rules"]
    assert result["redacted_text"] is not None
    assert "j.smith@school.ca" not in result["redacted_text"]
    assert "[REDACTED_EMAIL]" in result["redacted_text"]


def test_pii_address_is_redacted_and_allowed() -> None:
    text = "Drop the form at 123 Maple Street before Friday."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "pii_address" in result["blocked_rules"]
    assert result["redacted_text"] is not None
    assert "123 Maple Street" not in result["redacted_text"]
    assert "[REDACTED_ADDRESS]" in result["redacted_text"]


def test_redaction_case_combined_pii_still_allowed() -> None:
    """Spec-mandated redaction case: PII present, scrubbed, still allowed."""
    text = (
        "Call 416-555-1234 or email teacher@school.ca about the worksheet."
    )
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "pii_phone" in result["blocked_rules"]
    assert "pii_email" in result["blocked_rules"]
    assert result["redacted_text"] is not None
    assert "416-555-1234" not in result["redacted_text"]
    assert "teacher@school.ca" not in result["redacted_text"]


# ---------------------------------------------------------------------------
# Named other-kid rule — must block
# ---------------------------------------------------------------------------

def test_named_other_kid_in_school_context_blocks() -> None:
    text = (
        "Aanya said her classmate Priya forgot her lunch and cried at recess."
    )
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "named_other_kid" in result["blocked_rules"]


def test_named_own_kid_does_not_block() -> None:
    """Family's own kid name in school context must be allowed."""
    text = "Aanya raised her hand in class to answer a math question."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "named_other_kid" not in result["blocked_rules"]


def test_capitalised_word_without_school_context_does_not_block() -> None:
    """Random capitalised words outside school context must not trip."""
    text = "We learned about Mars and the solar system today."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "named_other_kid" not in result["blocked_rules"]


def test_multiple_family_kids_whitelisted() -> None:
    text = "Aanya and Veer worked together at their classroom desk."
    result = check(text, family_kid_names=["Aanya", "Veer"])
    assert result["allowed"] is True


def test_possessive_form_of_own_kid_does_not_block() -> None:
    """``Aanya's`` should be normalised to ``Aanya`` for whitelist match."""
    text = "Aanya's classmate Priya cried at recess today."
    result = check(text, family_kid_names=["Aanya"])
    # Aanya itself stays whitelisted; only Priya should flag.
    assert result["allowed"] is False
    assert "named_other_kid" in result["blocked_rules"]


def test_apostrophe_name_detected_in_school_context() -> None:
    """Internal-apostrophe names like O'Brien should still flag."""
    text = "Aanya played at recess with her classmate O'Brien today."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "named_other_kid" in result["blocked_rules"]


def test_empty_family_list_flags_school_context_name() -> None:
    """When family list is unknown, any school-context name flags."""
    text = "The classmate Priya cried at recess today."
    result = check(text, family_kid_names=[])
    assert result["allowed"] is False
    assert "named_other_kid" in result["blocked_rules"]


# ---------------------------------------------------------------------------
# Medical rule — must block
# ---------------------------------------------------------------------------

def test_medical_diagnosis_phrase_blocks() -> None:
    text = "The teacher thinks Aanya might have ADHD based on today's behaviour."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "medical_keyword" in result["blocked_rules"]


def test_medical_medication_phrase_blocks() -> None:
    text = "Aanya needs medication for her focus issues at school."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "medical_keyword" in result["blocked_rules"]


# ---------------------------------------------------------------------------
# Legal rule — must block
# ---------------------------------------------------------------------------

def test_legal_lawsuit_phrase_blocks() -> None:
    text = (
        "The teacher's behaviour was outrageous — you should sue the school "
        "board over this incident."
    )
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "legal_keyword" in result["blocked_rules"]


def test_legal_police_phrase_blocks() -> None:
    text = "Honestly, the police should look into what happened at recess."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    assert "legal_keyword" in result["blocked_rules"]


# ---------------------------------------------------------------------------
# Multiple-rule fail
# ---------------------------------------------------------------------------

def test_multiple_rules_all_recorded() -> None:
    text = (
        "Aanya's friend Priya was diagnosed with autism — the teacher said "
        "you should sue. Reach out at parent@example.com."
    )
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is False
    rules = set(result["blocked_rules"])
    assert "named_other_kid" in rules
    assert "medical_keyword" in rules
    assert "legal_keyword" in rules
    assert "pii_email" in rules


# ---------------------------------------------------------------------------
# Audit log integration
# ---------------------------------------------------------------------------

def test_audit_block_calls_audit_service_with_expected_shape() -> None:
    """audit_block must call audit_service.log_action with the right args."""
    fake_db = MagicMock()
    with patch.object(dci_content_policy.audit_service, "log_action") as mock_log:
        dci_content_policy.audit_block(
            fake_db,
            parent_id=42,
            summary_id=7,
            blocked_rules=["medical_keyword", "legal_keyword"],
            raw="Some raw blocked summary text.",
        )
    mock_log.assert_called_once()
    _args, kwargs = mock_log.call_args
    assert kwargs["user_id"] == 42
    assert kwargs["action"] == "dci_policy_block"
    assert kwargs["resource_type"] == "ai_summary"
    assert kwargs["resource_id"] == 7
    assert kwargs["details"]["blocked_rules"] == [
        "medical_keyword", "legal_keyword",
    ]
    assert "raw_excerpt" in kwargs["details"]


def test_audit_block_truncates_long_raw_text() -> None:
    long_raw = "x" * 2000
    fake_db = MagicMock()
    with patch.object(dci_content_policy.audit_service, "log_action") as mock_log:
        dci_content_policy.audit_block(
            fake_db,
            parent_id=1,
            summary_id=1,
            blocked_rules=["pii_sin"],
            raw=long_raw,
        )
    _args, kwargs = mock_log.call_args
    assert len(kwargs["details"]["raw_excerpt"]) == 500


def test_audit_block_supports_extra_details() -> None:
    fake_db = MagicMock()
    with patch.object(dci_content_policy.audit_service, "log_action") as mock_log:
        dci_content_policy.audit_block(
            fake_db,
            parent_id=1,
            summary_id=1,
            blocked_rules=["pii_sin"],
            raw="hi",
            extra={"retry_count": 2, "model_version": "sonnet-4.6"},
        )
    _args, kwargs = mock_log.call_args
    assert kwargs["details"]["retry_count"] == 2
    assert kwargs["details"]["model_version"] == "sonnet-4.6"


def test_audit_block_extra_cannot_clobber_canonical_keys() -> None:
    """A buggy caller passing protected keys in ``extra`` must not win."""
    fake_db = MagicMock()
    with patch.object(dci_content_policy.audit_service, "log_action") as mock_log:
        dci_content_policy.audit_block(
            fake_db,
            parent_id=1,
            summary_id=1,
            blocked_rules=["pii_sin"],
            raw="real raw text",
            extra={
                "blocked_rules": ["EVIL_OVERRIDE"],
                "raw_excerpt": "EVIL_OVERRIDE",
                "retry_count": 3,
            },
        )
    _args, kwargs = mock_log.call_args
    assert kwargs["details"]["blocked_rules"] == ["pii_sin"]
    assert kwargs["details"]["raw_excerpt"] == "real raw text"
    assert kwargs["details"]["retry_count"] == 3


# ---------------------------------------------------------------------------
# Defensive cap on input length
# ---------------------------------------------------------------------------

def test_check_truncates_pathologically_long_input() -> None:
    """``check`` must not blow up on a 1MB input — it truncates first."""
    big = "All good today. " * 100_000  # ~1.6MB
    result = check(big, family_kid_names=["Aanya"])
    # Should still return a well-formed result without raising.
    assert isinstance(result["allowed"], bool)


# ---------------------------------------------------------------------------
# Substring-tightening regression: legitimate "diagnosed with" usage
# ---------------------------------------------------------------------------

def test_benign_diagnosed_with_does_not_block() -> None:
    """v0 must not block ``diagnosed with a stomach bug`` etc."""
    text = "Aanya was diagnosed with a stomach bug and stayed home today."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "medical_keyword" not in result["blocked_rules"]


def test_iep_form_does_not_block() -> None:
    """``IEP form`` (paperwork) must not trip the medical filter."""
    text = "Please sign the IEP form and return it tomorrow."
    result = check(text, family_kid_names=["Aanya"])
    assert result["allowed"] is True
    assert "medical_keyword" not in result["blocked_rules"]


# ---------------------------------------------------------------------------
# Smoke: returned dict shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,family,expected_allowed", [
    ("All good today.", ["Aanya"], True),
    ("call 416-555-1234", ["Aanya"], True),  # PII-only → allowed with redaction
    ("classmate Priya was sad", ["Aanya"], False),
])
def test_result_shape_is_typeddict_compliant(text, family, expected_allowed) -> None:
    result = check(text, family_kid_names=family)
    assert set(result.keys()) == {"allowed", "blocked_rules", "redacted_text"}
    assert isinstance(result["allowed"], bool)
    assert isinstance(result["blocked_rules"], list)
    assert result["allowed"] is expected_allowed
