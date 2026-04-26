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
