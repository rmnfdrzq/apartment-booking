"""Integration tests for Booking lifecycle and operations (US2)."""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus


def create_sample_apartment(db: Session, title: str = "Central Loft", price: float = 100.0) -> Apartment:
    """Helper to persist a test apartment."""
    apt = Apartment(
        title=title,
        description="Cozy space",
        address="Piazza Walther 1",
        price_per_night=price,
        max_guests=2,
    )
    db.add(apt)
    db.commit()
    db.refresh(apt)
    return apt


def test_create_booking_success(client: TestClient, db_session: Session) -> None:
    """Verify that creating a booking succeeds with 201 and computes correct total price."""
    apt = create_sample_apartment(db_session, price=120.0)

    payload = {
        "apartment_id": apt.id,
        "guest_name": "Elena Rossi",
        "guest_email": "elena@example.com",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",  # 4 nights
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["apartment_id"] == apt.id
    assert data["guest_name"] == "Elena Rossi"
    assert data["total_price"] == 480.0  # 4 * 120
    assert data["status"] == "CONFIRMED"
    assert "id" in data


def test_create_booking_invalid_email(client: TestClient, db_session: Session) -> None:
    """Verify that booking creation rejects invalid email addresses."""
    apt = create_sample_apartment(db_session)
    payload = {
        "apartment_id": apt.id,
        "guest_name": "Elena Rossi",
        "guest_email": "not-an-email",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 422


def test_create_booking_whitespace_name(client: TestClient, db_session: Session) -> None:
    """Verify that whitespace-only guest names are rejected."""
    apt = create_sample_apartment(db_session)
    payload = {
        "apartment_id": apt.id,
        "guest_name": "   ",
        "guest_email": "elena@example.com",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 422


def test_create_booking_nonexistent_apartment(client: TestClient) -> None:
    """Verify that booking a non-existent apartment returns 404."""
    payload = {
        "apartment_id": "non-existent-id",
        "guest_name": "Ghost",
        "guest_email": "ghost@example.com",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_booking_invalid_dates(client: TestClient, db_session: Session) -> None:
    """Verify that booking with start_date >= end_date returns 422."""
    apt = create_sample_apartment(db_session)
    payload = {
        "apartment_id": apt.id,
        "guest_name": "Elena",
        "guest_email": "elena@example.com",
        "start_date": "2026-11-05",
        "end_date": "2026-11-05",  # 0 nights
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 422


def test_get_booking_by_id(client: TestClient, db_session: Session) -> None:
    """Verify fetching a booking by ID."""
    apt = create_sample_apartment(db_session)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Marco",
            "guest_email": "marco@example.com",
            "start_date": "2026-12-01",
            "end_date": "2026-12-04",
        },
    )
    booking_id = create_resp.json()["id"]

    get_resp = client.get(f"/bookings/{booking_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == booking_id

    # Non-existent ID
    assert client.get("/bookings/unknown-id").status_code == 404


def test_list_bookings_and_pagination(client: TestClient, db_session: Session) -> None:
    """Verify listing bookings with pagination and apartment filtering."""
    apt1 = create_sample_apartment(db_session, title="Apt 1")
    apt2 = create_sample_apartment(db_session, title="Apt 2")

    for i in range(5):
        client.post(
            "/bookings",
            json={
                "apartment_id": apt1.id,
                "guest_name": f"Guest {i}",
                "guest_email": f"g{i}@example.com",
                "start_date": f"2026-11-0{i+1}",
                "end_date": f"2026-11-0{i+2}",
            },
        )

    # Test limit and offset
    resp_page1 = client.get("/bookings?limit=2&offset=0")
    assert resp_page1.status_code == 200
    assert len(resp_page1.json()) == 2

    resp_page2 = client.get("/bookings?limit=2&offset=2")
    assert resp_page2.status_code == 200
    assert len(resp_page2.json()) == 2
    assert resp_page1.json() != resp_page2.json()

    # Filter by apartment
    filtered_resp = client.get(f"/bookings?apartment_id={apt1.id}")
    assert len(filtered_resp.json()) == 5


def test_update_booking_dates_and_recalculate_price(client: TestClient, db_session: Session) -> None:
    """Verify updating dates recalculates price properly."""
    apt = create_sample_apartment(db_session, price=100.0)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",  # 2 nights = 200
        },
    )
    booking_id = create_resp.json()["id"]
    assert create_resp.json()["total_price"] == 200.0

    # Extend to 4 nights
    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"end_date": "2026-11-05"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["total_price"] == 400.0
    assert update_resp.json()["end_date"] == "2026-11-05"


def test_update_booking_transfer_apartment(client: TestClient, db_session: Session) -> None:
    """Verify moving a booking to another apartment updates apartment_id and recalculates total_price."""
    apt1 = create_sample_apartment(db_session, title="Economy", price=50.0)
    apt2 = create_sample_apartment(db_session, title="Luxury", price=200.0)

    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt1.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-04",  # 3 nights = 150
        },
    )
    booking_id = create_resp.json()["id"]
    assert create_resp.json()["total_price"] == 150.0

    # Transfer to apt2
    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"apartment_id": apt2.id},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["apartment_id"] == apt2.id
    assert update_resp.json()["total_price"] == 600.0  # 3 * 200


