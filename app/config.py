"""Application configuration settings."""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists for SQLite storage
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR / 'apartments.db'}",
)

# Application Metadata
APP_TITLE: str = "Apartment Booking API"
APP_DESCRIPTION: str = (
    "A headless RESTful API for managing apartments, bookings, "
    "date-range availability, and preventing overlapping reservations."
)
APP_VERSION: str = "1.0.0"
