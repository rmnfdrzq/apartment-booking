"""Tests for database engine, SQLite PRAGMA configuration, and session generator."""

import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import engine, get_db


def test_get_db_yields_session_and_closes() -> None:
    """Verify that get_db yields a valid SQLAlchemy Session and cleans it up."""
    db_gen = get_db()
    session = next(db_gen)
    assert isinstance(session, Session)
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_engine_connection_and_foreign_keys_pragma() -> None:
    """Verify that the engine connects, executes queries, and enforces foreign keys."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

        fk_status = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk_status == 1


def test_settings_ensure_data_dir(tmp_path: Path) -> None:
    """Verify that Settings.ensure_data_dir creates target directory only when using disk file."""
    # Test with disk file
    disk_db = tmp_path / "subdir" / "test.db"
    settings = Settings()
    settings.data_dir = tmp_path / "subdir"
    settings.database_url = f"sqlite:///{disk_db.as_posix()}"
    settings.ensure_data_dir()
    assert (tmp_path / "subdir").exists()

    # Test with in-memory database (should not create folder)
    non_existent = tmp_path / "memory_subdir"
    settings.data_dir = non_existent
    settings.database_url = "sqlite:///:memory:"
    settings.ensure_data_dir()
    assert not non_existent.exists()
