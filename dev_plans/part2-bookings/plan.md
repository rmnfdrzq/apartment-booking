# Implementation Plan: Part 2 — Booking Lifecycle & Overlap Prevention Engine

**Document Path:** `/dev_plans/part2-bookings/plan.md`  
**Phase:** `feature/part2-bookings`  
**User Stories Covered:** **US2** (Manage Bookings) & **US4** (Prevent Overlapping Bookings)  
**Target Milestone:** Checkpoint 1 Core Business Logic  

---

## 1. Goal

Deliver a production-ready **Booking Subsystem** that handles the complete reservation lifecycle and strictly guarantees that no apartment can ever be double-booked for overlapping dates. 

By the end of this phase, the application will:
1. Provide persistent storage for `Apartment` and `Booking` entities with foreign key enforcement.
2. Calculate total stay pricing automatically based on nights stayed and target apartment rates.
3. Enforce mathematical interval overlap prevention returning HTTP `409 Conflict` on date collisions.
4. Support booking viewing, full updates (including date changes, guest info, and moving the booking to a different `apartment_id`), and soft-cancellation via `POST /bookings/{id}/cancel`.
5. Protect active reservations by rejecting apartment deletions with HTTP `409 Conflict` when confirmed future bookings exist.
6. Expose documented REST endpoints:
   - `POST /bookings` (create reservation with overlap check)
   - `GET /bookings` & `GET /bookings/{id}` (inspect reservations)
   - `PUT /bookings/{id}` (modify dates, guest info, or transfer to another apartment with overlap validation)
   - `POST /bookings/{id}/cancel` (soft-cancel reservation and release dates)
7. Deliver a comprehensive test suite (`tests/test_bookings.py` and `tests/test_overlap.py`) covering all lifecycle and collision edge cases.

---

## 2. Locked Decisions (Clarified & Confirmed)

### Decision 1: Half-Open Date Intervals $[check\_in, check\_out)$ for Stays
- **What:** Model stays as discrete calendar dates where `start_date` is the check-in day and `end_date` is the check-out day.
- **Why:** 
  - Standard in modern hospitality (Airbnb, Booking.com): a guest checks in during the afternoon of `start_date` and departs in the morning of `end_date`.
  - Same-day turnaround is permitted: Guest A checking out on `2026-11-05` and Guest B checking in on `2026-11-05` do **not** overlap.
  - Duration of stay is calculated exactly as `(end_date - start_date).days` nights.

### Decision 2: Canonical Overlap Condition Formula
- **What:** Two bookings $A$ and $B$ for the same apartment overlap if and only if:
  $$\text{Existing.start\_date} < \text{Requested.end\_date} \quad \text{AND} \quad \text{Existing.end\_date} > \text{Requested.start\_date} \quad \text{AND} \quad \text{status} \neq \text{'CANCELLED'}$$
- **Why:**
  - Evaluates to `True` for all 5 collision topologies (exact, left-overlap, right-overlap, enclosing, subset).
  - Evaluates to `False` for adjacent non-overlapping bookings ($E_1 \le S_2$ or $E_2 \le S_1$).

### Decision 3: Soft-Cancellation via Dedicated Action Endpoint
- **What:** Booking cancellation is exposed via `POST /bookings/{id}/cancel`, setting `status = 'CANCELLED'`.
- **Why:**
  - Preserves historical booking records and customer audit trails.
  - Automatically frees the calendar dates for subsequent bookings without erasing data.

### Decision 4: Full Booking Updates (`PUT /bookings/{id}`) Including Apartment Transfers
- **What:** A booking can be updated to change dates (`start_date`, `end_date`), guest info (`guest_name`, `guest_email`), AND `apartment_id` (moving to another apartment).
- **Why:**
  - Provides full flexibility for guests/hosts managing stays.
  - The service checks overlap on the target `apartment_id` (excluding the current booking if updating on the same apartment), verifies target apartment existence, and recalculates `total_price` based on the target apartment's nightly rate.

### Decision 5: Apartment Deletion Protection (Prevent Orphaned Stays)
- **What:** Deleting an apartment that has active/confirmed bookings is rejected with `409 Conflict`.
- **Why:**
  - Prevents hosts from accidentally deleting an apartment that guests have already paid for or reserved.
  - Preserves referential integrity in SQLite with `PRAGMA foreign_keys = ON;`.

### Decision 6: HTTP Status Codes & Error Payloads
- **What:**
  - `409 Conflict`: Overlap detected (`detail`: collision explanation) OR apartment deletion blocked by active bookings.
  - `400 Bad Request`: Invalid dates (`start_date >= end_date`).
  - `404 Not Found`: `apartment_id` or `booking_id` does not exist.
  - `201 Created`: Booking successfully created.
  - `200 OK`: Successful retrieval, update, or cancellation.

---

## 3. What Exists Today

- **Repository & Branch:** On dedicated branch `feature/part2-bookings`.
- **Persistence:** SQLite engine configured in `app/database.py` with foreign keys enabled, WAL mode active, and busy timeout set to 30s.
- **Configuration:** `app/config.py` with path resolution and environment settings.
- **Application Shell:** `app/main.py` with lifespan and `/health` route.
- **Test Infrastructure:** `tests/conftest.py` with in-memory SQLite (`StaticPool`), fresh per-request sessions, and `pyproject.toml` configuration.
- **Current Test Status:** 5 passed tests (100% green, 0 test pollution).

---

## 4. Verified and Measured Facts

