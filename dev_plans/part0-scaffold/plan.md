# Implementation Plan: Part 0 — Project Scaffold & Test Harness

**Document Path:** `/dev_plans/part0-scaffold/plan.md`  
**Phase:** `feature/part0-scaffold`  
**Target Milestone:** Checkpoint 1 Foundation  

---

## 1. Goal

Establish a production-grade, reproducible, and minimal shared architectural foundation for the Apartment Booking backend. By the end of this phase, the project will have:
1. An isolated Python runtime environment with pinned dependencies.
2. A working persistent SQLite database engine with declarative ORM mapping.
3. An initialized FastAPI application exposing automated OpenAPI/Swagger documentation (`/docs`) and a `/health` endpoint.
4. An automated test harness with `pytest` that executes against an in-memory SQLite database, guaranteeing zero test pollution on the persistent database file.
5. 100% green automated smoke tests verifying the full server-to-database lifecycle.

---

## 2. Locked Decisions

### Decision 1: Framework — FastAPI with Uvicorn
- **What:** Use [FastAPI](https://fastapi.tiangolo.com/) as the HTTP framework and [Uvicorn](https://www.uvicorn.org/) as the ASGI server.
- **Why:** 
  - Fulfills **Shared Project Constraint 1** (*Documented API callable without GUI*) automatically via interactive Swagger UI (`/docs`) and OpenAPI JSON.
  - Native integration with Pydantic v2 ensures strict request/response data validation and type safety.
  - Asynchronous, lightweight, and standard in modern Python service development.

### Decision 2: Persistence Engine — SQLite with SQLAlchemy 2.0 ORM
- **What:** Use file-based SQLite stored at `./data/apartments.db` managed via SQLAlchemy 2.0.
- **Why:**
  - Fulfills **Shared Project Constraint 2** (*Persistent data storage surviving application restarts*).
  - Requires **zero external infrastructure** (no Docker daemon or background database service like PostgreSQL needed for evaluation).
  - SQLite is bundled natively in Python's standard library.
  - Setting `connect_args={"check_same_thread": False}` allows safe multi-threaded concurrency across FastAPI worker threads.

### Decision 3: Session Management — Dependency Injection with Generator Lifecycle
- **What:** Provide database sessions to FastAPI routers via a `get_db()` dependency generator using `yield` and `finally: db.close()`.
- **Why:**
  - Guarantees deterministic session opening and closing per request.
  - Prevents connection leaks and file lock retention in SQLite.
  - Allows seamless overriding in tests via FastAPI's `app.dependency_overrides`.

### Decision 4: Application Lifecycle — Modern `lifespan` Context Manager
- **What:** Use FastAPI's async `lifespan` context manager instead of deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")`.
- **Why:**
  - `on_event` is deprecated in Starlette/FastAPI.
  - Ensures database table initialization (`Base.metadata.create_all(bind=engine)`) executes cleanly before accepting HTTP traffic.

### Decision 5: Test Architecture — Pytest with In-Memory SQLite and `StaticPool`
- **What:** Use `pytest` with `httpx.AsyncClient` / `TestClient` wired to `sqlite:///:memory:` with SQLAlchemy's `StaticPool`.
- **Why:**
  - Fast test execution (< 1 second).
  - Guarantees **total isolation**: running tests will never read from, write to, or corrupt the persistent `./data/apartments.db` file used by the application during manual verification.
  - Each test runs against clean, ephemeral schema tables.

### Decision 6: Project Layout — Modular Layered Separation
- **What:** Maintain separation of concerns:
  - `app/config.py`: Environment settings and constants.
  - `app/database.py`: Engine, session maker, declarative base, and `get_db` dependency.
  - `app/main.py`: Application instantiation, lifespan, router inclusions, and health check.
  - `tests/conftest.py`: Shared test fixtures and dependency overrides.
- **Why:**
  - Keeps database configuration decoupled from routing logic.
  - Allows multiple developers to work on routers and services independently without merge conflicts.

---

## 3. What Exists Today

As of this planning phase:
- **Git Repository:** Initialized on `main` branch, synced with remote origin at `https://github.com/rmnfdrzq/apartment-booking`.
- **Documentation:** 
  - `README.md` (comprehensive project specification, user stories, cURL examples).
  - `dev_plans/roadmap.md` (concurrency and dependency roadmap for Parts 0 to 4).
  - `.gitignore` (ignores `.venv/`, `__pycache__/`, `*.db`, test artifacts).
  - `data/.gitkeep` (tracked placeholder ensuring the `data/` folder exists).
- **Application Code:** None. No Python files or virtual environment exist yet in the working directory.

---

## 4. Verified and Measured Facts

The following facts have been measured and verified directly on the host machine:

| Metric / Attribute | Measured Value | Verification Source |
| :--- | :--- | :--- |
| **Operating System** | macOS (Darwin 24.3.0, arm64) | System environment |
| **Primary Python Runtime** | Python `3.14.6` | `/opt/homebrew/bin/python3 --version` |
| **Secondary Python Runtime** | Python `3.13` available | `/opt/homebrew/bin/python3.13` |
| **Built-in SQLite Version** | SQLite `3.53.4` | `python3 -c "import sqlite3; print(...)"` |
| **Default Port 8000** | Available (no processes listening) | `lsof -i :8000` |
| **Git Working Tree** | Clean, 0 uncommitted changes | `git status` |
| **Remote Sync** | Branch `main` up to date with `origin/main` | `git status` / `git log` |

---

## 5. Risks and Mitigations

### Risk 1: Python 3.14 Pre-compiled Binary Wheel Availability
- **Context:** Python 3.14 is a very recent release. Certain third-party libraries requiring C-extensions might lack pre-compiled binary wheels or fail to build.
- **Severity:** Medium.
- **Mitigation:** Pin standard modern versions of `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, and `pytest`. If compilation errors occur during `pip install`, immediately pin to `/opt/homebrew/bin/python3.13` which has universal wheel support.

### Risk 2: SQLite Concurrency & Thread Sharing in FastAPI
- **Context:** SQLite disallows sharing connection objects across different threads by default (`SQLite objects created in a thread can only be used in that thread`). FastAPI handles requests across thread pools.
- **Severity:** High (would cause runtime HTTP 500 errors).
- **Mitigation:** Explicitly configure the SQLAlchemy engine with `connect_args={"check_same_thread": False}` in `app/database.py`.

### Risk 3: Test Runs Mutating or Corrupting Persistent Data
- **Context:** If tests connect to `./data/apartments.db`, running `pytest` will delete or tamper with demo records created during manual cURL testing.
- **Severity:** High.
- **Mitigation:** In `tests/conftest.py`, create an isolated test engine pointing to `sqlite:///:memory:` with `StaticPool` and override FastAPI's `get_db` dependency via `app.dependency_overrides[get_db]`.

### Risk 4: Connection Leaks & File Locking
- **Context:** Unclosed database sessions can lock the SQLite file on disk.
- **Severity:** Medium.
- **Mitigation:** Implement `get_db()` with a strict `try ... yield ... finally: db.close()` pattern.

---

## 6. High-Level Implementation Stages

The scaffold phase will be implemented across **5 distinct stages**:

### Stage 1: Dependency Management & Virtual Environment Setup
- Create `requirements.txt` containing pinned core packages:
  - `fastapi>=0.115.0`
  - `uvicorn[standard]>=0.32.0`
  - `sqlalchemy>=2.0.35`
  - `pydantic>=2.9.0`
  - `pytest>=8.3.0`
  - `pytest-cov>=5.0.0`
  - `httpx>=0.27.0`
- Create and activate a local virtual environment (`.venv`).
- Install dependencies via `pip` and verify clean installation without build errors.

### Stage 2: Configuration & Persistence Engine
- Create `app/config.py`:
  - Define `Settings` class (or module constants) holding `DATABASE_URL = "sqlite:///./data/apartments.db"`, API title, and version.
- Create `app/database.py`:
  - Initialize the persistent SQLite SQLAlchemy `engine` with `check_same_thread=False`.
  - Configure `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
  - Declare `Base = declarative_base()`.
  - Implement the `get_db()` session generator function.

### Stage 3: FastAPI Application Shell & Lifespan Setup
- Create `app/main.py`:
  - Define an async `lifespan(app: FastAPI)` context manager that triggers `Base.metadata.create_all(bind=engine)` upon server startup.
  - Instantiate `app = FastAPI(title="Apartment Booking API", lifespan=lifespan)`.
  - Add a lightweight `GET /health` endpoint returning `{"status": "ok", "app": "Apartment Booking API"}`.

### Stage 4: Test Harness & Automated Fixtures
- Create `tests/conftest.py`:
  - Configure an in-memory SQLite engine (`sqlite:///:memory:`) using `StaticPool` to preserve schema across connections in a single test process.
  - Create a test session fixture that binds tables before each test and drops them on teardown.
  - Override `get_db` in `app.dependency_overrides`.
  - Expose a `client` fixture using Starlette's `TestClient(app)`.
- Create `tests/test_health.py`:
  - Write an automated test calling `GET /health`.
  - Assert HTTP `200 OK` and payload validation.

### Stage 5: Verification & Checkpoint 1 Readiness
- Execute `pytest -v` to ensure 100% passing test status.
- Start `uvicorn app.main:app` and verify the `/health` endpoint and the `/docs` Swagger UI.
- Verify that `./data/apartments.db` is created and managed cleanly.
- Commit all scaffold files with descriptive conventional commit messages.
