# Implementation Plan: Checkpoint 2 — Web Application UI, OpenAPI Enrichment & Docker Compose Persistent Deployment

**Document Path:** `/dev_plans/checkpoint-2-web-docker/plan.md`  
**Phase:** `checkpoint-2-web-docker`  
**Milestone:** Checkpoint 2 Delivery (Web UI Forms, OpenAPI Specification, Docker Volumes & Docker Compose)  

---

## 1. Goal

Transform the existing headless backend into a **complete, interactive web application** that allows users to complete all rental workflows through web forms without command-line input, enriched with comprehensive OpenAPI documentation, and packaged for reproducible deployment with **persistent Docker volumes** and **Docker Compose**.

By the end of this implementation:
1. **Interactive Web Application:** A clean, responsive web interface served directly at `http://localhost:8000` with dedicated HTML forms for all workflows:
   - **Apartment Catalog:** Listing view, "Add Apartment" form, "Edit Apartment" form, and "Delete Apartment" action with active-booking protection alerts.
   - **Availability Search:** Date-picker search form returning available apartments with one-click "Book Now" actions.
   - **Booking Creation:** Interactive reservation form with real-time night calculation and total price preview before submission.
   - **Booking Management:** Active bookings dashboard, date update / apartment transfer form, and one-click soft cancellation releasing dates.
   - **User-Friendly Error Handling:** Toast/alert notifications displaying human-readable explanations on `409 Conflict` (overlap/deletion protection), `400 Bad Request`, and `422 Unprocessable Entity` without exposing raw JSON to the user.
2. **Resource-Oriented REST API & OpenAPI Enrichment:**
   - Verify and enrich the existing REST API with explicit parameter descriptions, realistic request/response payload examples, and structured error schemas (400, 404, 409, 422) in the OpenAPI 3.1 specification at `/openapi.json` and `/docs`.
3. **Unit & Integration Tests:**
   - Add automated tests (`tests/test_web_ui.py`) covering UI routes, form rendering, static asset serving, and web interaction rules.
4. **Docker Containerization & Persistent Volumes:**
   - Production-ready `Dockerfile` based on `python:3.12-slim`.
   - `docker-compose.yml` orchestrating the application with a dedicated named volume (`apartment_data:/app/data`) guaranteeing that SQLite database records survive container restarts and `docker compose down` / `up` cycles.
5. **Fresh Checkout Verification & Documentation:**
   - Update `README.md` with unambiguous, copy-pasteable commands for starting the application, stopping it, running tests inside the container, and accessing the web address from a fresh checkout.

---

## 2. Locked Decisions

### Decision 1: Lightweight, Dependency-Free Frontend (Vanilla HTML5 / Modern CSS / Fetch API)
- **What:** Serve a clean single-page dashboard with tabbed workflows and modal forms using semantic HTML5, modern vanilla CSS (responsive grid/cards, clean typography), and asynchronous JavaScript (`fetch`). Files will be organized under `app/static/` and served via FastAPI's `StaticFiles`.
- **Why:**
  - **Zero extra build dependencies:** Avoids Node.js, npm, Webpack, or heavy frontend toolchains. Keeps Docker images small (< 180MB) and build times lightning-fast.
  - **Decoupled API consumer:** The UI acts as a pure consumer of the existing REST API (`/apartments`, `/apartments/search`, `/bookings`, etc.), sending and receiving JSON.
  - **Preserves existing backend:** All 154 existing backend tests remain 100% valid and unchanged.
  - **Better user experience:** Modals and dynamic updates allow real-time stay duration and price calculations without full-page reloads.

### Decision 2: Root Path (`/`) Serves the Web Application; `/docs` Remains OpenAPI
- **What:** Update `GET /` in `app/main.py` to serve the interactive web application (`index.html`). Keep `/docs` for interactive Swagger UI, `/redoc` for ReDoc, and `/openapi.json` for raw OpenAPI 3.1.
- **Why:**
  - Directly fulfills the requirement: *"turn your scripts into a web application with forms for the existing workflows, so users can complete them without command-line input"*.
  - A first-time visitor opening `http://localhost:8000` immediately lands on the web interface, while developers and evaluators can still visit `http://localhost:8000/docs`.

### Decision 3: Enriched OpenAPI Documentation with Explicit Examples and Error Models
- **What:** Add `examples` to Pydantic schemas and add explicit `responses={...}` models on FastAPI router decorators for `400 Bad Request`, `404 Not Found`, and `409 Conflict`.
- **Why:**
  - The requirement specifies: *"document its endpoints, parameters, examples, and errors in an OpenAPI specification"*.
  - Enhancing the OpenAPI metadata ensures the interactive Swagger UI displays exact payload structures and error scenarios.

