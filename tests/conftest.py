import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

PG_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/emai_test"


def pytest_addoption(parser):
    parser.addoption(
        "--pg",
        action="store_true",
        default=False,
        help="Run tests against a real PostgreSQL database instead of SQLite",
    )


@pytest.fixture(scope="session")
def test_db_url(request, tmp_path_factory):
    if request.config.getoption("--pg"):
        return PG_URL
    db_path = tmp_path_factory.mktemp("db") / "test_emai.db"
    return f"sqlite:///{db_path}"


@pytest.fixture(scope="session")
def app(test_db_url):
    os.environ["DATABASE_URL"] = test_db_url

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


# ── Shared auth helpers (used by all test files) ──

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}
