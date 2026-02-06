import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_db_url(tmp_path_factory):
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
