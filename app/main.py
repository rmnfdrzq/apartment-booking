"""FastAPI application entrypoint and lifespan management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.database import Base, engine
from app.routers import bookings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Application lifespan context manager for startup and shutdown tasks."""
    # Ensure data directory exists on disk if using SQLite file
    settings.ensure_data_dir()
    # Initialize all database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Dispose engine pools on server termination
    engine.dispose()


app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(bookings.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Check whether the API service is alive and healthy.",
)
def health_check() -> dict[str, str]:
    """Return current API service status."""
    return {
        "status": "ok",
        "app": settings.app_title,
        "version": settings.app_version,
    }