### Decision 4: Base Image `python:3.12-slim` for Docker
- **What:** Use `python:3.12-slim` in `Dockerfile`.
- **Why:**
  - Debian-based slim image provides pre-compiled binary wheels for all dependencies (`pydantic-core`, `uvicorn`, `sqlalchemy`, `pytest`), avoiding the need for heavy build tools (`gcc`, `g++`, `make`) in the runtime image.
  - Highly secure, predictable, and standard in production container deployments.

### Decision 5: Named Volume `apartment_data:/app/data` for Database Persistence
- **What:** In `docker-compose.yml`, mount a named volume `apartment_data` to `/app/data`, where `apartments.db` is stored.
- **Why:**
  - Fulfills the requirement: *"configure persistent Docker volumes for databases"*.
  - Ensures data is retained across `docker compose down` and `docker compose up`. Data is only deleted if the user explicitly runs `docker compose down -v`.

### Decision 6: Docker Compose Healthcheck & Standard Port Mapping
- **What:** Map host port `8000:8000` and configure a container healthcheck using Python's standard `urllib.request` (no external `curl` dependency required inside the container):
  `test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]`
- **Why:**
  - Allows Docker Compose to monitor application readiness without adding extra utilities to the container image.
  - Standard port `8000` matches existing local documentation and curl examples.

---

## 3. What Exists Today

- **Domain Models & Persistence:**
  - `Apartment` and `Booking` models in `app/models.py`.
  - SQLite with WAL mode, foreign keys (`ondelete="RESTRICT"`), and composite index `ix_bookings_apartment_status_dates`.
  - Persistent file `./data/apartments.db`.
- **REST API Endpoints:**
  - `POST /apartments`, `GET /apartments`, `GET /apartments/{id}`, `PUT /apartments/{id}`, `DELETE /apartments/{id}`.
  - `GET /apartments/search?start_date=...&end_date=...`.
  - `POST /bookings`, `GET /bookings`, `GET /bookings/{id}`, `PUT /bookings/{id}`, `POST /bookings/{id}/cancel`.
  - `GET /health` system health endpoint.
- **Automated Tests:**
  - 154 unit and integration tests across 8 test suites (`pytest`).
  - 98% overall test coverage with zero test pollution on `./data/apartments.db`.
- **Missing Elements:**
  - No web UI, HTML forms, or static assets (users currently must use `curl` or Swagger UI).
  - No `Dockerfile`.
  - No `docker-compose.yml` or Docker persistent volume configuration.
  - No automated tests for web forms.
  - Documentation does not yet cover Docker Compose workflows.

---

## 4. Verified and Measured Facts

| Metric / Check | Measured / Verified Value | Source |
| :--- | :--- | :--- |
| **Git Working Tree** | Clean on `main`, tagged `checkpoint-1` (`ef4d0ed`) | `git status` / `git log` |
| **Host Docker Engine** | Docker version `27.5.1` | `docker --version` |
| **Host Docker Compose** | Docker Compose version `v2.32.4-desktop.1` | `docker compose version` |
| **Current Test Suite** | 154 passed in 4.69s (100% green, 98% coverage) | `.venv/bin/pytest` |
| **SQLite WAL & FKs** | Active and verified | `app/database.py` |
| **Application Port** | 8000 free and responsive | `lsof -i :8000` |

---

## 5. Risks and Mitigations

### Risk 1: In-Container Permissions for SQLite Database File
- **Context:** SQLite creates additional temporary files (`-wal`, `-shm`) in the directory containing the database. If the container runs as a non-privileged user without write permissions to `/app/data`, SQLite operations will fail with `sqlite3.OperationalError: unable to open database file`.
- **Severity:** High.
- **Mitigation:** Ensure the `/app/data` directory inside the Dockerfile is owned by the container application user, and permissions are verified during container startup via `ensure_data_dir()`.

### Risk 2: Divergence Between Web UI and REST API Schemas
- **Context:** If web forms submit custom form-encoded bodies that differ from the JSON REST API schemas, we would need duplicate validation logic.
- **Severity:** Medium.
- **Mitigation:** Have the web UI forms submit standard JSON payloads via JavaScript `fetch()` directly to the existing REST endpoints. The web UI acts as a client of the exact same API, keeping validation DRY and consistent.

### Risk 3: Docker Volume Path Collision with Host Repository
- **Context:** If a bind mount `./data:/app/data` is used instead of a named volume, host file permissions and macOS/Linux file-sharing idiosyncrasies can cause write-lock issues.
- **Severity:** Medium.
- **Mitigation:** Use a **named volume** (`apartment_data:/app/data`) in `docker-compose.yml` as explicitly requested ("configure persistent Docker volumes").

