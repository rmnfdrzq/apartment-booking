"""Application configuration settings."""

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    """Application runtime settings and path configuration."""

    def __init__(self) -> None:
        self.base_dir: Path = Path(__file__).resolve().parent.parent
        self.data_dir: Path = self.base_dir / "data"

        # Database URL with fallback to local SQLite file
        default_db_path = (self.data_dir / "apartments.db").as_posix()
        self.database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")

        # Metadata
        self.app_title: str = "Apartment Booking API"
        self.app_description: str = (
            "A headless RESTful API for managing apartments, bookings, "
            "date-range availability, and preventing overlapping reservations."
        )
        self.app_version: str = "1.0.0"

    def ensure_data_dir(self) -> None:
        """Create storage directory on disk if using a file-based SQLite database."""
        if self.database_url.startswith("sqlite") and ":memory:" not in self.database_url:
            self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached singleton provider for application settings."""
    return Settings()
