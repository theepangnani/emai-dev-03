import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure all SQLAlchemy models are loaded before any test runs (#2686)
import app.models  # noqa: F401


@pytest.fixture(scope="session")
def test_db_url(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test_emai.db"
    return f"sqlite:///{db_path}"


@pytest.fixture(scope="session")
def app(test_db_url):
    os.environ["DATABASE_URL"] = test_db_url
    os.environ["TESTING"] = "1"
    os.environ.setdefault("GOOGLE_CLASSROOM_ENABLED", "true")
    os.environ.setdefault("WAITLIST_ENABLED", "false")

    import app.core.config as config
    importlib.reload(config)

    for module_name in list(sys.modules):
        if module_name.startswith("app.models"):
            del sys.modules[module_name]

    import app.db.database as database
    importlib.reload(database)

    import app.models
    importlib.reload(app.models)

    import main as main_module
    importlib.reload(main_module)

    app_instance = main_module.app
    app_instance.router.on_startup.clear()
    app_instance.router.on_shutdown.clear()

    # Disable rate limiting during tests
    app_instance.state.limiter.enabled = False

    database.Base.metadata.create_all(bind=database.engine)
    return app_instance


@pytest.fixture()
def db_session(app):
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


# ── CB-TASKSYNC-001 feature-flag isolation (#4059) ──
#
# The session-scoped DB fixture lets the ``task_sync_enabled`` feature flag
# leak across tests: once a test flips it ON, every subsequent test sees it
# ON unless that test explicitly resets it. Tests in
# ``test_assignments_routes.py`` and ``test_task_sync_jobs.py`` each rely on
# the default-OFF state for their flag-off assertions — they race and flake
# in CI depending on pytest's collection order.
#
# This autouse fixture forces the flag back to OFF before every test. Tests
# that need it ON flip it inside the test body.
#
# Scope: intentionally applied to every test in the suite. The per-test cost
# is a single indexed `SELECT ... WHERE key = 'task_sync_enabled'` — a few
# microseconds — and narrowing to just the two failing files risks re-
# introducing the flake for future tests that rely on flag defaults.
#
# Naming note: `_isolate_task_sync_flag` (not `_reset_task_sync_flag`) to
# avoid shadowing the module-level helper of the same name in
# `tests/test_feature_flags.py`.
@pytest.fixture(autouse=True)
def _isolate_task_sync_flag(app):
    import logging

    from sqlalchemy.exc import SQLAlchemyError

    from app.db.database import SessionLocal

    # Default-OFF flags whose ON state must not leak between tests under
    # the session-scoped DB fixture. Add new entries here when introducing
    # a new default-OFF flag that any test toggles ON.
    default_off_keys = (
        "task_sync_enabled",
        "dci_v1_enabled",  # CB-DCI-001 M0-3 (#4141)
    )
    # #4542 — default-ON flags whose OFF state must not leak. PR #4448 added
    # tests that flip ``parent.unified_digest_v2`` to False to pin the legacy
    # path; without this reset, the polluted (enabled=False, variant="on_100")
    # state survives into ``test_feature_flags`` which asserts the seeded-
    # default ON contract. The seed-time auto-promote at
    # ``feature_seed_service.py:159`` only fires when BOTH variant=="off" AND
    # enabled is False, so it doesn't catch the leak.
    default_on_keys = (
        "parent.unified_digest_v2",
    )

    db = SessionLocal()
    try:
        from app.models.feature_flag import FeatureFlag

        flags = (
            db.query(FeatureFlag)
            .filter(FeatureFlag.key.in_(default_off_keys + default_on_keys))
            .all()
        )
        dirty = False
        for flag in flags:
            if flag.key in default_off_keys and flag.enabled:
                flag.enabled = False
                dirty = True
            elif flag.key in default_on_keys and not flag.enabled:
                flag.enabled = True
                # Restore the canonical seeded variant alongside enabled —
                # the polluting tests only flip ``enabled`` (not ``variant``),
                # and the auto-promote on seed_features() refuses rows whose
                # variant has drifted from the original "off" sentinel.
                flag.variant = "on_100"
                dirty = True
        if dirty:
            db.commit()
        # When a row is missing (earliest startup-smoke tests, or a test
        # that hasn't yet triggered seed_features) there is nothing to
        # reset — the default-state contract is already satisfied.
    except SQLAlchemyError:
        # Surface real DB errors (including missing-table OperationalError)
        # at WARNING so a genuine failure in the reset path is visible in
        # CI, rather than manifesting later as a mysterious cross-test
        # flake.
        db.rollback()
        logging.getLogger(__name__).warning(
            "feature-flag reset failed", exc_info=True
        )
    finally:
        db.close()
    yield


# ── Shared auth helpers (used by all test files) ──

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


# ── CB-DCI-001 shared seed factory (#4275) ──
#
# Promoted from `tests/test_dci_checkin_api.py` so any DCI test file can seed
# a check-in row plus its classification event without duplicating the
# boilerplate. Usage:
#
#     def test_something(seed_checkin_with_classification, db_session, kid,
#                        linked_parent):
#         checkin_id, ce_id = seed_checkin_with_classification(
#             kid_id=kid.id, parent_id=linked_parent.id, subject="English"
#         )
#         ...
#
# Returns a callable so a single test can seed multiple rows. The factory
# binds to the test's `db_session` so all writes participate in the same
# session and are visible to subsequent queries in the same test.
@pytest.fixture()
def seed_checkin_with_classification(db_session):
    """Factory fixture: create a daily_checkins row + one classification_events row.

    The returned callable accepts keyword arguments::

        kid_id    -- Student.id (required)
        parent_id -- User.id of the linked parent (required)
        subject   -- canonical subject string, default "Math"

    and returns ``(checkin_id, classification_id)``.
    """

    def _seed(*, kid_id, parent_id, subject="Math"):
        from app.models.dci import ClassificationEvent, DailyCheckin

        c = DailyCheckin(
            kid_id=kid_id,
            parent_id=parent_id,
            photo_uris=[],
            text_content="hello",
            source="kid_web",
        )
        db_session.add(c)
        db_session.flush()
        ce = ClassificationEvent(
            checkin_id=c.id,
            artifact_type="text",
            subject=subject,
            confidence=0.9,
        )
        db_session.add(ce)
        db_session.commit()
        db_session.refresh(c)
        db_session.refresh(ce)
        return c.id, ce.id

    return _seed