def test_update_booking_guest_info_only(client: TestClient, db_session: Session) -> None:
    """Verify updating guest name and email without altering dates."""
    apt = create_sample_apartment(db_session)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
        },
    )
    booking_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"guest_name": "Elena Rossi Updated", "guest_email": "new.email@example.com"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["guest_name"] == "Elena Rossi Updated"
    assert update_resp.json()["guest_email"] == "new.email@example.com"
    assert update_resp.json()["total_price"] == create_resp.json()["total_price"]


def test_update_booking_errors(client: TestClient, db_session: Session) -> None:
    """Verify error handling on booking update: 404, 400 on invalid dates."""
    apt = create_sample_apartment(db_session)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
        },
    )
    booking_id = create_resp.json()["id"]

    # 1. Update non-existent booking
    assert client.put("/bookings/non-existent-id", json={"guest_name": "New"}).status_code == 404

    # 2. Transfer to non-existent apartment
    resp = client.put(f"/bookings/{booking_id}", json={"apartment_id": "unknown-apt"})
    assert resp.status_code == 404

    # 3. Invalid date order where new start_date is after existing end_date
    resp = client.put(f"/bookings/{booking_id}", json={"start_date": "2026-11-10"})
    assert resp.status_code == 400


def test_cannot_update_cancelled_booking(client: TestClient, db_session: Session) -> None:
    """Verify that updating a cancelled booking is rejected with 400 Bad Request."""
    apt = create_sample_apartment(db_session)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
        },
    )
    booking_id = create_resp.json()["id"]

    # Cancel booking
    client.post(f"/bookings/{booking_id}/cancel")

    # Attempt update on cancelled booking
    update_resp = client.put(f"/bookings/{booking_id}", json={"guest_name": "Attempt"})
    assert update_resp.status_code == 400
    assert "cannot modify a cancelled booking" in update_resp.json()["detail"].lower()


def test_cancel_booking(client: TestClient, db_session: Session) -> None:
    """Verify cancelling a booking marks status as CANCELLED and is idempotent."""
    apt = create_sample_apartment(db_session)
    create_resp = client.post(
        "/bookings",
        json={
            "apartment_id": apt.id,
            "guest_name": "Elena",
            "guest_email": "elena@example.com",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
        },
    )
    booking_id = create_resp.json()["id"]

    cancel_resp = client.post(f"/bookings/{booking_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Idempotent re-cancel returns 200
    recancel_resp = client.post(f"/bookings/{booking_id}/cancel")
    assert recancel_resp.status_code == 200

    # Non-existent booking cancel returns 404
    assert client.post("/bookings/unknown-id/cancel").status_code == 404


def test_foreign_key_restricts_apartment_deletion_with_active_bookings(db_session: Session) -> None:
    """Verify that deleting an apartment with active bookings is restricted by foreign key."""
    apt = create_sample_apartment(db_session)
    booking = Booking(
        apartment_id=apt.id,
        guest_name="Elena",
        guest_email="elena@example.com",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 5),
        total_price=400.0,
        status=BookingStatus.CONFIRMED,
    )
    db_session.add(booking)
    db_session.commit()

    # Attempting to delete the apartment directly should raise IntegrityError due to RESTRICT
    db_session.delete(apt)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
