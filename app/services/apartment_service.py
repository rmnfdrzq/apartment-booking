"""Business logic for the apartment catalog (US1) and availability search (US3)."""

from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus
from app.schemas import ApartmentCreate, ApartmentUpdate
from app.services.booking_service import active_overlap_condition


def _not_found(apartment_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Apartment with ID '{apartment_id}' not found.",
    )


def _active_bookings_conflict(apartment_id: str, count: Optional[int] = None) -> HTTPException:
    amount = f"{count} active booking(s)" if count else "active bookings"
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Apartment with ID '{apartment_id}' has {amount}. "
            "Cancel or wait for these stays to finish before deleting the apartment."
        ),
    )


def _get_or_404(db: Session, apartment_id: str) -> Apartment:
    apartment = get_apartment_by_id(db, apartment_id)
    if apartment is None:
        raise _not_found(apartment_id)
    return apartment


def create_apartment(db: Session, data: ApartmentCreate) -> Apartment:
    """Persist a new apartment listing."""
    apartment = Apartment(**data.model_dump())
    db.add(apartment)
    db.commit()
    db.refresh(apartment)
    return apartment


CATALOG_ORDER = (Apartment.created_at.asc(), Apartment.id.asc())


def get_apartments(db: Session, limit: int = 100, offset: int = 0) -> List[Apartment]:
    """Return a page of apartments in stable creation order."""
    statement = select(Apartment).order_by(*CATALOG_ORDER).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


def search_available_apartments(
    db: Session,
    start_date: date,
    end_date: date,
    limit: int = 100,
    offset: int = 0,
) -> List[Apartment]:
    """Return apartments with no confirmed booking overlapping the stay [start_date, end_date).

    Uses the same overlap rule as booking creation, so every apartment returned here
    can be booked for these dates (unless someone else books it first).
    """
    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date (start_date) must be strictly before check-out date (end_date).",
        )

    has_overlapping_booking = exists().where(
        Booking.apartment_id == Apartment.id,
        active_overlap_condition(start_date, end_date),
    )
    statement = select(Apartment).where(~has_overlapping_booking).order_by(*CATALOG_ORDER).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


def get_apartment_by_id(db: Session, apartment_id: str) -> Optional[Apartment]:
    """Return a single apartment, or None if it does not exist."""
    return db.get(Apartment, apartment_id)


def update_apartment(db: Session, apartment_id: str, data: ApartmentUpdate) -> Apartment:
    """Apply a partial update: only fields present in the request are changed.

    Existing bookings keep their stored total_price, so a price change never
    alters reservations that were already confirmed.
    """
    apartment = _get_or_404(db, apartment_id)

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return apartment

    for field, value in changes.items():
        setattr(apartment, field, value)

    db.commit()
    db.refresh(apartment)
    return apartment


def delete_apartment(db: Session, apartment_id: str, today: Optional[date] = None) -> None:
    """Delete an apartment unless guests still have an active stay in it.

    A booking is active when it is CONFIRMED and its check-out date is after today.
    Historical bookings (cancelled or already finished) are removed in the same
    transaction, because the foreign key is ON DELETE RESTRICT.

    Only historical rows are deleted explicitly: if an active booking is created
    concurrently, the RESTRICT constraint makes the commit fail and the whole
    transaction is rolled back instead of deleting a live reservation.
    """
    apartment = _get_or_404(db, apartment_id)
    current_day = today or date.today()

    active_bookings = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.apartment_id == apartment_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.end_date > current_day,
        )
    )
    if active_bookings:
        raise _active_bookings_conflict(apartment_id, active_bookings)

    db.execute(
        delete(Booking).where(
            Booking.apartment_id == apartment_id,
            or_(
                Booking.status == BookingStatus.CANCELLED,
                Booking.end_date <= current_day,
            ),
        )
    )
    db.delete(apartment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _active_bookings_conflict(apartment_id) from None
