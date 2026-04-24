"""Tests for grade-level tone adapters (#4071)."""

import pytest

from app.prompts.grade_tone import get_tone_profile


EXPECTED_KEYS = {"voice", "vocabulary", "sentence_length", "examples", "directive"}


@pytest.mark.parametrize("grade", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, None])
def test_returns_dict_for_each_grade(grade):
    profile = get_tone_profile(grade)
    assert isinstance(profile, dict)
    assert set(profile.keys()) == EXPECTED_KEYS
    for key, val in profile.items():
        assert isinstance(val, str) and val.strip(), f"{key} must be a non-empty string"


def test_k3_profile_mentions_simple_words():
    for g in (0, 1, 2, 3):
        profile = get_tone_profile(g)
        combined = (profile["vocabulary"] + " " + profile["directive"]).lower()
        assert "simple" in combined, f"K-3 grade {g} should mention simple vocab"


def test_10_12_profile_mentions_academic():
    for g in (10, 11, 12):
        profile = get_tone_profile(g)
        combined = (profile["vocabulary"] + " " + profile["directive"]).lower()
        assert "academic" in combined, f"Grade {g} should mention academic register"


def test_grade_5_maps_to_4_6_bucket():
    assert get_tone_profile(5) == get_tone_profile(4)
    assert get_tone_profile(5) == get_tone_profile(6)
    # And differs from adjacent buckets
    assert get_tone_profile(5) != get_tone_profile(3)
    assert get_tone_profile(5) != get_tone_profile(7)


def test_grade_8_maps_to_7_9_bucket():
    assert get_tone_profile(8) == get_tone_profile(7)
    assert get_tone_profile(8) == get_tone_profile(9)
    assert get_tone_profile(8) != get_tone_profile(6)
    assert get_tone_profile(8) != get_tone_profile(10)


def test_none_returns_7_9_default():
    assert get_tone_profile(None) == get_tone_profile(8)


def test_all_profiles_share_same_shape():
    profiles = [
        get_tone_profile(0),
        get_tone_profile(5),
        get_tone_profile(8),
        get_tone_profile(11),
        get_tone_profile(None),
    ]
    shapes = [set(p.keys()) for p in profiles]
    assert all(s == EXPECTED_KEYS for s in shapes)


def test_directive_is_ready_to_concat():
    """Directive should be a self-contained string with clear labeling."""
    for g in (2, 5, 8, 11):
        directive = get_tone_profile(g)["directive"]
        assert "TONE" in directive.upper() or "VOICE" in directive.upper()
        assert len(directive) > 50
