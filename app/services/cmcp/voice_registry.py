"""CB-CMCP-001 M1-C 1C-1 — Versioned voice-module registry (FR-02.7).

Maps a *target persona* (``student`` / ``teacher`` / ``parent``) to an
*active voice module ID* (e.g., ``arc_voice_v1``). Each module is a plain
``.txt`` file under ``prompt_modules/voice/`` containing a voice-overlay
prompt block; downstream content-generation services load the active module
for the persona they're rendering for and prepend it to their system prompt.

Why a registry (not just a constant):
- **Hot-swap without code deploy** — admins can flip the active module ID
  for a persona at runtime (FR-02.7). In this stripe the swap mutates an
  in-memory dict; persistence to DB / config is a Wave 3 concern.
- **Versioning** — adding a new voice variant is a drop-a-new-``.txt`` +
  ``set_active_module(...)`` operation. Old IDs keep working until they're
  explicitly retired, so artifacts can record the exact module they were
  generated against.
- **Hash-stamping** — :py:meth:`module_hash` returns the SHA-256 of the
  module's contents so artifacts generated in 1C-2 (wave 2) can stamp the
  voice version they used and the wave-3 audit job can flag
  voice-inconsistent artifacts.

Issue: #4461
Epic: #4351
Plan: docs/design/CB-CMCP-001-batch-implementation-plan.md §7 M1-C 1C-1
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# ``app/services/cmcp/voice_registry.py`` -> repo root via four ``parent`` hops:
#   parent[0] = cmcp/, parent[1] = services/, parent[2] = app/, parent[3] = repo root.
# Pinning to ``Path(__file__)`` (rather than ``Path.cwd()``) makes the
# registry independent of where the process was launched from — important
# for tests, Cloud Run, and ``python -m`` invocations alike.
VOICE_MODULES_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent.parent / "prompt_modules" / "voice"
)

# Active module ID per target persona. Mutable at runtime via
# :py:meth:`VoiceRegistry.set_active_module` (FR-02.7 hot-swap).
#
# Persistence is intentionally out of scope for stripe 1C-1: a process
# restart resets to these defaults. Wave 3 (1C-3) backs this with a DB
# table + admin endpoint so the swap survives restarts.
_ACTIVE_MODULES: dict[str, str] = {
    "student": "arc_voice_v1",
    "teacher": "professional_v1",
    "parent": "parent_coach_v1",
}


class VoiceRegistry:
    """Static-method registry for versioned voice-overlay prompt modules.

    All methods are stateless apart from the module-level ``_ACTIVE_MODULES``
    dict that :py:meth:`set_active_module` mutates. We use static methods
    (rather than free functions) so callers have a single import surface
    (``from app.services.cmcp.voice_registry import VoiceRegistry``) and so
    the future DB-backed implementation can swap to instance methods without
    breaking call sites.

    Concurrency: in stripe 1C-1 the registry is in-memory only and reads /
    writes go through the GIL-protected dict, so a single-process uvicorn
    deployment is safe without an explicit lock. Wave 3 (1C-3) backs the
    active-module map with a DB row + admin endpoint; that implementation
    will need its own row-level locking.
    """

    # ------------------------------------------------------------------
    # Active-module lookup + hot-swap
    # ------------------------------------------------------------------
    @staticmethod
    def active_module_id(persona: str) -> str:
        """Return the active voice-module ID for ``persona``.

        Args:
            persona: One of ``"student"``, ``"teacher"``, ``"parent"``.

        Raises:
            KeyError: if ``persona`` is not a recognised target persona.
        """
        if persona not in _ACTIVE_MODULES:
            raise KeyError(
                f"Unknown voice persona {persona!r}; "
                f"expected one of {sorted(_ACTIVE_MODULES.keys())}"
            )
        return _ACTIVE_MODULES[persona]

    @staticmethod
    def set_active_module(persona: str, module_id: str) -> None:
        """Hot-swap the active voice module for ``persona`` (FR-02.7).

        The swap is validated — we ``load_module`` the new ID first so a
        typo'd module can't silently disable a persona's voice on the next
        artifact generation. Validation failures surface as
        :class:`FileNotFoundError` and the active module is left unchanged.

        Args:
            persona: Target persona to update.
            module_id: New voice-module ID (must correspond to an existing
                ``prompt_modules/voice/<module_id>.txt`` file).

        Raises:
            KeyError: if ``persona`` is not a recognised target persona.
            FileNotFoundError: if the module file does not exist (active
                module is **not** changed in this case — fail closed so a
                bad swap can't silently leave the persona without a voice).
        """
        if persona not in _ACTIVE_MODULES:
            raise KeyError(
                f"Unknown voice persona {persona!r}; "
                f"expected one of {sorted(_ACTIVE_MODULES.keys())}"
            )
        # Validate before mutating — a swap that points at a nonexistent file
        # would silently break the next artifact for this persona.
        VoiceRegistry.load_module(module_id)
        _ACTIVE_MODULES[persona] = module_id

    # ------------------------------------------------------------------
    # Module IO
    # ------------------------------------------------------------------
    @staticmethod
    def module_path(module_id: str) -> Path:
        """Return the filesystem path for ``module_id``.

        The path is *not* checked for existence — callers that need to know
        whether the module file is on disk should call :py:meth:`load_module`
        (which surfaces :class:`FileNotFoundError`) or check
        ``module_path(...).exists()`` themselves.
        """
        return VOICE_MODULES_DIR / f"{module_id}.txt"

    @staticmethod
    def load_module(module_id: str) -> str:
        """Read the voice-module ``.txt`` file and return its contents.

        Args:
            module_id: Voice-module identifier (e.g., ``arc_voice_v1``).

        Returns:
            The full text of the module, exactly as stored on disk
            (no trimming, no normalisation — the bytes that get hashed
            by :py:meth:`module_hash` are the bytes returned here).

        Raises:
            FileNotFoundError: if no ``<module_id>.txt`` exists under
                :py:data:`VOICE_MODULES_DIR`.
        """
        path = VoiceRegistry.module_path(module_id)
        # ``Path.read_text`` raises FileNotFoundError natively on missing
        # files, so we don't need an existence pre-check. UTF-8 is explicit
        # so Windows + Linux callers see identical bytes for the hash.
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Hash stamping (consumed by 1C-2 wave 2)
    # ------------------------------------------------------------------
    @staticmethod
    def module_hash(module_id: str) -> str:
        """Return the SHA-256 hex digest of the module's contents.

        Wave 2 (1C-2) stamps this hash on every generated artifact so the
        wave-3 audit job can flag artifacts whose voice no longer matches
        the active module.

        The hash is computed from the **bytes returned by
        :py:meth:`load_module`** (UTF-8 encoded) so platform line-ending
        quirks don't shift the hash across dev/CI/prod. Editing the
        underlying ``.txt`` changes the hash; that's by design — a voice
        edit ships as a new module ID, not an in-place rewrite of an
        existing one.

        Raises:
            FileNotFoundError: if the module file does not exist.
        """
        text = VoiceRegistry.load_module(module_id)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