### Risk 4: Test Suite Portability Inside Docker
- **Context:** `tests/test_demo_script.py` executes `scripts/demo.sh`, which searches for a free local port and starts a temporary `uvicorn` instance.
- **Severity:** Medium.
- **Mitigation:** Ensure `demo.sh` runs cleanly inside container environments by relying solely on standard POSIX shell constructs and Python standard library tools.

---

## 6. Implementation Stages

### Stage 1: OpenAPI Specification Enrichment
- **Tasks:**
  - Define explicit request and response example payloads in `app/schemas.py` using Pydantic `model_config = ConfigDict(json_schema_extra={...})`.
  - Add explicit error response schemas (`HTTPErrorResponse`) and document `responses={400: ..., 404: ..., 409: ..., 422: ...}` on apartment and booking router endpoints.
  - Add parameter-level descriptions and examples in route decorators.
  - Verify enriched documentation in Swagger UI (`/docs`) and raw OpenAPI (`/openapi.json`).

### Stage 2: Web Application Frontend & Interactive Forms
- **Tasks:**
  - Create static web assets under `app/static/`:
    - `index.html`: Responsive single-page dashboard with clear navigation tabs:
      1. **"Search & Book" tab:** Date range availability search form $\to$ interactive results list with live pricing $\to$ booking modal form with instant total price preview $\to$ confirmation feedback.
      2. **"Manage Apartments" tab:** Cards/table of all listings $\to$ "Add Apartment" modal form $\to$ "Edit Apartment" modal form $\to$ "Delete" button with active booking protection alert.
      3. **"Manage Bookings" tab:** Search/list bookings with apartment filter $\to$ "Modify Dates / Transfer" modal form $\to$ "Cancel Booking" button with immediate date release.
    - `styles.css`: Clean, professional, modern styling (responsive layout, accessible focus states, alert banners, modal dialogs).
    - `app.js`: Clean vanilla JavaScript handling form submissions via `fetch()`, dynamic UI rendering, date validation, and clear error toast displays.
  - Mount static assets in `app/main.py`:
    - Mount `/static` to `app/static/`.
    - Update `GET /` route to serve `app/static/index.html`.
    - Keep `/docs` and `/redoc` fully accessible.

### Stage 3: Automated Tests for Web UI & Forms
- **Tasks:**
  - Create `tests/test_web_ui.py`:
    - Test `GET /` returns HTTP `200 OK` with `text/html` content type and contains required form elements (`#search-form`, `#apartment-form`, `#booking-form`).
    - Test static assets (`/static/styles.css`, `/static/app.js`) are served correctly with proper MIME types.
    - Test that form API workflows work identically through the UI client layer.
  - Run full test suite (`pytest`) and confirm 100% green status.

### Stage 4: Dockerfile & Persistent Docker Volume Configuration
- **Tasks:**
  - Create `Dockerfile`:
    - Base: `python:3.12-slim`.
    - Working directory: `/app`.
    - Copy `requirements.txt` and install dependencies.
    - Copy application code (`app/`, `tests/`, `pyproject.toml`, `README.md`).
    - Create persistent data directory `/app/data`.
    - Expose port `8000`.
    - Standard command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
  - Create `.dockerignore` ignoring `.venv`, `__pycache__`, local `.git`, local `data/*.db`, and editor files.
  - Build and verify the Docker image locally: `docker build -t apartment-booking:latest .`.

### Stage 5: Docker Compose Configuration & Workflow Verification
- **Tasks:**
  - Create `docker-compose.yml`:
    - Service `web` with build context `.`.
    - Port mapping: `8000:8000`.
    - Environment: `DATABASE_URL=sqlite:////app/data/apartments.db`.
    - Volume: `apartment_data:/app/data`.
    - Healthcheck definition using Python urllib.
    - Named volume declaration: `volumes: apartment_data:`.
  - Verify complete workflow using Docker Compose:
    1. Start: `docker compose up --build -d`.
    2. Verify health: `docker compose ps` shows `healthy`.
    3. Run automated tests in container: `docker compose run --rm web pytest`.
    4. Test web forms & API at `http://localhost:8000`.
    5. Verify persistence: Create apartment and booking, run `docker compose down`, restart with `docker compose up -d`, and verify records are retained.
    6. Clean shutdown: `docker compose down`.

### Stage 6: Documentation & Fresh Checkout Verification Guide
- **Tasks:**
  - Update `README.md` with:
    - **Web Application Guide:** Visual and textual walkthrough of using the web forms at `http://localhost:8000`.
    - **Docker Compose Commands:** Exact commands to start, stop, and test the app from a fresh checkout.
    - **Web Address & Documentation Links:** `http://localhost:8000` (Web UI), `http://localhost:8000/docs` (Swagger UI).
    - **Persistent Volume Verification Guide:** Step-by-step instructions proving SQLite data survives `docker compose down` and container restarts.
  - Review all code changes for quality, maintainability, and security.
  - Commit all files with conventional commit messages and push to remote.
