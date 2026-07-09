"""Pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Force test settings before imports
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USE_MOCK_LLM"] = "true"
os.environ["USE_MOCK_MARKET_DATA"] = "true"

from stockresearch.api.app import create_app  # noqa: E402
from stockresearch.db.models import Base  # noqa: E402
from stockresearch.db import session as db_session_module  # noqa: E402
from stockresearch.db.session import (  # noqa: E402
    _migration_002_user_preferences,
    _migration_003_provider_cache,
    get_db,
)
from stockresearch.services.cache import CacheService  # noqa: E402


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="set RUN_LIVE_TESTS=1 to test real internet providers")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def _reset_test_database() -> None:
    engine = db_session_module.engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migration_002_user_preferences(conn)
        _migration_003_provider_cache(conn)
        conn.execute(text("DELETE FROM provider_cache"))


def _clear_provider_cache() -> None:
    engine = db_session_module.engine
    with engine.begin() as conn:
        try:
            conn.execute(text("DELETE FROM provider_cache"))
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _isolated_provider_cache() -> None:
    _clear_provider_cache()
    yield
    _clear_provider_cache()


@pytest.fixture(autouse=True)
def _clear_news_ingest_jobs() -> None:
    from stockresearch.services.news_ingest_jobs import clear_jobs

    clear_jobs()
    yield
    clear_jobs()


@pytest.fixture()
def db_session() -> object:
    _reset_test_database()
    session = db_session_module.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        _clear_provider_cache()
        Base.metadata.drop_all(bind=db_session_module.engine)


@pytest.fixture()
def client(db_session: object) -> TestClient:
    app = create_app()

    def override_get_db() -> object:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    cache = CacheService()
    cache.clear_memory()
    return TestClient(app)
