# Implementation Plan: Part 1 — Apartment Catalog Subsystem

**Document Path:** `/dev_plans/part1-apartments/plan.md`  
**Phase:** `feature/part1-apartments`  
**User Stories Covered:** **US1** (Add, update, remove, and view apartments)  
**Target Milestone:** Checkpoint 1 Core Domain (Track A)  

---

## 1. Goal

Deliver a production-ready **Apartment Catalog Subsystem** so that the list of available places is always current. By the end of this phase, the application will:

1. Expose a documented REST resource for apartments:
   - `POST /apartments` → `201 Created`
   - `GET /apartments` → `200 OK` (paginated)
   - `GET /apartments/{apartment_id}` → `200 OK` / `404 Not Found`
   - `PUT /apartments/{apartment_id}` → `200 OK` / `404 Not Found`
   - `DELETE /apartments/{apartment_id}` → `204 No Content` / `404 Not Found` / `409 Conflict`
2. Isolate all apartment business rules in `app/services/apartment_service.py`, keeping the router thin.
3. Reject every invalid payload with `422 Unprocessable Entity` before it reaches the database (no `500` caused by user input).
4. Protect guests: an apartment with active (confirmed, not yet finished) bookings cannot be deleted.
5. Ship a test suite covering the service (unit, TDD) and the HTTP API (integration), with the whole existing suite still green.

---

## 2. Locked Decisions

### Decision 1: Build on the Existing `Apartment` Model and Schemas (Contract-First)
- **What:** Reuse the `Apartment` ORM model and `ApartmentCreate` / `ApartmentUpdate` / `ApartmentResponse` schemas already merged with Part 2. Step 1.1 becomes a *hardening* step, not a rewrite.
- **Why:**
  - Part 2 (bookings) already depends on `Apartment.id` (UUID string) and `price_per_night`; changing the contract would break the merged track.
  - Avoids duplicate definitions and merge conflicts in `app/models.py` / `app/schemas.py`.

### Decision 2: Thin Router → Service Layer → ORM
- **What:** `app/routers/apartments.py` only parses HTTP input and maps results; `app/services/apartment_service.py` holds all logic (`create_apartment`, `get_apartments`, `get_apartment_by_id`, `update_apartment`, `delete_apartment`).
- **Why:**
  - Same layering as `booking_service.py` (consistency across the codebase).
  - Service functions are unit-testable with a plain `Session`, without HTTP.
  - Part 3 (search) can reuse the service without touching the router logic.
- **Note:** To stay consistent with `booking_service.py`, the service raises `HTTPException` for `404`/`409`. Moving both services to domain exceptions is a separate, project-wide refactor and is out of scope here.

### Decision 3: `PUT` Uses Partial-Update Semantics, Explicit `null` Is Rejected for Required Fields
- **What:** `PUT /apartments/{id}` updates only the fields present in the body (`model_dump(exclude_unset=True)`). Sending `null` for `title`, `address`, `price_per_night`, or `max_guests` returns `422`. `description: null` is allowed and clears the description.
- **Why:**
  - Matches the roadmap and the example CLI (`apartment update ID [--name NAME] [--address ADDRESS]` — optional fields).
  - Without the `null` guard, `{"title": null}` would pass validation and hit the `NOT NULL` constraint → `IntegrityError` → `500`.

### Decision 4: Strict Input Bounds
- **What:**
  - `title`, `address`: 1–255 characters after whitespace trimming (matches `String(255)`).
  - `description`: optional, max 5,000 characters; blank strings are stored as `NULL`.
  - `price_per_night`: `> 0`, `≤ 1,000,000`, finite (`NaN`/`Infinity` rejected).
  - `max_guests`: integer `1–100`.
- **Why:**
  - Python's JSON parser accepts `Infinity` and `NaN`; `Infinity > 0` passes a plain `gt=0` check and would poison booking price calculations.
  - Unbounded text fields allow oversized payloads to be stored indefinitely.

### Decision 5: Deletion Policy — Block Active Bookings, Remove History
- **What:** `DELETE /apartments/{id}`:
  - `409 Conflict` if the apartment has at least one **active** booking (`status = CONFIRMED` and `end_date > today`).
  - Otherwise the apartment is deleted together with its **historical** bookings (cancelled or already finished) in one transaction → `204 No Content`.
- **Why:**
  - Fulfills the Part 2 locked decision ("deleting an apartment with active bookings is rejected with 409").
  - The FK is `ON DELETE RESTRICT`; without removing history, a single cancelled booking would make an apartment impossible to delete, which breaks US1 ("remove apartments").
  - The database stays the final guard: only history rows are deleted explicitly, so if a new booking slips in between the check and the delete, the `RESTRICT` constraint fails, the transaction rolls back, and the API returns `409` instead of silently deleting a live reservation.

### Decision 6: Paginated and Deterministic Listing
- **What:** `GET /apartments?limit=100&offset=0` (`1 ≤ limit ≤ 500`, `offset ≥ 0`), ordered by `created_at`, then `id`.
- **Why:**
  - Same pagination contract as `GET /bookings`.
  - Prevents unbounded responses as the catalog grows; the `id` tie-breaker keeps pages stable when several rows share a timestamp (SQLite `CURRENT_TIMESTAMP` has 1-second resolution).

### Decision 7: Route Naming Leaves Room for Part 3
- **What:** Path parameter is `/apartments/{apartment_id}` (string). Part 3 must declare `GET /apartments/search` **before** the `{apartment_id}` route in the same router.
- **Why:** Otherwise FastAPI would match `search` as an apartment ID and return `404`.

---

## 3. What Exists Today

