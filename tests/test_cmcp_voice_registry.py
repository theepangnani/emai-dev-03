"""CB-CMCP-001 M1-C 1C-1 — VoiceRegistry tests.

Covers :mod:`app.services.cmcp.voice_registry`:

- All 3 default modules (``arc_voice_v1``, ``professional_v1``,
  ``parent_coach_v1``) load successfully from ``prompt_modules/voice/``.
- :py:meth:`VoiceRegistry.module_hash` returns a stable SHA-256 across
  repeated calls AND changes when the underlying file changes (validated
  via a ``tmp_path`` fixture that monkeypatches ``VOICE_MODULES_DIR``).
- :py:meth:`VoiceRegistry.active_module_id` returns the documented
  defaults for each persona.
- :py:meth:`VoiceRegistry.set_active_module` swaps the active module AND
  the swap is reflected by ``active_module_id``.
- :py:meth:`VoiceRegistry.set_active_module` validates that the new
  module exists — pointing at a missing file raises FileNotFoundError
  AND leaves the active module unchanged (fail closed).
- :py:meth:`VoiceRegistry.load_module` raises ``FileNotFoundError`` for
  unknown module IDs.
- The 3 voice modules are *substantively* different — i.e., not stubs
  pointing at the same content (catches a regression where an editor
  accidentally copy-pasted one module into another).

Issue: #4461
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.cmcp import voice_registry as voice_registry_module
from app.services.cmcp.voice_registry import VOICE_MODULES_DIR, VoiceRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_active_modules():
    """Snapshot + restore ``_ACTIVE_MODULES`` around tests that mutate it.

    ``set_active_module`` mutates module-level state, so without this
    fixture a test that flips ``student`` -> a custom ID would leak that
    state into later tests. We restore the dict in-place (rather than
    rebinding) so the registry's view of the dict stays valid.
    """
    snapshot = dict(voice_registry_module._ACTIVE_MODULES)
    try:
        yield
    finally:
        voice_registry_module._ACTIVE_MODULES.clear()
        voice_registry_module._ACTIVE_MODULES.update(snapshot)


@pytest.fixture
def tmp_voice_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``VOICE_MODULES_DIR`` at a tmp dir for hash-change tests.

    We need a directory we can mutate freely without touching the
    committed voice modules. Monkeypatching the module-level constant
    is enough because :py:meth:`VoiceRegistry.module_path` reads it at
    call time.
    """
    monkeypatch.setattr(voice_registry_module, "VOICE_MODULES_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Default modules + active-module lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_id",
    ["arc_voice_v1", "professional_v1", "parent_coach_v1"],
)
def test_default_modules_load(module_id: str) -> None:
    """All three shipped voice modules exist and have non-trivial content."""
    text = VoiceRegistry.load_module(module_id)
    # >200 chars is a sanity floor — the shortest committed module is
    # several paragraphs long, so anything tiny means the file got
    # truncated to a stub by a bad merge.
    assert len(text) > 200, f"Module {module_id} is suspiciously short ({len(text)} chars)"


def test_default_modules_are_substantively_different() -> None:
    """The three voice modules must have distinct content.

    Catches the regression where someone copy-pastes one module into
    another and silently collapses Arc / professional / parent-coach
    into the same voice. We compare hashes rather than full text so
    the failure message stays short.
    """
    hashes = {
        module_id: VoiceRegistry.module_hash(module_id)
        for module_id in ("arc_voice_v1", "professional_v1", "parent_coach_v1")
    }
    assert len(set(hashes.values())) == 3, (
        f"Voice modules collapsed to duplicate content: {hashes}"
    )


@pytest.mark.parametrize(
    "persona,expected_module",
    [
        ("student", "arc_voice_v1"),
        ("teacher", "professional_v1"),
        ("parent", "parent_coach_v1"),
    ],
)
def test_active_module_id_defaults(persona: str, expected_module: str) -> None:
    assert VoiceRegistry.active_module_id(persona) == expected_module


def test_active_module_id_unknown_persona_raises() -> None:
    with pytest.raises(KeyError, match="Unknown voice persona"):
        VoiceRegistry.active_module_id("admin")


def test_module_path_returns_expected_location() -> None:
    path = VoiceRegistry.module_path("arc_voice_v1")
    assert path == VOICE_MODULES_DIR / "arc_voice_v1.txt"
    assert path.exists()


# ---------------------------------------------------------------------------
# Hash stability + change detection
# ---------------------------------------------------------------------------


def test_module_hash_is_stable_across_calls() -> None:
    """Repeated hash calls on an unchanged file return the same digest."""
    h1 = VoiceRegistry.module_hash("arc_voice_v1")
    h2 = VoiceRegistry.module_hash("arc_voice_v1")
    h3 = VoiceRegistry.module_hash("arc_voice_v1")
    assert h1 == h2 == h3
    # Sanity: it's actually a SHA-256 hex digest (64 chars).
    assert len(h1) == 64
    # And it matches what we'd compute by hand from the file contents.
    expected = hashlib.sha256(
        VoiceRegistry.load_module("arc_voice_v1").encode("utf-8")
    ).hexdigest()
    assert h1 == expected


def test_module_hash_changes_when_file_changes(tmp_voice_dir: Path) -> None:
    """Editing the .txt under VOICE_MODULES_DIR shifts the hash."""
    module_id = "synthetic_voice_v1"
    module_file = tmp_voice_dir / f"{module_id}.txt"

    module_file.write_text("first version of the voice", encoding="utf-8")
    h_before = VoiceRegistry.module_hash(module_id)

    module_file.write_text("second version of the voice — edited", encoding="utf-8")
    h_after = VoiceRegistry.module_hash(module_id)

    assert h_before != h_after, "Hash should change when the underlying file changes"
    # And both are valid SHA-256 digests, not error strings.
    assert len(h_before) == 64
    assert len(h_after) == 64


# ---------------------------------------------------------------------------
# Hot-swap (FR-02.7)
# ---------------------------------------------------------------------------


def test_set_active_module_swaps_module(restore_active_modules) -> None:
    """An admin hot-swap is reflected by the next ``active_module_id`` lookup."""
    # Sanity: starting state is the documented default.
    assert VoiceRegistry.active_module_id("student") == "arc_voice_v1"

    # Swap student to professional_v1 (an existing module, so validation passes).
    VoiceRegistry.set_active_module("student", "professional_v1")

    assert VoiceRegistry.active_module_id("student") == "professional_v1"
    # Other personas are untouched by a single-persona swap.
    assert VoiceRegistry.active_module_id("teacher") == "professional_v1"
    assert VoiceRegistry.active_module_id("parent") == "parent_coach_v1"


def test_set_active_module_to_missing_module_raises_and_leaves_active_unchanged(
    restore_active_modules,
) -> None:
    """Pointing a persona at a nonexistent module fails closed.

    Per the design lock, a bad swap must NOT silently leave a persona
    without a working voice — we want the FileNotFoundError surfaced
    AND the previous active module preserved.
    """
    before = VoiceRegistry.active_module_id("student")

    with pytest.raises(FileNotFoundError):
        VoiceRegistry.set_active_module("student", "does_not_exist_v9")

    assert VoiceRegistry.active_module_id("student") == before


def test_set_active_module_unknown_persona_raises(restore_active_modules) -> None:
    with pytest.raises(KeyError, match="Unknown voice persona"):
        VoiceRegistry.set_active_module("admin", "arc_voice_v1")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_load_module_missing_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        VoiceRegistry.load_module("nonexistent_module_v0")


def test_module_hash_missing_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        VoiceRegistry.module_hash("nonexistent_module_v0")
