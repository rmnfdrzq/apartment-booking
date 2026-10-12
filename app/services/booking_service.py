"""Business logic and overlap validation engine for bookings."""

from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus
from app.schemas import BookingCreate, BookingUpdate


def check_date_overlap(
    db: Session,
    apartment_id: str,
    start_date: date,
    end_date: date,
    exclude_booking_id: Optional[str] = None,
) -> bool:
    """Evaluate whether the given date window overlaps with any active booking.

    Uses half-open intervals [start_date, end_date):
    Conflict exists iff:
        Existing.start_date < Requested.end_date AND Existing.end_date > Requested.start_date
    Cancelled bookings are ignored.
    """
    query = db.query(Booking).filter(
        Booking.apartment_id == apartment_id,
        Booking.status == BookingStatus.CONFIRMED,
        Booking.start_date < end_date,
        Booking.end_date > start_date,
    )
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)

    return query.first() is not None


def create_booking(db: Session, data: BookingCreate) -> Booking:
    """Create a new booking after validating apartment existence and availability."""
    # 1. Verify target apartment exists
    apartment = db.query(Apartment).filter(Apartment.id == data.apartment_id).first()
    if not apartment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Apartment with ID '{data.apartment_id}' not found.",
        )

    # 2. Defensive date validation
    if data.start_date >= data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date (start_date) must be strictly before check-out date (end_date).",
        )

    # 3. Check for overlapping bookings
    if check_date_overlap(db, data.apartment_id, data.start_date, data.end_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Apartment is not available for the requested date range: "
                f"{data.start_date} to {data.end_date}. Collides with an existing booking."
            ),
        )

    # 4. Calculate total price
    nights = (data.end_date - data.start_date).days
    total_price = round(nights * apartment.price_per_night, 2)

    # 5. Persist booking
    booking = Booking(
        apartment_id=data.apartment_id,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        start_date=data.start_date,
        end_date=data.end_date,
        total_price=total_price,
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def get_booking_by_id(db: Session, booking_id: str) -> Optional[Booking]:
    """Retrieve a single booking by ID."""
    return db.query(Booking).filter(Booking.id == booking_id).first()


def get_all_bookings(db: Session, apartment_id: Optional[str] = None) -> List[Booking]:
    """Retrieve all bookings, optionally filtered by apartment ID."""
    query = db.query(Booking)
    if apartment_id:
        query = query.filter(Booking.apartment_id == apartment_id)
    return query.order_by(Booking.start_date.asc()).all()


def update_booking(db: Session, booking_id: str, data: BookingUpdate) -> Booking:
    """Update an existing booking, re-checking availability and re-calculating price if needed."""
    booking = get_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID '{booking_id}' not found.",
        )

    # Resolve target apartment and dates
    target_apartment_id = data.apartment_id or booking.apartment_id
    target_start_date = data.start_date or booking.start_date
    target_end_date = data.end_date or booking.end_date

    # Validate target dates
    if target_start_date >= target_end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date (start_date) must be strictly before check-out date (end_date).",
        )

    # Resolve target apartment entity for pricing and existence
    target_apartment = db.query(Apartment).filter(Apartment.id == target_apartment_id).first()
    if not target_apartment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target apartment with ID '{target_apartment_id}' not found.",
        )

    # If dates or apartment changed, re-validate overlap
    dates_or_apartment_changed = (
        target_apartment_id != booking.apartment_id
        or target_start_date != booking.start_date
        or target_end_date != booking.end_date
    )

    if dates_or_apartment_changed and booking.status == BookingStatus.CONFIRMED:
        # If staying in same apartment, exclude self from collision check
        exclude_id = booking.id if target_apartment_id == booking.apartment_id else None
        if check_date_overlap(
            db,
            target_apartment_id,
            target_start_date,
            target_end_date,
            exclude_booking_id=exclude_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Apartment is not available for the updated date range: "
                    f"{target_start_date} to {target_end_date}. Collides with an existing booking."
                ),
            )

    # Update attributes
    if data.guest_name is not None:
        booking.guest_name = data.guest_name
    if data.guest_email is not None:
        booking.guest_email = data.guest_email

    if dates_or_apartment_changed:
        booking.apartment_id = target_apartment_id
        booking.start_date = target_start_date
        booking.end_date = target_end_date
        nights = (target_end_date - target_start_date).days
        booking.total_price = round(nights * target_apartment.price_per_night, 2)

    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking_id: str) -> Booking:
    """Transition a booking status to CANCELLED, freeing its dates."""
    booking = get_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID '{booking_id}' not found.",
        )

    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return booking
