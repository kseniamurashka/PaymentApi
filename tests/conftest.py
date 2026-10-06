from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def client(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")

    from app import main
    from app.database import get_db

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "engine", db_engine)
    monkeypatch.setattr(main, "session_factory", factory)
    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)

    with TestClient(main.app) as test_client:
        yield test_client
