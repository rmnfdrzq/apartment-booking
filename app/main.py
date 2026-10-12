"""FastAPI application entrypoint and lifespan management."""

import math
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.database import Base, engine
from app.routers import apartments, bookings

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


def _json_safe(value: Any) -> Any:
    """Replace NaN/Infinity (not valid JSON) with strings so error bodies can be serialized."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 for invalid input, including payloads containing NaN or Infinity.

    FastAPI's default handler echoes the rejected input back; with NaN/Infinity that
    echo is not serializable and the client would get a 500 instead of a 422.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": _json_safe(jsonable_encoder(exc.errors()))},
    )


app.include_router(apartments.router)
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
