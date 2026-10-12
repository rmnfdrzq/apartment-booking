"""Tests for database engine and session generator."""

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import engine, get_db


def test_get_db_yields_session_and_closes() -> None:
    """Verify that get_db yields a valid SQLAlchemy Session and cleans it up."""
    db_gen = get_db()
    session = next(db_gen)
    assert isinstance(session, Session)
    # Trigger generator teardown
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_engine_connection() -> None:
    """Verify that the configured engine can connect and execute a basic query."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
