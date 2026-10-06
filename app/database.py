from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

session_factory = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    with session_factory() as session:
        yield session
