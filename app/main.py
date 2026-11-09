"""FastAPI application entrypoint and lifespan management."""

import math
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

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


tags_metadata = [
    {
        "name": "Apartments",
        "description": "Apartment listing catalog (US1) and date-range availability search (US3).",
    },
    {
        "name": "Bookings",
        "description": "Guest stay reservations (US2) and overlap conflict prevention engine (US4).",
    },
    {
        "name": "System",
        "description": "System health and operational monitoring.",
    },
]

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    openapi_tags=tags_metadata,
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

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False, response_model=None)
def root() -> Response:
    """Serve the single-page web application frontend, or fallback to API docs."""
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file), media_type="text/html")
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
