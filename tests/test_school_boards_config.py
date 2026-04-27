"""Tests for app/core/school_boards.py — pinning the shape of the data module."""
from app.core.school_boards import KNOWN_SCHOOL_BOARD_DOMAINS


def test_known_school_board_domains_is_frozenset():
    """Frozenset for O(1) membership lookup AND immutability."""
    assert isinstance(KNOWN_SCHOOL_BOARD_DOMAINS, frozenset)


def test_known_school_board_domains_all_lowercase():
    """Apex-domain comparison is lowercase — pre-validate at the data layer."""
    for d in KNOWN_SCHOOL_BOARD_DOMAINS:
        assert d == d.lower(), f"domain {d!r} not lowercase"


def test_known_school_board_domains_no_protocol_or_port():
    """Apex domain only — no scheme, no port, no path."""
    for d in KNOWN_SCHOOL_BOARD_DOMAINS:
        assert "/" not in d
        assert ":" not in d
        assert "@" not in d


def test_known_school_board_domains_initial_set():
    """Pin the initial 9-entry set so accidental deletions surface in review."""
    expected = {
        "ocdsb.ca",
        "tdsb.on.ca",
        "peelschools.org",
        "dsbn.org",
        "yrdsb.ca",
        "dpcdsb.org",
        "hwdsb.on.ca",
        "wrdsb.ca",
        "sd35.bc.ca",
    }
    assert KNOWN_SCHOOL_BOARD_DOMAINS == frozenset(expected)
