"""Tests for app.core.bot_protection.is_bot_submission."""

from app.core.bot_protection import is_bot_submission


def test_honeypot_filled_returns_true():
    """Non-empty honeypot field indicates a bot."""
    assert is_bot_submission(honeypot_value="spam") is True


def test_honeypot_empty_passes():
    """Empty honeypot alone does not flag as bot."""
    assert is_bot_submission(honeypot_value="") is False


def test_elapsed_below_min_returns_true():
    """Elapsed time below minimum threshold indicates a bot."""
    assert is_bot_submission(elapsed_seconds=0.5, min_seconds=3.0) is True


def test_elapsed_above_min_returns_false():
    """Elapsed time above minimum threshold is not a bot."""
    assert is_bot_submission(elapsed_seconds=5.0, min_seconds=3.0) is False


def test_elapsed_exactly_min_returns_false():
    """Elapsed time exactly at minimum threshold is not a bot (boundary)."""
    assert is_bot_submission(elapsed_seconds=3.0, min_seconds=3.0) is False


def test_negative_elapsed_returns_true():
    """Negative elapsed time indicates tampered/suspicious submission."""
    assert is_bot_submission(elapsed_seconds=-1.0) is True


def test_excessive_elapsed_returns_true():
    """Elapsed time exceeding 86400 seconds indicates tampered submission."""
    assert is_bot_submission(elapsed_seconds=100000.0) is True


def test_elapsed_none_skips_timing_check():
    """None elapsed_seconds skips the timing check entirely."""
    assert is_bot_submission(elapsed_seconds=None) is False


def test_both_honeypot_and_timing_fail():
    """When both honeypot and timing fail, honeypot is caught first."""
    assert is_bot_submission(honeypot_value="filled", elapsed_seconds=0.1) is True


def test_clean_submission():
    """Empty honeypot with valid elapsed time is not a bot."""
    assert is_bot_submission(honeypot_value="", elapsed_seconds=10.0) is False
