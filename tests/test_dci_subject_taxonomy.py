"""Tests for app/services/dci_subject_taxonomy.py.

Covers both the strict ``validate_subject`` guard and the kid-friendly
``coerce_subject`` helper (#4231) used by the M0-4 PATCH endpoint to
normalise kid-typed corrections.
"""
from __future__ import annotations

import pytest

from app.services.dci_subject_taxonomy import (
    DCI_VALID_SUBJECTS,
    coerce_subject,
    validate_subject,
)


class TestValidateSubject:
    def test_canonical_passes(self):
        for s in DCI_VALID_SUBJECTS:
            assert validate_subject(s) == s

    def test_none_returns_none(self):
        assert validate_subject(None) is None

    def test_empty_returns_none(self):
        assert validate_subject("") is None
        assert validate_subject("   ") is None

    def test_lowercase_rejected(self):
        # validate_subject is strict — case matters.
        assert validate_subject("math") is None
        assert validate_subject("english") is None

    def test_unknown_rejected(self):
        assert validate_subject("Underwater Basket Weaving") is None

    def test_alias_not_normalised(self):
        # validate_subject does NOT alias-map; that's coerce_subject's job.
        assert validate_subject("maths") is None
        assert validate_subject("gym") is None


class TestCoerceSubject:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Math
            ("math", "Math"),
            ("MATH", "Math"),
            ("Math", "Math"),
            ("maths", "Math"),
            ("Mathematics", "Math"),
            # Science
            ("science", "Science"),
            ("SCIENCE", "Science"),
            ("sci", "Science"),
            # English
            ("english", "English"),
            ("ENGLISH", "English"),
            ("reading", "English"),
            ("Language Arts", "English"),
            ("ela", "English"),
            # History
            ("history", "History"),
            ("Social Studies", "History"),
            ("socials", "History"),
            # Geography
            ("geography", "Geography"),
            ("geo", "Geography"),
            # Art
            ("art", "Art"),
            ("arts", "Art"),
            # Music
            ("music", "Music"),
            # French
            ("french", "French"),
            ("francais", "French"),
            ("français", "French"),
            # Phys-Ed
            ("phys ed", "Phys-Ed"),
            ("phys-ed", "Phys-Ed"),
            ("PHYSED", "Phys-Ed"),
            ("physical education", "Phys-Ed"),
            ("gym", "Phys-Ed"),
            ("PE", "Phys-Ed"),
            # Other
            ("other", "Other"),
        ],
    )
    def test_alias_and_case_normalisation(self, raw, expected):
        assert coerce_subject(raw) == expected

    def test_none_returns_none(self):
        assert coerce_subject(None) is None

    def test_empty_returns_none(self):
        assert coerce_subject("") is None
        assert coerce_subject("   ") is None

    def test_unknown_returns_none(self):
        assert coerce_subject("Underwater Basket Weaving") is None
        assert coerce_subject("xyz") is None

    def test_whitespace_trimmed(self):
        assert coerce_subject("  math  ") == "Math"
        assert coerce_subject("\tscience\n") == "Science"

    def test_canonical_passes_through(self):
        for s in DCI_VALID_SUBJECTS:
            assert coerce_subject(s) == s

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Case-fold path covers canonical names not in the alias map
            # without touching locale-sensitive ``.title()``.
            ("MATH", "Math"),
            ("math", "Math"),
            ("Math", "Math"),
            ("HISTORY", "History"),
            ("history", "History"),
            ("GEOGRAPHY", "Geography"),
            ("phys-ed", "Phys-Ed"),
            ("PHYS-ED", "Phys-Ed"),
            ("Phys-Ed", "Phys-Ed"),
            ("OTHER", "Other"),
            ("other", "Other"),
        ],
    )
    def test_casefold_canonical_lookup(self, raw, expected):
        # Hyphenated canonical (``Phys-Ed``) is the load-bearing case —
        # ``"phys-ed".title()`` returns ``"Phys-Ed"`` only because Python
        # title-cases after the hyphen. Case-fold lookup makes the win
        # explicit and locale-independent. See #4276.
        assert coerce_subject(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            # Strings with apostrophes are the canonical footgun for
            # ``.title()`` ("l'art" → "L'Art" — wrong canonical and
            # locale-sensitive). They must fall through to ``None`` via
            # the explicit lookup path, never via title-casing.
            "l'art",
            "L'ART",
            "d'art",
            "ENGLISH'S",
        ],
    )
    def test_apostrophe_inputs_fall_through_cleanly(self, raw):
        # Not in the alias map, not a case-fold match for any canonical.
        # The explicit lookup must return None — no title-casing involved.
        assert coerce_subject(raw) is None

    def test_no_title_case_round_trip(self):
        # Regression guard: ``"english class".title()`` would yield
        # ``"English Class"`` which is not a canonical subject. Under the
        # old ``.title()`` fallback this still ended up at ``None`` (via
        # ``validate_subject``), but the round-trip masked the intent.
        # The explicit lookup must reject it directly.
        assert coerce_subject("english class") is None
        assert coerce_subject("Math Class") is None

    def test_returned_values_are_canonical(self):
        # Every non-None result must be in the canonical enum — the
        # explicit lookup guarantees this without a final
        # ``validate_subject`` round-trip.
        sample_inputs = [
            "math", "MATHS", "sci", "ENGLISH", "Reading", "ela",
            "Social Studies", "geo", "ARTS", "music", "français",
            "PE", "gym", "phys-ed", "Other",
        ]
        for raw in sample_inputs:
            result = coerce_subject(raw)
            assert result in DCI_VALID_SUBJECTS, f"{raw!r} → {result!r}"
