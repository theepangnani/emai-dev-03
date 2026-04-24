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
# that need it ON flip it inside the test body. The fixture is defensive —
# if the ``feature_flags`` table does not yet exist (earliest startup-smoke
# tests) it silently no-ops.
@pytest.fixture(autouse=True)
def _reset_task_sync_flag(app):
    import logging

    from sqlalchemy.exc import SQLAlchemyError

    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        from app.models.feature_flag import FeatureFlag

        flag = (
            db.query(FeatureFlag)
            .filter(FeatureFlag.key == "task_sync_enabled")
            .first()
        )
        if flag is not None and flag.enabled:
            flag.enabled = False
            db.commit()
    except SQLAlchemyError:
        # Surface real DB errors at WARNING so a genuine failure in the
        # reset path is visible in CI, rather than manifesting later as a
        # mysterious cross-test flake.
        db.rollback()
        logging.getLogger(__name__).warning(
            "task_sync_enabled reset failed", exc_info=True
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
