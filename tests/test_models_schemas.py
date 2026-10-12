"""Unit tests for models and Pydantic schemas."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.models import Apartment, Booking, BookingStatus
from app.schemas import ApartmentCreate, BookingCreate, BookingUpdate


def test_booking_create_schema_valid() -> None:
    """Verify that BookingCreate accepts valid dates and fields."""
    data = BookingCreate(
        apartment_id="apt-123",
        guest_name="Elena",
        guest_email="elena@example.com",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 5),
    )
    assert data.apartment_id == "apt-123"
    assert data.start_date < data.end_date


def test_booking_create_schema_invalid_dates() -> None:
    """Verify that BookingCreate rejects start_date >= end_date."""
    with pytest.raises(ValidationError) as exc_info:
        BookingCreate(
            apartment_id="apt-123",
            guest_name="Elena",
            guest_email="elena@example.com",
            start_date=date(2026, 11, 5),
            end_date=date(2026, 11, 5),
        )
    assert "start_date must be strictly before end_date" in str(exc_info.value)

    with pytest.raises(ValidationError):
        BookingCreate(
            apartment_id="apt-123",
            guest_name="Elena",
            guest_email="elena@example.com",
            start_date=date(2026, 11, 6),
            end_date=date(2026, 11, 5),
        )


def test_apartment_create_schema_price_validation() -> None:
    """Verify that ApartmentCreate rejects non-positive prices."""
    with pytest.raises(ValidationError):
        ApartmentCreate(
            title="Cozy Flat",
            address="Center",
            price_per_night=0.0,
            max_guests=2,
        )


def test_models_instantiation(db_session) -> None:
    """Verify ORM models can be persisted and related."""
    apt = Apartment(
        title="Alpine Retreat",
        address="Via Roma 1",
        price_per_night=100.0,
        max_guests=4,
    )
    db_session.add(apt)
    db_session.commit()
    db_session.refresh(apt)

    booking = Booking(
        apartment_id=apt.id,
        guest_name="Marco",
        guest_email="marco@example.com",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 5),
        total_price=400.0,
        status=BookingStatus.CONFIRMED,
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    assert booking.apartment_id == apt.id
    assert booking.status == BookingStatus.CONFIRMED
    assert len(apt.bookings) == 1
