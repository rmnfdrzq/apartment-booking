# Implementation Plan: Part 3 — Availability Search Engine

**Document Path:** `/dev_plans/part3-search/plan.md`  
**Phase:** `feature/part3-search`  
**User Stories Covered:** **US3** (Search for apartments available during a date range)  
**Target Milestone:** Checkpoint 1 Cross-Entity Features  

---

## 1. Goal

Deliver a production-ready **Availability Search** so that a guest can find a place to book for given travel dates. By the end of this phase, the application will:

1. Expose `GET /apartments/search?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` returning every apartment that has **no confirmed booking overlapping** the requested stay.
2. Reject invalid date windows (`start_date >= end_date`) with `400 Bad Request`, and missing or malformed dates with `422 Unprocessable Entity`.
3. Guarantee that search (US3) and overlap prevention (US4) can never disagree: an apartment returned by the search can be booked for the same dates, and an excluded apartment is rejected with `409 Conflict`.
4. Keep the query efficient as the number of apartments and bookings grows.
5. Ship `tests/test_search.py` covering availability rules, validation, and pagination, with the whole existing suite still green.

---

## 2. Locked Decisions

### Decision 1: Same Half-Open Interval Rule as Overlap Prevention
- **What:** The requested stay is `[start_date, end_date)` (check-in inclusive, check-out exclusive). An apartment is unavailable if and only if it has a booking where:
  $$\text{status} = \text{CONFIRMED} \quad \text{AND} \quad \text{Booking.start\_date} < \text{search\_end} \quad \text{AND} \quad \text{Booking.end\_date} > \text{search\_start}$$
- **Why:**
  - Identical to the Part 2 locked decision, so same-day turnaround stays allowed (a guest may arrive on the day another leaves).
  - Cancelled bookings never block availability.

### Decision 2: One Shared Overlap Predicate (DRY)
- **What:** Extract the overlap condition into a single function `active_overlap_condition(start_date, end_date)` in `app/services/booking_service.py`. Both `check_date_overlap()` (US4) and the new search (US3) use it.
- **Why:**
  - Two copies of the same rule would drift over time; a guest could then see an apartment in search results and still get `409` when booking it.
  - A consistency test locks this guarantee in place.

### Decision 3: `NOT EXISTS` Correlated Subquery Instead of `NOT IN`
- **What:** Implement the roadmap SQL as `WHERE NOT EXISTS (SELECT 1 FROM bookings WHERE bookings.apartment_id = apartments.id AND <overlap>)`.
- **Why:**
  - Same result as `NOT IN` (here `apartment_id` is `NOT NULL`), but it lets SQLite probe the existing composite index `ix_bookings_apartment_status_dates (apartment_id, status, start_date, end_date)` per apartment instead of building the full list of booked IDs first.
  - It stays safe against the `NOT IN` + `NULL` pitfall if the schema changes later.

### Decision 4: Validation Split — 422 for Format, 400 for Business Rule
- **What:**
  - `start_date` and `end_date` are required query parameters typed as `date`; missing or malformed values → `422` (FastAPI default).
  - `start_date >= end_date` → `400 Bad Request` with a clear `detail` message.
- **Why:** Matches the roadmap, the README contract, and the booking service (which also returns `400` for an invalid date order).

### Decision 5: Paginated, Stable Results Reusing the Catalog Ordering
- **What:** `limit` (1–500, default 100) and `offset` (≥ 0) query parameters; results ordered by `created_at`, then `id`.
- **Why:**
  - Same contract as `GET /apartments` and `GET /bookings`.
  - Reuses the existing `ix_apartments_created_at_id` index and keeps pages stable.

### Decision 6: Route Declared Before `/apartments/{apartment_id}`
- **What:** `GET /apartments/search` is registered in `app/routers/apartments.py` above the `/{apartment_id}` routes.
- **Why:** Otherwise FastAPI matches `search` as an apartment ID and returns `404` (documented as a risk in the Part 1 plan).

### Decision 7: Out of Scope
- Filtering by guest count or price, and limits on how far ahead a guest can search, are not part of US3. They can be added later as optional query parameters without breaking this contract.

---

## 3. What Exists Today