- **Branch:** `feature/part1-apartments`, created from `main` at `886bd46`.
- **Merged on `main`:** Part 0 (scaffold) and Part 2 (bookings + overlap engine, review fixes).
- **Already present for apartments:**
  - `Apartment` model in `app/models.py` (`id`, `title`, `description`, `address`, `price_per_night`, `max_guests`, `created_at`, `bookings` relationship).
  - `ApartmentBase`, `ApartmentCreate`, `ApartmentUpdate`, `ApartmentResponse` in `app/schemas.py`.
  - FK `bookings.apartment_id → apartments.id` with `ON DELETE RESTRICT`; `PRAGMA foreign_keys = ON` for every engine (including tests).
- **Missing:** `app/services/apartment_service.py`, `app/routers/apartments.py`, router registration in `app/main.py`, `tests/test_apartments.py`, service unit tests.
- **Gaps found in existing apartment schemas:** explicit `null` accepted in `ApartmentUpdate` (→ `500`), `Infinity` accepted for price, no upper bounds, unbounded `description`.

---

## 4. Verified and Measured Facts

| Metric / Check | Verified State | Source |
| :--- | :--- | :--- |
| **Active Git Branch** | `feature/part1-apartments` (from `main` @ `886bd46`) | `git branch --show-current` |
| **Existing Test Suite** | 33 passed in 1.33 s, 97% line coverage | `pytest` |
| **Runtime (verification env)** | Python 3.13.16, SQLite 3.45.1 | `python3 --version` |
| **Library Versions** | FastAPI 0.143.0, SQLAlchemy 2.1.4, Pydantic 2.14.1 | `pip` / `__version__` |
| **Apartment Endpoints** | None registered (only `/bookings`, `/health`) | `app/main.py` |
| **FK Enforcement in Tests** | Active — deleting a booked apartment raises `IntegrityError` | `tests/test_bookings.py` |

*The team's main development machine runs Python 3.14.6 (Part 0 plan); the code uses no version-specific features.*

---

## 5. Risks and Mitigations

### Risk 1: Deleting an Apartment Guests Have Booked
- **Context:** Hosts could remove an apartment that has upcoming confirmed stays.
- **Severity:** High.
- **Mitigation:** Active-booking check → `409`; FK `RESTRICT` as the final guard; `IntegrityError` is caught, rolled back, and mapped to `409`.

### Risk 2: Internal Server Errors from Invalid Updates
- **Context:** `{"title": null}` or `{"price_per_night": null}` passes a schema with `Optional[...]` fields and violates `NOT NULL`.
- **Severity:** High.
- **Mitigation:** Model validator in `ApartmentUpdate` rejecting `null` for required fields → `422`; regression tests for each field.

### Risk 3: Non-Finite or Absurd Numeric Values
- **Context:** `Infinity` price → infinite booking totals; huge `max_guests` values.
- **Severity:** Medium.
- **Mitigation:** `allow_inf_nan=False` and upper bounds on numeric fields (Decision 4).

### Risk 4: Unbounded List Responses
- **Context:** `GET /apartments` without limits loads the whole table into memory.
- **Severity:** Medium.
- **Mitigation:** Mandatory pagination with capped `limit` (Decision 6).

### Risk 5: Route Collision with the Part 3 Search Endpoint
- **Context:** `/apartments/search` would be captured by `/apartments/{apartment_id}`.
- **Severity:** Medium (affects the next phase).
- **Mitigation:** Documented in Decision 7 and in a comment in the router.

### Risk 6: Price Changes Affecting Existing Bookings
- **Context:** Updating `price_per_night` must not change totals of already-confirmed bookings.
- **Severity:** Low.
- **Mitigation:** `Booking.total_price` is stored at booking time; a test verifies it does not change after an apartment price update.

---

## 6. High-Level Implementation Stages

### Stage 1: Harden Model & Schemas (Step 1.1)
- Keep the `Apartment` model contract unchanged.
- Update `app/schemas.py`:
  - Apply bounds and finite-number checks from Decision 4 to `ApartmentBase` and `ApartmentUpdate`.
  - Normalize blank `description` to `None`.
  - Add a validator rejecting explicit `null` for required fields in `ApartmentUpdate`.
  - Make `ApartmentResponse` a plain output schema (no input constraints re-validated on output).
- Add schema unit tests.

### Stage 2: Apartment Service (Step 1.2, TDD)
- Write failing unit tests first (`tests/test_apartment_service.py`).
- Implement `app/services/apartment_service.py`:
  - `create_apartment(db, data)`
  - `get_apartments(db, limit, offset)`
  - `get_apartment_by_id(db, apartment_id)`
  - `update_apartment(db, apartment_id, data)` — partial update, `404` if missing.
  - `delete_apartment(db, apartment_id, today=None)` — deletion policy from Decision 5; `today` injectable for deterministic tests.

### Stage 3: Apartment Router (Step 1.3)
- Implement `app/routers/apartments.py` with the five endpoints, status codes, OpenAPI summaries, and documented error responses.
- Register the router in `app/main.py`.

### Stage 4: API Tests (Step 1.4)
- Create `tests/test_apartments.py`:
  - Full CRUD happy paths and `404`s.
  - Validation errors: negative/zero/infinite price, invalid `max_guests`, missing/blank required fields, `null` in `PUT`.
  - Partial update keeps untouched fields; `description` can be cleared.
  - Pagination and ordering.
  - Deletion: `409` with active booking; `204` with only cancelled/past bookings (history removed); cancelled booking no longer blocks deletion.
  - Price update does not change existing booking totals.

### Stage 5: Verification, Senior Review & Git
- Run `ruff check`, `ruff format --check`, `mypy app`, and the full `pytest` suite; fix all findings in new code.
- Perform the 11-point senior code review; fix all Critical/High/Medium issues.
- Commit with Conventional Commits on `feature/part1-apartments`, ready to merge into `main`.
