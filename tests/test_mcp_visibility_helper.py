"""Unit tests for ``app.mcp.tools._visibility`` (#4567).

Covers the shared ``resolve_caller_board_id`` helper that 2B-2
(get_artifact) and 2B-3 (list_catalog) consume. Behavior must be
byte-identical to the pre-extraction local copies.

Imports live inside the test bodies (not at module top) because the
session-scoped ``app`` fixture in ``conftest.py`` reloads ``app.models``
on first use; importing ``app.*`` modules at collection time can prime
sys.modules with stale references that survive the reload and trip up
downstream test files (e.g. ``test_mcp_routes.py``) that share the
same conftest. See conftest's "ensure all SQLAlchemy models are loaded"
comment for context.
"""


def test_resolve_caller_board_id_missing_attr() -> None:
    from app.mcp.tools._visibility import resolve_caller_board_id

    class DummyUser:
        pass

    assert resolve_caller_board_id(DummyUser()) is None


def test_resolve_caller_board_id_present() -> None:
    from app.mcp.tools._visibility import resolve_caller_board_id

    class DummyUser:
        board_id = "yrdsb"

    assert resolve_caller_board_id(DummyUser()) == "yrdsb"