- **Branch:** `feature/part3-search`, created from `main` at `56abc76` (Part 1 merged via PR #1).
- **Merged on `main`:** Part 0 (scaffold), Part 1 (apartment catalog), Part 2 (bookings + overlap engine).
- **Reusable building blocks:**
  - `Apartment` and `Booking` models; `BookingStatus` enum.
  - `check_date_overlap()` in `booking_service.py` with the canonical interval rule.
  - Composite index `ix_bookings_apartment_status_dates` and `ix_apartments_created_at_id`.
  - `ApartmentResponse` schema and the `/apartments` router (with a note reserving the position of `/search`).
- **Missing:** search service function, `GET /apartments/search` endpoint, `tests/test_search.py`.
- **Documentation gap:** `README.md` already documents `GET /apartments/search`, but the endpoint does not exist yet (the request currently returns `404`).

---

## 4. Verified and Measured Facts

| Metric / Check | Verified State | Source |
| :--- | :--- | :--- |
| **Active Git Branch** | `feature/part3-search` (from `main` @ `56abc76`) | `git branch --show-current` |
| **Existing Test Suite** | 118 passed, 98% coverage | `pytest` |
| **Search Endpoint** | Not registered (`/apartments/search` matched as an ID → `404`) | `app/routers/apartments.py` |
| **Overlap Rule** | Defined once in `check_date_overlap()` | `app/services/booking_service.py` |
| **Booking Index** | `(apartment_id, status, start_date, end_date)` present | `app/models.py` |
| **Runtime (verification env)** | Python 3.13.16, SQLite 3.45.1 | `python3 --version` |

---

## 5. Risks and Mitigations

### Risk 1: Search and Booking Disagree on Availability
- **Context:** If the search uses a different overlap rule than booking creation, guests see apartments they cannot book (or miss free ones).
- **Severity:** High.
- **Mitigation:** Shared predicate (Decision 2) and a consistency test: every returned apartment books with `201`, every excluded one returns `409`.

### Risk 2: Route Shadowing by `/{apartment_id}`
- **Context:** `/apartments/search` captured as `get_apartment("search")`.
- **Severity:** High.
- **Mitigation:** Route order (Decision 6) and a test that calls the real URL.

### Risk 3: Off-by-One at Stay Boundaries
- **Context:** Treating check-out day as occupied would hide apartments that are actually free (same-day turnaround).
- **Severity:** Medium.
- **Mitigation:** Strict `<` / `>` comparisons; boundary tests for check-out = search start and check-in = search end.

### Risk 4: Query Cost Growing with Data Volume
- **Context:** A naive implementation loads all bookings into Python or scans the bookings table for every apartment.
- **Severity:** Medium.
- **Mitigation:** Single SQL query with `NOT EXISTS` on the composite index (Decision 3), pagination (Decision 5); verified with `EXPLAIN QUERY PLAN`.

### Risk 5: Time-of-Check vs Time-of-Use
- **Context:** An apartment shown as free may be booked by someone else before the guest submits a booking.
- **Severity:** Low (expected behavior of any search).
- **Mitigation:** Search is informational only; `POST /bookings` re-checks overlap and returns `409`, so a double booking is still impossible.

---

## 6. High-Level Implementation Stages

### Stage 1: Shared Overlap Predicate
- Add `active_overlap_condition(start_date, end_date)` to `booking_service.py`.
- Refactor `check_date_overlap()` to use it without changing behavior (existing overlap tests must stay green).

### Stage 2: Availability Search Service (TDD)
- Write failing unit tests first.
- Implement `search_available_apartments(db, start_date, end_date, limit, offset)` in `app/services/apartment_service.py`:
  - `400` if `start_date >= end_date`.
  - `NOT EXISTS` subquery using the shared predicate; ordered and paginated like the catalog.

### Stage 3: Search Endpoint
- Add `GET /apartments/search` to `app/routers/apartments.py` above the `/{apartment_id}` routes, with required `start_date` / `end_date`, `limit` / `offset`, OpenAPI summary and documented `400` response.

### Stage 4: Tests (`tests/test_search.py`)
- Only available apartments are returned; booked apartments are excluded.
- Apartments with cancelled bookings are included.
- Boundary cases: same-day turnaround on both sides; partial, enclosing, and contained overlaps excluded.
- Validation: `400` for `start_date >= end_date`; `422` for missing or malformed dates and invalid pagination.
- Route is not shadowed by `/{apartment_id}`.
- Consistency with booking creation (US3 ↔ US4).
- Cancelling a booking makes the apartment appear again.

### Stage 5: Verification, Senior Review & Git
- Run linter, formatter, type checker, and the full `pytest` suite; fix every finding in new code.
- Check the query plan with `EXPLAIN QUERY PLAN`.
- Perform the 11-point senior code review; fix all Critical/High/Medium issues.
- Mark Phase 3 steps as done in `dev_plans/roadmap.md`.
- Commit with Conventional Commits on `feature/part3-search` and push for review.
