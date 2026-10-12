# Apartment Booking API

A headless, RESTful backend service for managing apartment listings and reservations, built for the **Agile Software Development** course (Project 1).

---

## 📌 Table of Contents

- [Project Overview](#-project-overview)
- [Project Case & First Users](#-project-case--first-users)
- [User Stories & Acceptance Criteria](#-user-stories--acceptance-criteria)
- [Technology Stack](#-technology-stack)
- [Architecture & Persistence Strategy](#-architecture--persistence-strategy)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [API Documentation (No GUI Required)](#-api-documentation-no-gui-required)
- [🎮 Demonstrating the System (Checkpoint 1)](#-demonstrating-the-system-checkpoint-1)
  - [Option 1: Automated Demonstration Script (`scripts/demo.sh`)](#option-1-automated-demonstration-script-scriptsdemosh)
  - [Option 2: Step-by-Step Manual cURL Walkthrough](#option-2-step-by-step-manual-curl-walkthrough)
    - [Step 1: Check System Health](#step-1-check-system-health)
    - [Step 2: Manage Apartments (US1)](#step-2-manage-apartments-us1)
    - [Step 3: Search for Available Apartments (US3)](#step-3-search-for-available-apartments-us3)
    - [Step 4: Create a Booking (US2)](#step-4-create-a-booking-us2)
    - [Step 5: Verify Overlapping Booking Prevention (US4)](#step-5-verify-overlapping-booking-prevention-us4)
    - [Step 6: Update a Booking / Transfer Apartment (US2)](#step-6-update-a-booking--transfer-apartment-us2)
    - [Step 7: Cancel a Booking & Release Dates (US2)](#step-7-cancel-a-booking--release-dates-us2)
    - [Step 8: Verify Active Booking Deletion Protection](#step-8-verify-active-booking-deletion-protection)
- [Running Automated Tests](#-running-automated-tests)
- [Verifying Data Persistence](#-verifying-data-persistence)
- [Project Checkpoint 1 Checklist](#-project-checkpoint-1-checklist)

---

## 📖 Project Overview

This project provides a robust, backend-only API to power short-term apartment rentals. It eliminates the need for a graphical user interface by exposing a fully documented, standards-compliant OpenAPI/REST interface that allows users to:
1. List and maintain apartment catalogs.
2. Search available apartments across arbitrary date ranges.
3. Reserve stays with automatic pricing calculation and manage booking lifecycles.
4. Guarantee booking integrity by mathematically rejecting double and overlapping bookings.

---

## 👥 Project Case & First Users

### Selected Case: *Urban Short-Stay Rental Service*
A property rental platform facilitating short-term bookings between apartment hosts and traveling guests.

### First Users (Personas)
1. **Marco — The Property Host**
   - **Role:** Apartment owner/manager.
   - **Needs:** Add new apartments with pricing, capacity, and descriptions; update details or remove listings when no longer available.
   - **Goal:** Keep property information up to date without manual overhead, while ensuring existing bookings are never orphaned.
2. **Elena — The Traveler / Guest**
   - **Role:** Customer looking for accommodation.
   - **Needs:** Search for apartments free during specific travel dates; book a stay; view, modify, or cancel reservations.
   - **Goal:** Confidently reserve an apartment knowing dates are guaranteed and never double-booked.

---

## 🎯 User Stories & Acceptance Criteria

### User Story 1: Apartment Management
> *As a user, I want to add, update, remove, and view apartments so that the available places are current.*
- **Acceptance Criteria:**
  - Create an apartment with title, description, address, price per night, and capacity (`POST /apartments`).
  - View all apartments (`GET /apartments`) or single apartment details (`GET /apartments/{id}`).
  - Modify any attribute of an existing apartment (`PUT /apartments/{id}`).
  - Delete an apartment (`DELETE /apartments/{id}`). Deletion of an apartment with active, confirmed bookings is rejected with `409 Conflict`.

### User Story 2: Booking Management
> *As a user, I want to create, view, change, and cancel bookings so that I can manage my stay.*
- **Acceptance Criteria:**
  - Book an apartment by specifying `apartment_id`, `guest_name`, `guest_email`, `start_date`, and `end_date` (`POST /bookings`). Total price is automatically computed based on nights stayed and apartment rates.
  - View all bookings with pagination (`GET /bookings?limit=100&offset=0`) or filter by apartment (`GET /bookings?apartment_id=...`).
  - Fetch a specific booking by ID (`GET /bookings/{id}`).
  - Update dates, guest info, or transfer a booking to another apartment (`PUT /bookings/{id}`).
  - Cancel a booking via dedicated action endpoint (`POST /bookings/{id}/cancel`). Status transitions to `CANCELLED`, preserving audit history and immediately releasing dates for new guests. Cancelled bookings are immutable and cannot be updated.

### User Story 3: Date Range Availability Search
> *As a user, I want to search for apartments available during a date range so that I can find a place to book.*
- **Acceptance Criteria:**
  - Query apartments specifying `start_date` and `end_date` query parameters (`GET /apartments/search?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`).
  - Returns only apartments with **zero active/confirmed bookings** overlapping the requested date window.
  - Rejects invalid queries (e.g., `start_date >= end_date`) with descriptive `400 Bad Request` errors.

### User Story 4: Overlapping Booking Prevention
> *As a user, I want the system to prevent overlapping bookings so that an apartment is not booked by two people for the same dates.*
- **Acceptance Criteria:**
  - When creating or modifying a booking, the system evaluates active reservations for that apartment.
  - An overlap occurs when:
    $$\text{Existing.start\_date} < \text{Requested.end\_date} \quad \text{AND} \quad \text{Existing.end\_date} > \text{Requested.start\_date}$$
    AND $\text{Existing.status} \neq \text{'CANCELLED'}$.
  - If an overlap is detected, the API returns `409 Conflict` containing a clear error payload explaining the collision.
  - Cancelled bookings are ignored during collision checks.
  - Check-in on the same day another guest checks out is permitted (half-open date interval: `[start_date, end_date)`).
  - Updating a booking within the same apartment excludes itself from collision checks to prevent false self-collisions.

---

## 🛠 Technology Stack

- **Language:** Python 3.10+ (tested on Python 3.14)
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (modern, asynchronous, auto-generates OpenAPI/Swagger)
- **Data Validation & Schemas:** [Pydantic v2](https://docs.pydantic.dev/) (with whitespace trimming and email regex validation)
- **ORM & Database Abstraction:** [SQLAlchemy](https://www.sqlalchemy.org/) 2.0
- **Database Engine:** [SQLite](https://www.sqlite.org/) (file-based persistence in `./data/apartments.db` with `PRAGMA foreign_keys = ON;` and Write-Ahead Logging `WAL` mode)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (lightweight ASGI production server)
- **Automated Testing:** [pytest](https://docs.pytest.org/) & [HTTPX](https://www.python-httpx.org/) (in-memory SQLite test fixtures with zero file pollution)

---

## 💾 Architecture & Persistence Strategy

The system uses a layered architecture to keep business logic independent of transport and storage:

```
[ HTTP Requests / cURL / Swagger UI ]
                 │
                 ▼
     [ FastAPI Routers / Endpoints ]
                 │  (Pydantic validation & whitespace trimming)
                 ▼
    [ Service Layer / Business Logic ]  <─── Overlap Prevention Engine
                 │
                 ▼
   [ Data Layer (SQLAlchemy ORM) ]
                 │  (Composite Index & Foreign Key RESTRICT)
                 ▼
   [ SQLite File: ./data/apartments.db (WAL Mode) ]
```

### Persistence Mechanism
- Data is stored in a local SQLite file (`./data/apartments.db`).
- SQLite is configured with:
  - `PRAGMA foreign_keys = ON;` to enforce relational integrity.
  - `PRAGMA journal_mode = WAL;` (Write-Ahead Logging) to allow concurrent reads and writes without lock contention.
  - `timeout = 30.0` seconds to gracefully handle burst write concurrency.
- Database tables are automatically initialized on application startup.
- Data persists across server restarts, crashes, and machine reboots without needing external background services (like Docker or Postgres).

---

## 📁 Project Structure

```text
apartment-booking/
├── README.md               # Project documentation, quickstart, demo guides
├── pyproject.toml          # Pytest, coverage, and warning suppression configuration
├── requirements.txt        # Production & testing dependencies
├── data/
│   └── .gitkeep            # Directory holding the persistent SQLite DB file
├── dev_plans/
│   ├── roadmap.md          # Multi-phase implementation roadmap & dependency graph
│   ├── part0-scaffold/plan.md # Plan for initial setup and test harness
│   └── part2-bookings/plan.md # Plan for booking lifecycle and overlap engine
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI entrypoint, router registration, lifespan setup
│   ├── config.py           # Application settings (database path, debug flags)
│   ├── database.py         # SQLAlchemy engine, PRAGMA listeners, and get_db dependency
│   ├── models.py           # Database entities (Apartment, Booking, BookingStatus)
│   ├── schemas.py          # Pydantic request/response validation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── booking_service.py # Booking lifecycle, pricing, and overlap validation
│   └── routers/
│       ├── __init__.py
│       └── bookings.py     # /bookings endpoints (US2, US4)
└── tests/
    ├── __init__.py
    ├── conftest.py         # Test fixtures (in-memory SQLite, fresh sessions, TestClient)
    ├── test_health.py      # Health check and root redirect tests
    ├── test_database.py    # Engine connection, PRAGMA, and settings tests
    ├── test_models_schemas.py # Model persistence and schema validation tests
    ├── test_bookings.py    # US2 booking lifecycle and operation tests
    └── test_overlap.py     # US4 comprehensive overlap collision tests
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or newer (verify via `python3 --version`)
- `git`
- `curl` (for testing via command-line)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rmnfdrzq/apartment-booking.git
   cd apartment-booking
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(On Windows PowerShell: `.venv\Scripts\Activate.ps1`)*

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Running the Application

Start the local API server with Uvicorn:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- The API is available at: `http://127.0.0.1:8000`
- The database is automatically created at `./data/apartments.db`.

---

## 📚 API Documentation (No GUI Required)

FastAPI generates interactive, machine-readable, and web-readable documentation automatically:

- **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
  *(Allows exploring endpoints, schemas, and executing requests directly from a browser)*
- **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Raw OpenAPI JSON Spec:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 🎮 Demonstrating the System (Checkpoint 1)

For evaluation and demonstration purposes, two options are supported:

---

### Option 1: Automated Demonstration Script (`scripts/demo.sh`)

An automated shell script is provided to test the full end-to-end user journey across all user stories in a single command. It exercises creation, searching, booking, overlap rejection (`409 Conflict`), updating, cancellation, and persistence.

#### How to run the automated demo:
1. Ensure the server is running in a terminal:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. In a second terminal, execute the script:
   ```bash
   chmod +x scripts/demo.sh
   ./scripts/demo.sh
   ```

The script will print color-coded output verifying each step, asserting expected HTTP status codes (`201`, `200`, `409`), and producing a clean final report.

---

### Option 2: Step-by-Step Manual cURL Walkthrough

You can execute each user story interactively via `curl` to inspect the exact request and response payloads.

#### Step 1: Check System Health
```bash
curl -X GET http://127.0.0.1:8000/health
```
*Expected response:* `200 OK`
```json
{"status":"ok","app":"Apartment Booking API","version":"1.0.0"}
```

---

#### Step 2: Manage Apartments (US1)

##### Add an Apartment
```bash
curl -s -X POST http://127.0.0.1:8000/apartments \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sunny Alpine Studio",
    "description": "Cozy studio near central square with mountain views.",
    "address": "Piazza Walther 4, Bolzano",
    "price_per_night": 100.0,
    "max_guests": 2
  }'
```
*Expected response:* `201 Created` with generated `id`. Save the returned `id` to an environment variable:
```bash
APT_ID="<returned-apartment-id>"
```

##### List All Apartments
```bash
curl -s -X GET http://127.0.0.1:8000/apartments
```

##### Get Apartment Details
```bash
curl -s -X GET "http://127.0.0.1:8000/apartments/${APT_ID}"
```

##### Update an Apartment
```bash
curl -s -X PUT "http://127.0.0.1:8000/apartments/${APT_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sunny Alpine Studio (Renovated)",
    "price_per_night": 120.0
  }'
```

---

#### Step 3: Search for Available Apartments (US3)

Query apartments available between `2026-11-01` and `2026-11-05`:
```bash
curl -s -X GET "http://127.0.0.1:8000/apartments/search?start_date=2026-11-01&end_date=2026-11-05"
```
*Expected response:* `200 OK` with list containing `Sunny Alpine Studio`.

---

#### Step 4: Create a Booking (US2)

Reserve the apartment from `2026-11-01` to `2026-11-05` (4 nights at 120.0 € = 480.0 €):
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Elena Rossi\",
    \"guest_email\": \"elena.rossi@example.com\",
    \"start_date\": \"2026-11-01\",
    \"end_date\": \"2026-11-05\"
  }"
```
*Expected response:* `201 Created`
```json
{
  "id": "e67d4987-...",
  "apartment_id": "...",
  "guest_name": "Elena Rossi",
  "guest_email": "elena.rossi@example.com",
  "start_date": "2026-11-01",
  "end_date": "2026-11-05",
  "total_price": 480.0,
  "status": "CONFIRMED",
  "created_at": "..."
}
```
Save the returned booking ID:
```bash
BOOKING_ID="<returned-booking-id>"
```

---

#### Step 5: Verify Overlapping Booking Prevention (US4)

##### Scenario A: Attempt Overlapping Dates (Nov 3 to Nov 7)
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Bob Smith\",
    \"guest_email\": \"bob@example.com\",
    \"start_date\": \"2026-11-03\",
    \"end_date\": \"2026-11-07\"
  }"
```
*Expected response:* **`409 Conflict`**
```json
{
  "detail": "Apartment is not available for the requested date range: 2026-11-03 to 2026-11-07. Collides with an existing booking."
}
```

##### Scenario B: Same-Day Turnover (Nov 5 to Nov 10)
Check-in on checkout date (half-open interval `[2026-11-05, 2026-11-10)`) is permitted:
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Charlie Brown\",
    \"guest_email\": \"charlie@example.com\",
    \"start_date\": \"2026-11-05\",
    \"end_date\": \"2026-11-10\"
  }"
```
*Expected response:* `201 Created` *(Turnover permitted without conflict).*

---

#### Step 6: Update a Booking / Transfer Apartment (US2)

Modify booking dates from Nov 1–5 to Nov 1–6 (5 nights) and update guest contact:
```bash
curl -s -X PUT "http://127.0.0.1:8000/bookings/${BOOKING_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "end_date": "2026-11-06",
    "guest_email": "elena.updated@example.com"
  }'
```
*Expected response:* `200 OK` with recalculated `total_price: 600.0`. *(Note: updating on the same apartment applies self-exclusion to prevent false self-collisions).*

---

#### Step 7: Cancel a Booking & Release Dates (US2)

Soft-cancel Elena's booking to free up the dates:
```bash
curl -s -X POST "http://127.0.0.1:8000/bookings/${BOOKING_ID}/cancel"
```
*Expected response:* `200 OK` with `"status": "CANCELLED"`.

Now re-attempt the previously blocked dates (Nov 3 to Nov 7):
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Bob Smith\",
    \"guest_email\": \"bob@example.com\",
    \"start_date\": \"2026-11-03\",
    \"end_date\": \"2026-11-07\"
  }"
```
*Expected response:* `201 Created` *(Dates are now free after cancellation).*

---

#### Step 8: Verify Active Booking Deletion Protection

Attempt to delete an apartment that has active bookings:
```bash
curl -s -X DELETE "http://127.0.0.1:8000/apartments/${APT_ID}"
```
*Expected response:* `409 Conflict` *(Deletion is restricted to protect guest reservations).*

---

## 🧪 Running Automated Tests

A comprehensive test suite verifies all user stories, edge cases, date validation, and overlap conflicts.

Run the test suite:
```bash
pytest -v
```

Run with test coverage report:
```bash
pytest --cov=app --cov-report=term-missing
```

The test suite runs against an isolated, in-memory SQLite database (`sqlite:///:memory:`) using `StaticPool` to ensure fast and repeatable execution without altering your persistent `./data/apartments.db` file.

---

## 🔄 Verifying Data Persistence

To verify that project data survives restarts:
1. Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Create an apartment and booking via `curl` (see Steps 2 and 4).
3. Stop the server using `Ctrl + C`.
4. Check that the file `./data/apartments.db` exists on disk:
   ```bash
   ls -lh data/apartments.db
   ```
5. Restart the server:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Query the bookings list:
   ```bash
   curl -s -X GET http://127.0.0.1:8000/bookings
   ```
   *The previously created booking and apartment are still present.*

---

## ✅ Project Checkpoint 1 Checklist

| Checkpoint 1 Requirement | How It Is Satisfied | Status |
| :--- | :--- | :---: |
| **Selected project case & first users** | Detailed in [Project Case & First Users](#-project-case--first-users) (Marco & Elena). | ✅ |
| **Running application implementing user stories** | Implements US1 (Apartments), US2 (Bookings), US3 (Search), and US4 (Overlap prevention). | ✅ |
| **Documented API without GUI** | Interactive Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI JSON spec. | ✅ |
| **Persistent data storage** | SQLite file database at `./data/apartments.db` surviving application restarts with WAL mode and foreign keys. | ✅ |
| **Demonstrating and trying commands** | Two options provided: [Option 1 Automated Script](#option-1-automated-demonstration-script-scriptsdemosh) and [Option 2 Manual cURL Walkthrough](#option-2-step-by-step-manual-curl-walkthrough). | ✅ |
