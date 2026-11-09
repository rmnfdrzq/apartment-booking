"""Integration tests for Overlapping Booking Prevention Engine (US4)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus


@pytest.fixture
def sample_apartment(db_session: Session) -> Apartment:
    """Fixture providing an apartment for overlap testing."""
    apt = Apartment(
        title="Dolomite Penthouse",
        description="Luxury stay with view",
        address="Via Monte 10, Bolzano",
        price_per_night=150.0,
        max_guests=4,
    )
    db_session.add(apt)
    db_session.commit()
    db_session.refresh(apt)
    return apt


@pytest.fixture
def baseline_booking(client: TestClient, sample_apartment: Apartment) -> dict:
    """Fixture providing an initial confirmed booking for Nov 10 to Nov 15."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Primary Guest",
            "guest_email": "primary@example.com",
            "start_date": "2026-11-10",
            "end_date": "2026-11-15",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_overlap_exact_match(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 1: Attempt booking on the exact same dates (Nov 10 - Nov 15) -> 409 Conflict."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Collision Guest",
            "guest_email": "collision@example.com",
            "start_date": "2026-11-10",
            "end_date": "2026-11-15",
        },
    )
    assert response.status_code == 409
    assert "collides with an existing booking" in response.json()["detail"].lower()


def test_overlap_starts_before_and_ends_inside(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 2: Requested starts before and ends inside (Nov 8 - Nov 12) -> 409 Conflict."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Left Overlap",
            "guest_email": "left@example.com",
            "start_date": "2026-11-08",
            "end_date": "2026-11-12",
        },
    )
    assert response.status_code == 409


def test_overlap_starts_inside_and_ends_after(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 3: Requested starts inside and ends after (Nov 13 - Nov 18) -> 409 Conflict."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Right Overlap",
            "guest_email": "right@example.com",
            "start_date": "2026-11-13",
            "end_date": "2026-11-18",
        },
    )
    assert response.status_code == 409


def test_overlap_enclosing_date_range(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 4: Requested completely encloses existing (Nov 5 - Nov 20) -> 409 Conflict."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Enclosing Overlap",
            "guest_email": "enclosing@example.com",
            "start_date": "2026-11-05",
            "end_date": "2026-11-20",
        },
    )
    assert response.status_code == 409


def test_overlap_subset_interior_date_range(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 5: Requested is a subset inside existing (Nov 11 - Nov 14) -> 409 Conflict."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Interior Overlap",
            "guest_email": "interior@example.com",
            "start_date": "2026-11-11",
            "end_date": "2026-11-14",
        },
    )
    assert response.status_code == 409


def test_same_day_turnaround_before(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 6: Adjacent before (Nov 5 - Nov 10). Checkout on Nov 10 matches check-in on Nov 10 -> 201 Created."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Adjacent Before",
            "guest_email": "before@example.com",
            "start_date": "2026-11-05",
            "end_date": "2026-11-10",
        },
    )
    assert response.status_code == 201


def test_same_day_turnaround_after(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 7: Adjacent after (Nov 15 - Nov 20). Check-in on Nov 15 matches checkout on Nov 15 -> 201 Created."""
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Adjacent After",
            "guest_email": "after@example.com",
            "start_date": "2026-11-15",
            "end_date": "2026-11-20",
        },
    )
    assert response.status_code == 201


def test_rebooking_cancelled_booking_dates(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 8: Re-booking dates of a cancelled booking -> 201 Created."""
    booking_id = baseline_booking["id"]
    # 1. Cancel baseline booking
    cancel_resp = client.post(f"/bookings/{booking_id}/cancel")
    assert cancel_resp.status_code == 200

    # 2. Re-book the exact same dates
    response = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "New Guest for freed dates",
            "guest_email": "new@example.com",
            "start_date": "2026-11-10",
            "end_date": "2026-11-15",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "CONFIRMED"


def test_update_booking_without_false_self_collision(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 9: Updating an existing booking on the same apartment does NOT collide with itself."""
    booking_id = baseline_booking["id"]

    # Extend stay by 1 day (Nov 10 - Nov 16)
    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"end_date": "2026-11-16"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["end_date"] == "2026-11-16"


def test_update_booking_collides_with_another_booking(
    client: TestClient,
    sample_apartment: Apartment,
    baseline_booking: dict,
) -> None:
    """Case 10: Updating booking A to overlap with existing booking B -> 409 Conflict."""
    # Create booking B (Nov 20 - Nov 25)
    resp_b = client.post(
        "/bookings",
        json={
            "apartment_id": sample_apartment.id,
            "guest_name": "Guest B",
            "guest_email": "b@example.com",
            "start_date": "2026-11-20",
            "end_date": "2026-11-25",
        },
    )
    assert resp_b.status_code == 201
    booking_b_id = resp_b.json()["id"]

    # Try moving booking B to overlap with baseline (Nov 10 - Nov 15)
    update_resp = client.put(
        f"/bookings/{booking_b_id}",
        json={"start_date": "2026-11-12", "end_date": "2026-11-17"},
    )
    assert update_resp.status_code == 409
    assert "collides with an existing booking" in update_resp.json()["detail"].lower()
