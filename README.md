# Apartment Booking System

A full-stack web application and RESTful backend service for managing apartment listings, searching date-range availability, and handling reservations with strict collision prevention. Built for the **Agile Software Development** course (Project 1, Free University of Bozen-Bolzano).

---

## 📌 Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Selected Project Case & First Users](#2-selected-project-case--first-users)
- [3. Domain Concept Map](#3-domain-concept-map)
- [4. User Stories & Acceptance Criteria](#4-user-stories--acceptance-criteria)
- [5. Technology Stack & Design Decisions](#5-technology-stack--design-decisions)
- [6. Architecture & Database Persistence](#6-architecture--database-persistence)
- [7. Project Directory Structure](#7-project-directory-structure)
- [8. 🚀 Docker Quickstart (Fresh Checkout Commands)](#8--docker-quickstart-fresh-checkout-commands)
- [9. 💻 Local Quickstart Guide (Virtualenv)](#9--local-quickstart-guide-virtualenv)
- [10. 🌐 Interactive Web Application (Forms & Workflows)](#10--interactive-web-application-forms--workflows)
- [11. 📘 Resource-Oriented REST API & OpenAPI Specification](#11--resource-oriented-rest-api--openapi-specification)
- [12. 🎮 Demonstrating the System via CLI (Two Options)](#12--demonstrating-the-system-via-cli-two-options)
  - [Option 1: Automated Demo Script (`scripts/demo.sh`)](#option-1-automated-demo-script-scriptsdemosh)
  - [Option 2: Step-by-Step Manual cURL Walkthrough (Beginner-Friendly)](#option-2-step-by-step-manual-curl-walkthrough-beginner-friendly)
- [13. Verifying Persistent Storage Across Restarts & Docker Volumes](#13-verifying-persistent-storage-across-restarts--docker-volumes)
- [14. Running Automated Tests & Coverage](#14-running-automated-tests--coverage)
- [15. Database Management & Reset](#15-database-management--reset)
- [16. Checkpoint Compliance Checklist](#16-checkpoint-compliance-checklist)

---

## 1. Project Overview

This project implements an authoritative, headless backend engine for short-term apartment rentals. 

### What problem does it solve?
In vacation and apartment rentals, the single most critical failure mode is **double booking** (two guests reserving the same apartment for overlapping dates). This leads to displaced travelers, host penalties, and operational disruption.

This API provides:
1. **Catalog Management:** Hosts can list, update, and remove apartments.
2. **Date Availability Search:** Travelers can search for apartments free during specific calendar dates.
3. **Reservation Engine:** Guests can create, view, update, and cancel bookings with automated price calculation.
4. **Collision Prevention Engine:** A mathematical guarantee that overlapping dates for the same apartment return HTTP `409 Conflict` and are never committed to the database.
5. **Zero-Configuration Persistence:** Relational SQLite storage persisting data across restarts without external database servers or Docker containers.

---

## 2. Selected Project Case & First Users

### The Case: *Urban Short-Stay Rental Management*
A self-contained platform facilitating short-term rentals between apartment owners (hosts) and traveling guests.

### First Users (Personas)

```mermaid
flowchart LR
    Host["Marco (Property Host)\n• Lists apartments\n• Updates pricing & capacity\n• Protects bookings from deletion"]
    API["Apartment Booking API\n(Headless REST Engine)"]
    Guest["Elena (Traveler / Guest)\n• Searches free dates\n• Reserves stays\n• Modifies or cancels stays"]

    Host -->|POST /apartments| API
    Guest -->|GET /apartments/search\nPOST /bookings| API
```

1. **Marco — The Property Host**
   - **Role:** Apartment owner/property manager in Bolzano.
   - **Needs:** Add apartments with pricing per night, maximum guests, and descriptions; update details; remove unlisted places.
   - **Pain Point:** Avoid double bookings at all costs to preserve host reputation, and ensure active reservations are not accidentally orphaned if an apartment is deleted.

2. **Elena — The Traveler / Guest**
   - **Role:** Tourist or business traveler.
   - **Needs:** Discover apartments available for her travel dates; book a stay; inspect confirmation details; adjust dates if plans change; cancel if necessary.
   - **Pain Point:** Frustrated when double bookings occur or when cancellation policies are opaque.

---

## 3. Domain Concept Map

The domain concept map illustrates the core entities, their attributes, and their relationships:

```mermaid
classDiagram
    direction TB

    class Apartment {
        +String id (UUID PK)
        +String title
        +String description
        +String address
        +Float price_per_night
        +Int max_guests
        +DateTime created_at
    }

    class Booking {
        +String id (UUID PK)
        +String apartment_id (FK RESTRICT)
        +String guest_name
        +String guest_email
        +Date start_date
        +Date end_date
        +Float total_price
        +BookingStatus status
        +DateTime created_at
    }

    class BookingStatus {
        <<enumeration>>
        CONFIRMED
        CANCELLED
    }

    Apartment "1" o-- "0..*" Booking : has stays
    Booking ..> BookingStatus : lifecycle status
```

### Key Business Rules & Boundaries

1. **Discrete Date Nights & Half-Open Intervals $[check\_in, check\_out)$:**
   Stays are modeled as discrete calendar dates where `start_date` is the check-in day and `end_date` is the check-out day.
   - **Same-day turnover is strictly permitted:** Guest A checking out on `2026-11-05` and Guest B checking in on `2026-11-05` do **not** collide.
   - **Duration:** Exactly `(end_date - start_date).days` nights.
   - **Total Price:** Automatically computed as:
     $$\text{total\_price} = (\text{end\_date} - \text{start\_date}).\text{days} \times \text{apartment.price\_per\_night}$$

2. **The Canonical Overlap Formula:**
   Two bookings for the same apartment overlap if and only if:
   $$\text{Existing.start\_date} < \text{Requested.end\_date} \quad \text{AND} \quad \text{Existing.end\_date} > \text{Requested.start\_date}$$
   AND $\text{Existing.status} \neq \text{'CANCELLED'}$.

3. **Soft Cancellation & Date Release:**
   Cancelling a reservation (`POST /bookings/{id}/cancel`) marks `status = 'CANCELLED'`. This retains booking history for auditing while **immediately freeing up the calendar dates** for other guests. Cancelled bookings are immutable.

4. **Referential Integrity & Deletion Protection:**
   Foreign key constraints are enforced with `ondelete="RESTRICT"`. An apartment with active/confirmed bookings **cannot be deleted**, preventing orphaned guest reservations (`409 Conflict`). Once its stays are cancelled or finished, deleting the apartment (`204 No Content`) also removes that booking history.

---

## 4. User Stories & Acceptance Criteria

| User Story | Method & Endpoint | Acceptance Criteria |
| :--- | :--- | :--- |
| **US1: Manage Apartments** | `POST /apartments`<br>`GET /apartments`<br>`GET /apartments/{id}`<br>`PUT /apartments/{id}`<br>`DELETE /apartments/{id}` | Full CRUD. Adding an apartment requires title, address, positive price, and capacity. Deleting an apartment with active bookings returns `409 Conflict`. |
| **US2: Manage Bookings** | `POST /bookings`<br>`GET /bookings`<br>`GET /bookings/{id}`<br>`PUT /bookings/{id}`<br>`POST /bookings/{id}/cancel` | Create reservations with automatic price calculation. List bookings with pagination (`limit`/`offset`). Update dates or transfer to another apartment. Soft-cancel stays via dedicated action endpoint. |
| **US3: Date Range Search** | `GET /apartments/search?start_date=...&end_date=...` | Returns all apartments that have **zero active bookings** overlapping the requested date window. Rejects invalid queries (`start_date >= end_date`) with `400 Bad Request`. |
| **US4: Overlap Prevention** | Evaluated on `POST /bookings` & `PUT /bookings/{id}` | Rejects colliding reservations with HTTP `409 Conflict`. Allows same-day turnaround. Applies self-exclusion when updating dates within the same apartment. |

---

## 5. Technology Stack & Design Decisions

- **Runtime:** Python 3.10+ (tested on Python 3.14 on macOS arm64).
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (high performance, auto-generates OpenAPI 3.1 & Swagger UI).
- **Data Validation:** [Pydantic v2](https://docs.pydantic.dev/) (automatic whitespace stripping, email regex validation, date order validators).
- **ORM & Database:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with [SQLite](https://www.sqlite.org/).
- **Concurrency & Locking:** SQLite configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`), `PRAGMA foreign_keys = ON;`, and a 30-second busy timeout.
- **Server:** [Uvicorn](https://www.uvicorn.org/) (ASGI web server).
- **Testing:** [pytest](https://docs.pytest.org/) and [HTTPX](https://www.python-httpx.org/) with an isolated in-memory SQLite database (`StaticPool`) guaranteeing zero test pollution on disk.

---

## 6. Architecture & Database Persistence

### Do I need to install or run a database?
> [!IMPORTANT]
> **No!** SQLite is an embedded database included directly in the Python standard library. You do **not** need PostgreSQL, MySQL, Docker, or background database services. 
> 
> When the API starts, it automatically creates the database file at `./data/apartments.db` and initializes all tables and indexes. All data is saved persistently to disk and survives server restarts.

### Layered Architecture

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

---

## 7. Project Directory Structure

```text
apartment-booking/
├── README.md               # Complete project documentation & demonstration guide
├── Dockerfile              # Production Python 3.12-slim container definition
├── docker-compose.yml      # Orchestration with named persistent volume (apartment_data)
├── .dockerignore           # Ignored files for lean Docker build context
├── pyproject.toml          # Pytest, coverage, and warning suppression settings
├── requirements.txt        # Pinned Python dependencies
├── data/
│   └── .gitkeep            # Directory holding the persistent SQLite DB file
├── dev_plans/
│   ├── roadmap.md          # Multi-phase development roadmap & dependency graph
│   ├── part0-scaffold/plan.md # Plan for initial setup & test harness
│   ├── part1-apartments/plan.md # Plan for apartment catalog CRUD
│   ├── part2-bookings/plan.md # Plan for booking lifecycle & overlap engine
│   ├── part3-search/plan.md # Plan for date range availability search
│   ├── part4-demo/plan.md # Plan for end-to-end demo & Checkpoint 1 sign-off
│   └── checkpoint-2-web-docker/plan.md # Plan for Web UI, Docker, & OpenAPI
├── docs/
│   ├── openapi.json        # Enriched OpenAPI 3.1 specification (JSON format)
│   └── openapi.yaml        # Enriched OpenAPI 3.1 specification (YAML format)
├── scripts/
│   ├── demo.sh             # One-command CLI demo (all user stories + persistence)
│   └── export_openapi.py   # Automated script to export OpenAPI JSON & YAML
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI entrypoint, lifespan startup, & static mounts
│   ├── config.py           # Application settings (DB path, metadata)
│   ├── database.py         # SQLAlchemy engine, PRAGMA listeners, & get_db dependency
│   ├── models.py           # Database entities (Apartment, Booking, BookingStatus)
│   ├── schemas.py          # Pydantic schemas with examples & error structures
│   ├── static/             # Single-Page Web Application Frontend
│   │   ├── index.html      # Responsive HTML UI with forms and modals
│   │   ├── styles.css      # Design-token modern CSS styles
│   │   └── app.js          # Client-side workflows & Fetch API logic
│   ├── services/
│   │   ├── __init__.py
│   │   ├── apartment_service.py # Apartment catalog rules & availability search
│   │   └── booking_service.py # Overlap validation engine & booking lifecycle
│   └── routers/
│       ├── __init__.py
│       ├── apartments.py   # /apartments REST endpoints (US1, US3)
│       └── bookings.py     # /bookings REST endpoints (US2, US4)
└── tests/
    ├── __init__.py
    ├── conftest.py         # In-memory SQLite fixtures with zero file pollution
    ├── test_health.py      # Health check and root serving tests
    ├── test_database.py    # Engine connection, PRAGMA, and settings tests
    ├── test_models_schemas.py # Schema validation and ORM persistence tests
    ├── test_apartment_schemas.py # US1 apartment input validation tests
    ├── test_apartment_service.py # US1 apartment service and deletion policy tests
    ├── test_apartments.py  # US1 apartment REST API tests
    ├── test_search.py      # US3 availability search tests
    ├── test_demo_script.py # End-to-end test running scripts/demo.sh
    ├── test_bookings.py    # US2 booking lifecycle, pricing, and error handling tests
    ├── test_overlap.py     # US4 comprehensive overlap collision tests
    ├── test_web_ui.py      # Automated tests for HTML single-page app & static assets
    └── test_openapi.py     # OpenAPI schema validation & documentation tests
```

---

## 8. 🚀 Docker Quickstart (Fresh Checkout Commands)

For a fresh checkout, run the entire application, database, and interactive web interface in isolated containers with persistent storage using Docker Compose.

### App Web Address & Documentation URLs:
- 🌐 **Web Application UI:** [http://localhost:8000](http://localhost:8000)
- 📘 **Interactive Swagger UI (OpenAPI 3.1):** [http://localhost:8000/docs](http://localhost:8000/docs)
- 📕 **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- 📄 **Raw OpenAPI Spec:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Exact Commands for Fresh Checkout:

1. **Start the Application in the Background (with Live Updates):**
   ```bash
   docker compose up --build -d
   ```
   *Builds the container from `python:3.12-slim`, mounts persistent volume `apartment_data:/app/data` and live source `./app:/app/app`, runs startup table migrations, and starts Uvicorn with auto-reload on port `8000`.*

2. **Verify Container Health & Running Status:**
   ```bash
   docker compose ps
   ```
   *The container status will show `Up (healthy)` once the internal urllib healthcheck succeeds.*

3. **Run Automated Test Suite Inside Container:**
   ```bash
   docker compose exec web pytest
   # Or from a cold container run:
   docker compose run --rm web pytest
   ```
   *Executes all 165 unit, integration, and UI tests within the Docker container environment.*

4. **Stop the Application (Preserving Database Data):**
   ```bash
   docker compose down
   ```
   *Safely stops the container while keeping your database completely preserved in the named Docker volume `apartment_data`.*

5. **Stop and Reset Database Volume (Fresh Clean State):**
   ```bash
   docker compose down -v
   ```

### ⚡ Live Updates & Hot-Reloading (No Restart Needed):
- **Instant Code Reflection:** The host directory `./app` is bind-mounted directly into the container (`/app/app`), so any file saved on your host machine is immediately visible inside the container.
- **Auto-Reloading Backend:** Uvicorn runs with `--reload`, automatically detecting Python file changes and restarting the server without downtime.
- **Browser Live Refresh (SSE):** The frontend connects to `/dev/live-reload` via Server-Sent Events. When any HTML, CSS, JavaScript, or Python file is saved on the host, the browser page refreshes automatically without needing to restart Docker or manually reload the page.
- **No-Cache Static Headers:** Static files and HTML responses include `Cache-Control: no-cache, no-store, must-revalidate` preventing stale browser caching on reload.

---

## 9. 💻 Local Quickstart Guide (Virtualenv)

If you prefer running directly on your local machine without Docker:

### Step 1: Clone Repository
```bash
git clone https://github.com/rmnfdrzq/apartment-booking.git
cd apartment-booking
```

### Step 2: Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
*(On Windows PowerShell: `.venv\Scripts\Activate.ps1`)*

### Step 3: Install Dependencies & Start the Server
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Web App:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Database file:** Automatically created at `./data/apartments.db`.
- **Live Updates:** Automatic SSE reload and no-cache headers operate out of the box when editing any files.

---

## 10. 🌐 Interactive Web Application (Forms & Workflows)

The application provides an interactive single-page web interface served at **[http://localhost:8000](http://localhost:8000)** that allows users to complete all rental workflows using dedicated forms without command-line input.

```
┌────────────────────────────────────────────────────────────────────────┐
│ 🏠 Apartment Booking                                                   │
├────────────────────────────────────────────────────────────────────────┤
│ [Search & Book]        [Apartments]        [Bookings]       [API Docs] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  FIND AN APARTMENT FOR YOUR STAY                                       │
│  ┌────────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ Check-in: 2026-11-10│  │Check-out: 2026-11-14│  │ [Search Available] │  │
│  └────────────────────┘  └──────────────────┘  └────────────────────┘  │
│                                                                        │
│  Available Apartments (2 available for 4 nights):                      │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐    │
│  │ Alpine View Studio    ID #a9 │  │ City Center Loft      ID #b3 │    │
│  │ 📍 Via Roma 10, Bolzano      │  │ 📍 Piazza Walther 4, Bolzano │    │
│  │ 👥 Max 2 guests              │  │ 👥 Max 4 guests              │    │
│  │ €120.00 / night              │  │ €150.00 / night              │    │
│  │ Total (4 nights): €480.00    │  │ Total (4 nights): €600.00    │    │
│  │ [Book This Stay]             │  │ [Book This Stay]             │    │
│  └──────────────────────────────┘  └──────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

### Workflow 1: Date Availability Search & Instant Booking (Guest)
1. **Search Available Stays:**
   - Choose check-in and check-out dates via the date inputs.
   - Click **Search Available**. The system queries `/apartments/search` and renders cards for all properties with guaranteed zero overlapping reservations.
   - Each card dynamically displays the nightly rate and the total stay cost ($nights \times rate$).
2. **Instant Reservation Form (Modal):**
   - Click **Book This Stay** on an apartment card.
   - The booking modal appears, pre-populated with your chosen dates and live duration and price recalculation.
   - Enter guest full name and guest email.
   - Click **Confirm Reservation**. The booking is sent via `POST /bookings`.
   - On success, a confirmation toast notification pops up with the reservation ID and total price. If another guest books overlapping dates concurrently, a clear conflict error banner is displayed.

### Workflow 2: Apartment Catalog Management (Host)
1. Navigate to the **Apartments** tab.
2. **Add New Listing:**
   - Click **+ Add New Apartment**.
   - Fill in Title, Address, Price per Night (€), Max Guests, and Description.
   - Click **Save Listing** to create the apartment via `POST /apartments`.
3. **Edit Listing:**
   - Click **✏ Edit** on any card.
   - Modify pricing, address, capacity, or description.
   - Click **Update Listing** to commit changes via `PUT /apartments/{id}`.
4. **Delete Listing with Protection:**
   - Click **🗑 Delete** on any card.
   - If the property has active bookings, the system catches the `409 Conflict` and informs the host: *"Cannot delete apartment with active reservations. Cancel or modify reservations first."*

### Workflow 3: Reservations & Bookings Management (Guest / Host)
1. Navigate to the **Bookings** tab.
2. **Filter by Apartment:**
   - Use the dropdown menu to inspect reservations for a specific apartment or view all bookings across your portfolio.
3. **Modify Stay Dates or Transfer Apartment:**
   - Click **Modify** next to any active booking.
   - Adjust dates or select a different apartment. Duration and total price are automatically recalculated live.
   - Submit **Save Changes** (`PUT /bookings/{id}`).
4. **Cancel Stay to Release Calendar Dates:**
   - Click **Cancel** next to a booking.
   - The status is marked as `CANCELLED` (`POST /bookings/{id}/cancel`), and the dates are immediately released so other travelers can discover and book them.

---

## 11. 📘 Resource-Oriented REST API & OpenAPI Specification

The backend is engineered as a clean, resource-oriented REST API adhering strictly to HTTP/1.1 semantics, standard JSON structures, and standard HTTP status codes:

### Resource Endpoints Summary:
| HTTP Method | URL Path | Status Code | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/apartments` | `200 OK` | Paginated catalog of all apartments. |
| `POST` | `/apartments` | `201 Created` | Create a new apartment listing. |
| `GET` | `/apartments/{id}` | `200 OK` | Retrieve apartment listing by UUID. |
| `PUT` | `/apartments/{id}` | `200 OK` | Full update of apartment attributes. |
| `DELETE` | `/apartments/{id}` | `204 No Content` | Remove apartment listing (fails with `409` if active stays exist). |
| `GET` | `/apartments/search` | `200 OK` | Search for apartments with zero overlapping bookings for requested dates. |
| `GET` | `/bookings` | `200 OK` | Paginated list of reservations (filterable by apartment). |
| `POST` | `/bookings` | `201 Created` | Create new reservation (fails with `409` on date overlap). |
| `GET` | `/bookings/{id}` | `200 OK` | Retrieve reservation details by UUID. |
| `PUT` | `/bookings/{id}` | `200 OK` | Update reservation dates/guest (fails with `409` on overlap). |
| `POST` | `/bookings/{id}/cancel` | `200 OK` | Soft-cancel reservation and immediately free calendar dates. |
| `GET` | `/health` | `200 OK` | Service operational health monitoring. |

### Error Response Schemas & Status Codes:
All error responses adhere to a consistent JSON structure:
- `400 Bad Request`: Logical domain errors (e.g., check-out date before check-in date).
- `404 Not Found`: Target apartment or booking UUID does not exist.
- `409 Conflict`: Double-booking overlap detected or deletion blocked due to active stays.
- `422 Unprocessable Entity`: Input validation error (missing required fields, negative rates, invalid emails).

```json
{
  "detail": "Apartment 1 is already booked from 2026-11-01 to 2026-11-05"
}
```

### Static OpenAPI Specification Files:
- **JSON Format:** [`docs/openapi.json`](docs/openapi.json)
- **YAML Format:** [`docs/openapi.yaml`](docs/openapi.yaml)
- **Export Script:** To refresh the static spec files automatically:
  ```bash
  python scripts/export_openapi.py
  ```

---

## 12. 🎮 Demonstrating the System via CLI (Two Options)

For grading and verification, you can choose between two demonstration approaches:

---

### Option 1: Automated Demo Script (`scripts/demo.sh`)

Verify the entire system with **one command** (from the project root, with dependencies installed):

```bash
./scripts/demo.sh
```

The script starts its own server on a free port with a **temporary database** (your `./data/apartments.db` is never touched), runs the full user journey, restarts the server to prove persistence, and cleans up afterwards. It takes a few seconds.

| Step | What is checked |
| :--- | :--- |
| 1 | `GET /health` → `200` |
| 2 | Host adds 2 apartments (`201`), invalid price rejected (`422`), price updated (`PUT` → `200`), apartments listed and viewed (US1) |
| 3 | Guest searches a date range → both apartments available; invalid range → `400` (US3) |
| 4 | Elena books apartment 1 → `201`, price = nights × price per night; apartment disappears from search (US2) |
| 5 | Overlapping booking → `409`; same-day turnaround → `201` (US4) |
| 6 | Second guest books apartment 2 instead → `201` |
| 7 | Booking dates changed and booking transferred to another apartment, with re-checked overlaps and recalculated prices (US2, US4) |
| 8 | Elena cancels → `CANCELLED` (US2) |
| 9 | Search again → apartment 1 is free again (US3) |
| 10 | Server is stopped and restarted → all changes are still there (persistence) |
| 11 | `/docs` and `/openapi.json` document every endpoint |
| 12 | Apartment with active stays cannot be removed (`409`); after cancellations it is removed (`204`) (US1) |

Every step asserts the HTTP status code and key response values. Each check prints `✔`; the first failed check prints `✘` with the server response and the script exits with code `1`.

Dates are calculated relative to today, so the demo never goes out of date.

**Against a server you already started** (e.g. to watch requests in its log), pass its URL. The restart step is then skipped, and the demo removes the data it created at the end (if a check fails midway, the records created so far stay in that server's database):
```bash
BASE_URL=http://127.0.0.1:8000 ./scripts/demo.sh
```

Help: `./scripts/demo.sh --help`. The script works on macOS and Linux (bash 3.2+, `curl`, Python; no `jq` needed) and runs inside the test suite as `tests/test_demo_script.py`.

---

### Option 2: Step-by-Step Manual cURL Walkthrough (Beginner-Friendly)

If you prefer to execute commands one by one to inspect the requests and responses, open a terminal with the server running and follow these steps.

> [!TIP]
> The commands below use standard bash variables (`APT_ID` and `BOOKING_ID`) so you can copy and paste them directly into your terminal in order!
>
> Run the steps **in order on an empty database** (`rm -f data/apartments.db` before starting the server). The example dates are in November 2027; if they are already in the past, replace them with future dates — bookings that have already ended no longer count as active.

#### Step 1: Verify the API is Alive
Check that the service is running:
```bash
curl -s -X GET http://127.0.0.1:8000/health
```
**Expected Output:** `200 OK`
```json
{"status":"ok","app":"Apartment Booking API","version":"1.0.0"}
```

---

#### Step 2: Manage Apartments (US1)

##### 2.1 Add an Apartment (Marco the Host)
Add a listing with pricing of 100.0 € per night:
```bash
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/apartments \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sunny Alpine Studio",
    "description": "Cozy studio near central square with mountain views.",
    "address": "Piazza Walther 4, Bolzano",
    "price_per_night": 100.0,
    "max_guests": 2
  }')
echo $RESPONSE
```
**Expected Output:** `201 Created` with a generated UUID `id`.  
Save the apartment ID to a variable:
```bash
export APT_ID=$(echo $RESPONSE | grep -o '"id":"[^"]*' | cut -d'"' -f4)
echo "Using Apartment ID: $APT_ID"
```

##### 2.2 List All Apartments
```bash
curl -s -X GET http://127.0.0.1:8000/apartments
```

##### 2.3 Inspect Single Apartment Details
```bash
curl -s -X GET "http://127.0.0.1:8000/apartments/${APT_ID}"
```

##### 2.4 Update Apartment Pricing
Increase the price per night to 120.0 €:
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

Find apartments available for a stay between `2027-11-01` and `2027-11-05`:
```bash
curl -s -X GET "http://127.0.0.1:8000/apartments/search?start_date=2027-11-01&end_date=2027-11-05"
```
**Expected Output:** `200 OK` with an array containing `Sunny Alpine Studio (Renovated)` (since it currently has no bookings).

An invalid range (check-out before check-in) is rejected:
```bash
curl -s -i "http://127.0.0.1:8000/apartments/search?start_date=2027-11-05&end_date=2027-11-01"
```
**Expected Output:** `HTTP/1.1 400 Bad Request`

---

#### Step 4: Create a Booking with Automatic Price Calculation (US2)

Elena reserves the apartment from `2027-11-01` to `2027-11-05` (4 nights $\times$ 120.0 € = 480.0 €):
```bash
BOOKING_RESP=$(curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Elena Rossi\",
    \"guest_email\": \"elena.rossi@example.com\",
    \"start_date\": \"2027-11-01\",
    \"end_date\": \"2027-11-05\"
  }")
echo $BOOKING_RESP
```
**Expected Output:** `201 Created`
```json
{
  "id": "e67d4987-...",
  "apartment_id": "...",
  "guest_name": "Elena Rossi",
  "guest_email": "elena.rossi@example.com",
  "start_date": "2027-11-01",
  "end_date": "2027-11-05",
  "total_price": 480.0,
  "status": "CONFIRMED",
  "created_at": "..."
}
```
Save the booking ID:
```bash
export BOOKING_ID=$(echo $BOOKING_RESP | grep -o '"id":"[^"]*' | cut -d'"' -f4)
echo "Using Booking ID: $BOOKING_ID"
```

---

#### Step 5: Verify Overlapping Booking Prevention (US4)

##### 5.1 Test Collision Rejection (Nov 3 to Nov 7)
Bob attempts to book the same apartment for dates overlapping Elena's stay:
```bash
curl -s -i -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Bob Smith\",
    \"guest_email\": \"bob.smith@example.com\",
    \"start_date\": \"2027-11-03\",
    \"end_date\": \"2027-11-07\"
  }"
```
**Expected Output:** **`HTTP/1.1 409 Conflict`**
```json
{
  "detail": "Apartment is not available for the requested date range: 2027-11-03 to 2027-11-07. Collides with an existing booking."
}
```
*The double booking is rejected, protecting Elena's stay.*

##### 5.2 Test Same-Day Turnover (Nov 5 to Nov 10)
Charlie books starting on the exact day Elena checks out:
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Charlie Brown\",
    \"guest_email\": \"charlie@example.com\",
    \"start_date\": \"2027-11-05\",
    \"end_date\": \"2027-11-10\"
  }"
```
**Expected Output:** `201 Created`  
*(Same-day turnover $[start, end)$ is permitted: check-in on checkout date succeeds).*

---

#### Step 6: Update a Booking / Transfer Apartment (US2)

Elena wants to extend her stay until Nov 6, but Charlie checks in on Nov 5:
```bash
curl -s -X PUT "http://127.0.0.1:8000/bookings/${BOOKING_ID}" \
  -H "Content-Type: application/json" \
  -d '{"end_date": "2027-11-06"}'
```
**Expected Output:** `409 Conflict` — the changed dates are re-checked against other bookings.

Instead, she arrives one day earlier (check-in Oct 31 instead of Nov 1, total 5 nights $\times$ 120.0 € = 600.0 €) and updates her email:
```bash
curl -s -X PUT "http://127.0.0.1:8000/bookings/${BOOKING_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2027-10-31",
    "guest_email": "elena.updated@example.com"
  }'
```
**Expected Output:** `200 OK` with updated `start_date: 2027-10-31` and recalculated `total_price: 600.0`.  
*(Self-exclusion logic prevents the booking from colliding with its own previous dates).*

---

#### Step 7: Cancel a Booking & Release Dates (US2)

Elena cancels her reservation:
```bash
curl -s -X POST "http://127.0.0.1:8000/bookings/${BOOKING_ID}/cancel"
```
**Expected Output:** `200 OK` with `"status": "CANCELLED"`.

Now Bob books the dates Elena released (Nov 1 to Nov 5), which were blocked a moment ago:
```bash
curl -s -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Bob Smith\",
    \"guest_email\": \"bob.smith@example.com\",
    \"start_date\": \"2027-11-01\",
    \"end_date\": \"2027-11-05\"
  }"
```
**Expected Output:** `201 Created`  
*(The dates are immediately free for new bookings following cancellation).*

---

#### Step 8: Verify Active Booking Deletion Protection

Marco attempts to delete an apartment that has Bob's and Charlie's active confirmed bookings:
```bash
curl -s -i -X DELETE "http://127.0.0.1:8000/apartments/${APT_ID}"
```
**Expected Output:** **`HTTP/1.1 409 Conflict`**  
*(Apartments with active stays cannot be removed, protecting Bob's and Charlie's bookings. Once their bookings are cancelled or finished, `DELETE` succeeds with `204 No Content`.)*

---

## 13. Verifying Persistent Storage Across Restarts & Docker Volumes

The application guarantees that all catalog listings and reservations survive application restarts and container rebuilds.

### Scenario A: Docker Named Volume Persistence (`apartment_data`)

1. Start the Docker containers:
   ```bash
   docker compose up --build -d
   ```
2. Create an apartment listing:
   ```bash
   curl -s -X POST http://localhost:8000/apartments \
     -H "Content-Type: application/json" \
     -d '{"title": "Chalet Persistent", "address": "Via Roma 1, Bolzano", "price_per_night": 180.0, "max_guests": 4}'
   ```
3. Stop and remove the running container:
   ```bash
   docker compose down
   ```
4. Recreate and start the container afresh:
   ```bash
   docker compose up -d
   ```
5. Query the apartments catalog:
   ```bash
   curl -s http://localhost:8000/apartments
   ```
   **Result:** The listing created before container destruction is still fully present. The named volume `apartment_data` securely retained `/app/data/apartments.db`.

---

### Scenario B: Local Server SQLite File Persistence

1. Note existing bookings from your session:
   ```bash
   curl -s -X GET http://127.0.0.1:8000/bookings
   ```
2. Stop the local Uvicorn server by pressing `Ctrl + C`.
3. Check the persistent SQLite file on disk:
   ```bash
   ls -lh data/apartments.db
   ```
4. Restart Uvicorn:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
5. Query the bookings list again:
   ```bash
   curl -s -X GET http://127.0.0.1:8000/bookings
   ```
   **Result:** All listings, confirmed stays, and cancelled records remain intact.

---

## 14. Running Automated Tests & Coverage

The test suite contains **165 automated tests** covering schemas, services, overlap conflict detection, REST APIs, static assets, web UI HTML delivery, live updates, and OpenAPI documentation integrity.

### Run Tests Locally (Host Machine):
```bash
pytest -v
```

### Run Tests with Full Coverage Report:
```bash
pytest --cov=app --cov-report=term-missing
```

### Run Tests Inside Docker Container:
```bash
docker compose exec web pytest
# Or from a cold container run:
docker compose run --rm web pytest
```

### Test Suite Highlights:
- **165 Passed Tests** with **97% line & branch coverage**.
- **In-Memory SQLite Isolation:** Test database uses `StaticPool` in memory; running `pytest` will **never touch or pollute** `./data/apartments.db`.
- **Comprehensive Scenarios:** Covers valid workflows, edge cases, negative numbers, extreme date windows, same-day turnover, self-collision exclusion on edits, and full web UI form elements.

---

## 15. Database Management & Reset

### Reset Local Database:
```bash
rm data/apartments.db
```
The next time Uvicorn starts, an empty database will be recreated automatically.

### Reset Docker Compose Persistent Volume:
```bash
docker compose down -v
```
Removes all containers, internal networks, and the `apartment_data` persistent volume.

---

## 16. Checkpoint Compliance Checklist

| Checkpoint Criteria | Implementation Evidence | How to Verify | Status |
| :--- | :--- | :--- | :---: |
| **Web Application with Forms for Existing Workflows** | Single-page responsive web app at `/` with forms for searching, booking, adding/editing apartments, and modifying/cancelling reservations ([Section 10](#10--interactive-web-application-forms--workflows)). | Open [http://localhost:8000](http://localhost:8000) in browser; run `tests/test_web_ui.py`. | ✅ |
| **Resource-Oriented REST API** | Semantic URLs (`/apartments`, `/bookings`), standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`), clean JSON bodies, standard status codes (`200`, `201`, `204`, `400`, `404`, `409`, `422`) ([Section 11](#11--resource-oriented-rest-api--openapi-specification)). | Read Section 11; explore `/docs`. | ✅ |
| **Documented OpenAPI Specification** | Enriched OpenAPI 3.1 documentation with parameters, realistic examples, and error schemas (`400`, `404`, `409`, `422`). Exported to `docs/openapi.json` and `docs/openapi.yaml`. | Open [http://localhost:8000/docs](http://localhost:8000/docs); run `tests/test_openapi.py`. | ✅ |
| **Unit & Integration Tests for Key Rules** | 165 automated tests (97% branch coverage) testing date math, overlap formulas, cancellation release, deletion protection, and web UI. | Run `pytest -v` or `docker compose exec web pytest`. | ✅ |
| **Persistent Docker Volumes for Databases** | Docker Compose configured with named volume `apartment_data:/app/data` backing SQLite ([Section 8](#8--docker-quickstart-fresh-checkout-commands), [Section 13](#13-verifying-persistent-storage-across-restarts--docker-volumes)). | Run `docker compose down` then `docker compose up -d` and inspect data. | ✅ |
| **Verified Workflows Started with Docker Compose** | Multi-platform container based on `python:3.12-slim` with automated healthcheck and complete workflow support. | Run `docker compose up --build -d` and try web app or curl. | ✅ |
| **Documented Exact Commands & Web Address** | Exact commands to start, stop, and test from a fresh checkout documented alongside web address `http://localhost:8000` ([Section 8](#8--docker-quickstart-fresh-checkout-commands)). | Follow Section 8 from a clean shell. | ✅ |
