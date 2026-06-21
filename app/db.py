"""Database engine, session factory, and declarative base (SQLite via SQLAlchemy)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if they do not exist. Importing models registers them."""
    from app import models  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session and closes it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
