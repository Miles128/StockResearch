"""Pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Force test settings before imports
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USE_MOCK_LLM"] = "true"
os.environ["USE_MOCK_MARKET_DATA"] = "true"

from stockresearch.api.app import create_app  # noqa: E402
from stockresearch.db.models import Base  # noqa: E402
from stockresearch.db.session import get_db  # noqa: E402
from stockresearch.services.cache import CacheService  # noqa: E402


@pytest.fixture()
def db_session() -> object:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session: object) -> TestClient:
    app = create_app()

    def override_get_db() -> object:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    cache = CacheService()
    cache.clear_memory()
    return TestClient(app)
