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
- [Trying the API with cURL (Step-by-Step)](#-trying-the-api-with-curl-step-by-step)
  - [1. Manage Apartments (US1)](#1-manage-apartments-us1)
  - [2. Search for Available Apartments (US3)](#2-search-for-available-apartments-us3)
  - [3. Create and Manage Bookings (US2)](#3-create-and-manage-bookings-us2)
  - [4. Overlapping Booking Prevention (US4)](#4-overlapping-booking-prevention-us4)
- [Running Automated Tests](#-running-automated-tests)
- [Verifying Data Persistence](#-verifying-data-persistence)
- [Project Checkpoint 1 Checklist](#-project-checkpoint-1-checklist)

---

## 📖 Project Overview

This project provides a robust, backend-only API to power short-term apartment rentals. It eliminates the need for a graphical user interface by exposing a fully documented, standards-compliant OpenAPI/REST interface that allows users to:
1. List and maintain apartment catalogs.
2. Search available apartments across arbitrary date ranges.
3. Reserve stays and manage booking lifecycles.
4. Guarantee booking integrity by rejecting double/overlapping bookings.

---

## 👥 Project Case & First Users

### Selected Case: *Urban Short-Stay Rental Service*
A property rental platform facilitating short-term bookings between apartment hosts and traveling guests.

### First Users (Personas)
1. **Marco — The Property Host**
   - **Role:** Apartment owner/manager.
   - **Needs:** Add new apartments with pricing, capacity, and descriptions; update details or remove listings when no longer available.
   - **Goal:** Keep property information up to date without manual overhead.
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
  - Delete an apartment (`DELETE /apartments/{id}`).

### User Story 2: Booking Management
> *As a user, I want to create, view, change, and cancel bookings so that I can manage my stay.*
- **Acceptance Criteria:**
  - Book an apartment by specifying `apartment_id`, `guest_name`, `guest_email`, `start_date`, and `end_date` (`POST /bookings`).
  - View all bookings or fetch a specific booking by ID (`GET /bookings`, `GET /bookings/{id}`).
  - Update dates or guest information for an existing booking (`PUT /bookings/{id}`).
  - Cancel a booking (`POST /bookings/{id}/cancel` or `DELETE /bookings/{id}`). Cancelled bookings free up the calendar for other guests.

### User Story 3: Date Range Availability Search
> *As a user, I want to search for apartments available during a date range so that I can find a place to book.*
- **Acceptance Criteria:**
  - Query apartments specifying `start_date` and `end_date` query parameters (`GET /apartments/search?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`).
  - Returns only apartments with **zero active/confirmed bookings** overlapping the requested date window.
  - Rejects invalid queries (e.g., `start_date >= end_date` or past dates) with descriptive `400 Bad Request` errors.

### User Story 4: Overlapping Booking Prevention
> *As a user, I want the system to prevent overlapping bookings so that an apartment is not booked by two people for the same dates.*
- **Acceptance Criteria:**
  - When creating or modifying a booking, the system evaluates active reservations for that apartment.
  - An overlap occurs when:
    $$\text{Existing.start\_date} < \text{Requested.end\_date} \quad \text{AND} \quad \text{Existing.end\_date} > \text{Requested.start\_date}$$
  - If an overlap is detected, the API returns `409 Conflict` containing a clear error payload explaining the collision.
  - Cancelled bookings are ignored during collision checks.
  - Check-in on the same day another guest checks out is permitted (half-open date interval: `[start_date, end_date)`).

---

## 🛠 Technology Stack

- **Language:** Python 3.10+ (tested on Python 3.14)
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (modern, asynchronous, auto-generates OpenAPI/Swagger)
- **Data Validation & Schemas:** [Pydantic v2](https://docs.pydantic.dev/)
- **ORM & Database Abstraction:** [SQLAlchemy](https://www.sqlalchemy.org/) 2.0
- **Database Engine:** [SQLite](https://www.sqlite.org/) (file-based persistence in `./data/apartments.db`)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (lightweight ASGI production server)
- **Automated Testing:** [pytest](https://docs.pytest.org/) & [HTTPX](https://www.python-httpx.org/) (in-memory SQLite test fixtures)

---

## 💾 Architecture & Persistence Strategy

The system uses a layered architecture to keep business logic independent of transport and storage:

```
[ HTTP Requests / cURL / Swagger UI ]
                 │
                 ▼
     [ FastAPI Routers / Endpoints ]
                 │  (Pydantic validation)
                 ▼
    [ Service Layer / Business Logic ]  <─── Overlap Prevention Engine
                 │
                 ▼
   [ Data Layer (SQLAlchemy ORM) ]
                 │
                 ▼
   [ SQLite File: ./data/apartments.db ]
```

### Persistence Mechanism
- Data is stored in a local SQLite file (`./data/apartments.db`).
- On startup, database tables are automatically initialized if the file does not exist.
- Data persists across server restarts, crashes, and machine reboots without needing external background services (like Docker or Postgres).

---

## 📁 Project Structure

```text
apartment-booking/
├── README.md               # Project documentation, quickstart, API usage
├── .gitignore              # Ignores venv, db files, cache, bytecode
├── requirements.txt        # Production & testing dependencies
├── data/
│   └── .gitkeep            # Directory holding the persistent SQLite DB file
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI entrypoint, router registration, lifespan setup
│   ├── config.py           # Application settings (database path, debug flags)
│   ├── database.py         # SQLAlchemy engine, session maker, base declarative model
│   ├── models.py           # Database entities (Apartment, Booking)
│   ├── schemas.py          # Pydantic request/response validation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── apartment_service.py # Apartment business rules
│   │   └── booking_service.py   # Booking business rules & overlap validation
│   └── routers/
│       ├── __init__.py
│       ├── apartments.py        # /apartments endpoints (US1, US3)
│       └── bookings.py          # /bookings endpoints (US2, US4)
└── tests/
    ├── __init__.py
    ├── conftest.py         # Test database fixtures (in-memory SQLite)
    ├── test_apartments.py  # US1 apartment tests
    ├── test_bookings.py    # US2 booking management tests
    ├── test_overlap.py     # US4 overlap prevention test suite
    └── test_search.py      # US3 date search tests
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

## 💻 Trying the API with cURL (Step-by-Step)

You can try the entire application workflow directly from your terminal using `curl`:

### 1. Manage Apartments (US1)

#### Add an Apartment
```bash
curl -X POST http://127.0.0.1:8000/apartments \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sunny Alpine Studio",
    "description": "Cozy studio near central square with mountain views.",
    "address": "Piazza Walther 4, Bolzano",
    "price_per_night": 95.0,
    "max_guests": 2
  }'
```
*Expected response:* `201 Created` with generated `id`.

#### List All Apartments
```bash
curl -X GET http://127.0.0.1:8000/apartments
```

#### Get Apartment by ID
```bash
# Replace with your apartment id
APT_ID="<your-apartment-id>"
curl -X GET "http://127.0.0.1:8000/apartments/${APT_ID}"
```

#### Update an Apartment
```bash
curl -X PUT "http://127.0.0.1:8000/apartments/${APT_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sunny Alpine Studio (Renovated)",
    "description": "Newly renovated studio with panoramic views.",
    "address": "Piazza Walther 4, Bolzano",
    "price_per_night": 110.0,
    "max_guests": 3
  }'
```

#### Delete an Apartment
```bash
curl -X DELETE "http://127.0.0.1:8000/apartments/${APT_ID}"
```

---

### 2. Search for Available Apartments (US3)

Find apartments available for a stay between `2026-11-01` and `2026-11-05`:
```bash
curl -X GET "http://127.0.0.1:8000/apartments/search?start_date=2026-11-01&end_date=2026-11-05"
```
*Expected response:* `200 OK` with list of free apartments.

---

### 3. Create and Manage Bookings (US2)

#### Create a Booking
```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Elena Rossi\",
    \"guest_email\": \"elena.rossi@example.com\",
    \"start_date\": \"2026-11-01\",
    \"end_date\": \"2026-11-05\"
  }"
```
*Expected response:* `201 Created` with booking ID, status `"CONFIRMED"`, and calculated total price.

#### View Booking Details
```bash
BOOKING_ID="<your-booking-id>"
curl -X GET "http://127.0.0.1:8000/bookings/${BOOKING_ID}"
```

#### Change Booking Dates (Update)
```bash
curl -X PUT "http://127.0.0.1:8000/bookings/${BOOKING_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-11-01",
    "end_date": "2026-11-06"
  }'
```

#### Cancel a Booking
```bash
curl -X POST "http://127.0.0.1:8000/bookings/${BOOKING_ID}/cancel"
```
*Expected response:* `200 OK` with status `"CANCELLED"`. The dates are now freed for other bookings.

---

### 4. Overlapping Booking Prevention (US4)

#### Scenario A: Create first booking for Nov 10 - Nov 15
```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Alice\",
    \"guest_email\": \"alice@example.com\",
    \"start_date\": \"2026-11-10\",
    \"end_date\": \"2026-11-15\"
  }"
```
*Result:* `201 Created`.

#### Scenario B: Attempt overlapping booking for Nov 12 - Nov 17
```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Bob\",
    \"guest_email\": \"bob@example.com\",
    \"start_date\": \"2026-11-12\",
    \"end_date\": \"2026-11-17\"
  }"
```
*Result:* **`409 Conflict`**
```json
{
  "detail": "Apartment is not available for the requested date range: 2026-11-12 to 2026-11-17. Collides with an existing booking."
}
```

#### Scenario C: Non-overlapping booking starting on check-out date (Nov 15 - Nov 20)
```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d "{
    \"apartment_id\": \"${APT_ID}\",
    \"guest_name\": \"Charlie\",
    \"guest_email\": \"charlie@example.com\",
    \"start_date\": \"2026-11-15\",
    \"end_date\": \"2026-11-20\"
  }"
```
*Result:* **`201 Created`** *(Same-day turnover is allowed).*

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

The test suite runs against an isolated, in-memory SQLite database to ensure fast and repeatable execution without altering your persistent database file.

---

## 🔄 Verifying Data Persistence

To verify that project data survives restarts:
1. Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Create an apartment via `curl` (see US1).
3. Stop the server using `Ctrl + C`.
4. Check that the file `./data/apartments.db` exists on disk:
   ```bash
   ls -lh data/apartments.db
   ```
5. Restart the server:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Query the apartment list:
   ```bash
   curl -X GET http://127.0.0.1:8000/apartments
   ```
   *The previously created apartment is still present.*

---

## ✅ Project Checkpoint 1 Checklist

| Checkpoint 1 Requirement | How It Is Satisfied | Status |
| :--- | :--- | :---: |
| **Selected project case & first users** | Detailed in [Project Case & First Users](#-project-case--first-users) (Marco & Elena). | ✅ |
| **Running application implementing user stories** | Implements US1 (Apartments), US2 (Bookings), US3 (Search), and US4 (Overlap prevention). | ✅ |
| **Documented API without GUI** | Interactive Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI JSON spec. | ✅ |
| **Persistent data storage** | SQLite file database at `./data/apartments.db` surviving application restarts. | ✅ |
| **Instructions to start and try commands** | Clear instructions in [Getting Started](#-getting-started) and copy-pasteable [cURL Guide](#-trying-the-api-with-curl-step-by-step). | ✅ |