| Metric / Check | Verified State |
| :--- | :--- |
| **Active Git Branch** | `feature/part2-bookings` |
| **Existing Test Suite** | 5/5 passing in 0.06s (`pytest`) |
| **SQLite Foreign Keys** | Active (`PRAGMA foreign_keys = 1` verified) |
| **SQLite Journal Mode** | `WAL` on disk, `StaticPool` in tests |
| **Runtime Environment** | Python `3.14.6` in `.venv` |
| **Persistence Directory** | `data/` directory tracked with `.gitkeep`, zero test pollution |

---

## 5. Risks and Mitigations

### Risk 1: Moving a Booking to Another Apartment (`apartment_id` Transfer)
- **Context:** If a booking changes its `apartment_id` during `PUT /bookings/{id}`, overlap checks must target the *new* apartment, not the old one. If updating within the *same* apartment, self-exclusion must apply.
- **Severity:** High.
- **Mitigation:** In `booking_service.update_booking()`:
  - If `new_apartment_id != current_apartment_id`: verify new apartment exists, check overlap on new apartment (without self-exclusion), and recalculate total price using new apartment's `price_per_night`.
  - If `new_apartment_id == current_apartment_id`: check overlap on current apartment with `exclude_booking_id=current_booking_id`.

### Risk 2: Timezone Mismatches in Date Comparisons
- **Context:** Using timestamps for date arithmetic can shift dates across UTC and local timezones.
- **Severity:** High.
- **Mitigation:** Use strict `datetime.date` objects exclusively for `start_date` and `end_date`.

### Risk 3: Zero-Night or Negative-Duration Bookings
- **Context:** User submits `start_date: 2026-11-05` and `end_date: 2026-11-05` (0 nights) or `end_date: 2026-11-01` (-4 nights).
- **Severity:** Medium.
- **Mitigation:** Pydantic validation via `@model_validator(mode="after")` and service-level guard throwing `400 Bad Request`.

---

## 6. High-Level Implementation Stages

### Stage 1: Data Models & Pydantic Validation Schemas
- Create `app/models.py`:
  - `BookingStatus` (Enum: `CONFIRMED`, `CANCELLED`).
  - `Apartment` table (id, title, description, address, price_per_night, max_guests, created_at).
  - `Booking` table (id, apartment_id FK, guest_name, guest_email, start_date, end_date, total_price, status, created_at).
- Create `app/schemas.py`:
  - `BookingCreate` (apartment_id, guest_name, guest_email, start_date, end_date) with date order validator.
  - `BookingUpdate` (start_date, end_date, guest_name, guest_email, apartment_id) with optional fields.
  - `BookingResponse` (all booking fields serialized for API output).
  - `ApartmentResponse` (base schema for apartment details).

### Stage 2: Overlap Detection Logic & Booking Service
- Create `app/services/booking_service.py`:
  - `check_date_overlap(db, apartment_id, start_date, end_date, exclude_booking_id=None)`: implements canonical interval query.
  - `create_booking(db, data)`: verifies apartment existence, validates dates, detects overlap, computes price, persists booking.
  - `get_booking_by_id(db, booking_id)`: fetches single booking.
  - `get_all_bookings(db)`: fetches list of bookings.
  - `update_booking(db, booking_id, data)`: handles date changes, guest info changes, and apartment transfers with appropriate overlap validation and price recalculation.
  - `cancel_booking(db, booking_id)`: transitions status to `CANCELLED`.

### Stage 3: REST Router & Error Handling
- Create `app/routers/bookings.py`:
  - `POST /bookings` $\to$ `201 Created` / `400 Bad Request` / `404 Not Found` / `409 Conflict`.
  - `GET /bookings` $\to$ `200 OK`.
  - `GET /bookings/{id}` $\to$ `200 OK` / `404 Not Found`.
  - `PUT /bookings/{id}` $\to$ `200 OK` / `400 Bad Request` / `404 Not Found` / `409 Conflict`.
  - `POST /bookings/{id}/cancel` $\to$ `200 OK` / `404 Not Found`.
- Register router in `app/main.py`.

### Stage 4: Comprehensive Automated Test Suite
- Create `tests/test_bookings.py`:
  - Test booking creation, retrieval, updates, and cancellations.
  - Test pricing calculation: nights $\times$ price per night.
  - Test apartment transfer with recalculation of new apartment price.
  - Test 404 on missing apartment/booking.
  - Test 400 on invalid date ranges (`start_date >= end_date`).
- Create `tests/test_overlap.py`:
  - Test Case 1: Exact date collision $\to$ `409 Conflict`.
  - Test Case 2: Overlapping start date $\to$ `409 Conflict`.
  - Test Case 3: Overlapping end date $\to$ `409 Conflict`.
  - Test Case 4: Enclosing date range $\to$ `409 Conflict`.
  - Test Case 5: Subset date range $\to$ `409 Conflict`.
  - Test Case 6: Same-day turnaround (checkout = check-in) $\to$ `201 Created` (allowed).
  - Test Case 7: Re-booking dates of a cancelled booking $\to$ `201 Created` (allowed).
  - Test Case 8: Updating booking dates without false self-collision $\to$ `200 OK`.

### Stage 5: Senior Review, Verification & Git Integration
- Execute `pytest` across all test files and assert 100% green execution.
- Verify zero test pollution in `data/`.
- Review and refine code against all 11 senior-level criteria.
- Merge `feature/part2-bookings` into `main` and push to remote.
