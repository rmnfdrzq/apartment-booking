"""Database connection, engine, PRAGMA configuration, and session management."""

import sqlite3
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

connect_args: dict[str, Any] = {}
poolclass = None

if settings.database_url.startswith("sqlite"):
    # Allow multi-threading and add 30-second busy timeout for write concurrency
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30.0
    if ":memory:" in settings.database_url:
        poolclass = StaticPool

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    poolclass=poolclass if poolclass else None,
    echo=False,
)


@event.listens_for(Engine, "connect")
def configure_sqlite_connection(dbapi_connection: Any, connection_record: Any) -> None:
    """Enforce SQLite PRAGMAs: foreign keys, WAL journal mode, and synchronous normal."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        # 1. Strictly enforce foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")
        # 2. Enable Write-Ahead Logging (WAL) for disk databases to prevent lock contention
        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
        except sqlite3.OperationalError:
            # In-memory databases do not support WAL mode
            pass
        cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Dependency injection generator providing a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
