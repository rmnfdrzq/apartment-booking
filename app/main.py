"""FastAPI application entrypoint and lifespan management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.config import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Application lifespan context manager for startup and shutdown tasks."""
    # Startup: Ensure all database tables exist
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Clean up resources if needed
    engine.dispose()


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


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
        "app": APP_TITLE,
        "version": APP_VERSION,
    }
