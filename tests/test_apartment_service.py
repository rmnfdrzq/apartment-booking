"""Unit tests for the apartment service layer (US1)."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus
from app.schemas import ApartmentCreate, ApartmentUpdate
from app.services import apartment_service

TODAY = date(2026, 10, 12)


def make_apartment(db: Session, title: str = "Riverside Loft", price: float = 90.0) -> Apartment:
    return apartment_service.create_apartment(
        db,
        ApartmentCreate(
            title=title,
            description="Two rooms by the river",
            address="Upės g. 5, Vilnius",
            price_per_night=price,
            max_guests=3,
        ),
    )


def add_booking(
    db: Session,
    apartment: Apartment,
    start: date,
    end: date,
    status: BookingStatus = BookingStatus.CONFIRMED,
) -> Booking:
    booking = Booking(
        apartment_id=apartment.id,
        guest_name="Guest",
        guest_email="guest@example.com",
        start_date=start,
        end_date=end,
        total_price=100.0,
        status=status,
    )
    db.add(booking)
    db.commit()
    return booking


# --- create / read -----------------------------------------------------------


def test_create_apartment_persists_all_fields(db_session: Session) -> None:
    apt = make_apartment(db_session)

    assert apt.id
    assert apt.created_at is not None
    stored = db_session.get(Apartment, apt.id)
    assert stored is not None
    assert (stored.title, stored.address, stored.price_per_night, stored.max_guests) == (
        "Riverside Loft",
        "Upės g. 5, Vilnius",
        90.0,
        3,
    )


def test_get_apartment_by_id_returns_none_when_missing(db_session: Session) -> None:
    assert apartment_service.get_apartment_by_id(db_session, "does-not-exist") is None


def test_get_apartment_by_id_returns_apartment(db_session: Session) -> None:
    apt = make_apartment(db_session)
    found = apartment_service.get_apartment_by_id(db_session, apt.id)
    assert found is not None
    assert found.id == apt.id


def test_get_apartments_empty(db_session: Session) -> None:
    assert apartment_service.get_apartments(db_session) == []


def test_get_apartments_paginates_in_creation_order(db_session: Session) -> None:
    created = [make_apartment(db_session, title=f"Apartment {i}") for i in range(5)]
    expected_order = sorted(created, key=lambda a: (a.created_at, a.id))

    first_page = apartment_service.get_apartments(db_session, limit=2, offset=0)
    second_page = apartment_service.get_apartments(db_session, limit=2, offset=2)
    last_page = apartment_service.get_apartments(db_session, limit=2, offset=4)

    assert [a.id for a in first_page + second_page + last_page] == [a.id for a in expected_order]
    assert len(last_page) == 1


# --- update ------------------------------------------------------------------


def test_update_apartment_changes_only_sent_fields(db_session: Session) -> None:
    apt = make_apartment(db_session)

    updated = apartment_service.update_apartment(
        db_session, apt.id, ApartmentUpdate(title="Renovated Loft", price_per_night=110.0)
    )

    assert updated.title == "Renovated Loft"
    assert updated.price_per_night == 110.0
    assert updated.address == "Upės g. 5, Vilnius"
    assert updated.description == "Two rooms by the river"
    assert updated.max_guests == 3


def test_update_apartment_can_clear_description(db_session: Session) -> None:
    apt = make_apartment(db_session)
    updated = apartment_service.update_apartment(db_session, apt.id, ApartmentUpdate(description=None))
    assert updated.description is None


def test_update_apartment_with_empty_payload_is_noop(db_session: Session) -> None:
    apt = make_apartment(db_session)
    updated = apartment_service.update_apartment(db_session, apt.id, ApartmentUpdate())
    assert updated.title == "Riverside Loft"


def test_update_apartment_missing_raises_404(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        apartment_service.update_apartment(db_session, "missing", ApartmentUpdate(title="X"))
    assert exc_info.value.status_code == 404


def test_update_price_does_not_change_existing_booking_totals(db_session: Session) -> None:
    apt = make_apartment(db_session)
    booking = add_booking(db_session, apt, date(2026, 11, 1), date(2026, 11, 3))

    apartment_service.update_apartment(db_session, apt.id, ApartmentUpdate(price_per_night=500.0))

    db_session.refresh(booking)
    assert booking.total_price == 100.0


# --- delete ------------------------------------------------------------------


def test_delete_apartment_without_bookings(db_session: Session) -> None:
    apt = make_apartment(db_session)
    apt_id = apt.id

    apartment_service.delete_apartment(db_session, apt_id, today=TODAY)

    assert apartment_service.get_apartment_by_id(db_session, apt_id) is None


def test_delete_apartment_missing_raises_404(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        apartment_service.delete_apartment(db_session, "missing", today=TODAY)
    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 1), date(2026, 11, 5)),  # upcoming stay
        (date(2026, 10, 10), date(2026, 10, 14)),  # guest is staying right now
        (date(2026, 10, 11), date(2026, 10, 13)),  # checks out tomorrow
    ],
)
def test_delete_apartment_with_active_booking_raises_409(db_session: Session, start: date, end: date) -> None:
    apt = make_apartment(db_session)
    add_booking(db_session, apt, start, end)

    with pytest.raises(HTTPException) as exc_info:
        apartment_service.delete_apartment(db_session, apt.id, today=TODAY)

    assert exc_info.value.status_code == 409
    assert db_session.get(Apartment, apt.id) is not None
    assert db_session.scalars(select(Booking)).all() != []


def test_delete_apartment_removes_cancelled_and_finished_bookings(db_session: Session) -> None:
    apt = make_apartment(db_session)
    other = make_apartment(db_session, title="Other")
    add_booking(db_session, apt, date(2026, 12, 1), date(2026, 12, 5), status=BookingStatus.CANCELLED)
    add_booking(db_session, apt, date(2026, 9, 1), date(2026, 9, 5))  # finished
    add_booking(db_session, apt, date(2026, 10, 8), date(2026, 10, 12))  # checked out today
    other_booking = add_booking(db_session, other, date(2026, 11, 1), date(2026, 11, 5))
    apt_id = apt.id

    apartment_service.delete_apartment(db_session, apt_id, today=TODAY)

    assert db_session.get(Apartment, apt_id) is None
    remaining = db_session.scalars(select(Booking)).all()
    assert [b.id for b in remaining] == [other_booking.id]


def test_delete_apartment_defaults_to_current_date(db_session: Session) -> None:
    apt = make_apartment(db_session)
    add_booking(db_session, apt, date(2000, 1, 1), date(2000, 1, 3))  # long finished
    apt_id = apt.id

    apartment_service.delete_apartment(db_session, apt_id)

    assert db_session.get(Apartment, apt_id) is None


def test_delete_apartment_concurrent_active_booking_rolls_back(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If an active booking appears after the check, the FK RESTRICT guard must win."""
    apt = make_apartment(db_session)
    active = add_booking(db_session, apt, date(2026, 11, 1), date(2026, 11, 5))
    cancelled = add_booking(db_session, apt, date(2026, 12, 1), date(2026, 12, 5), status=BookingStatus.CANCELLED)
    # Simulate the race: the active-booking check sees nothing.
    monkeypatch.setattr(db_session, "scalar", lambda *_args, **_kwargs: 0)

    with pytest.raises(HTTPException) as exc_info:
        apartment_service.delete_apartment(db_session, apt.id, today=TODAY)

    assert exc_info.value.status_code == 409
    monkeypatch.undo()
    db_session.expire_all()
    assert db_session.get(Apartment, apt.id) is not None
    remaining = {b.id for b in db_session.scalars(select(Booking)).all()}
    assert remaining == {active.id, cancelled.id}


def test_booking_for_concurrently_deleted_apartment_returns_404(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting an apartment between booking validation and insert must not cause a 500."""
    from app.schemas import BookingCreate
    from app.services import booking_service
    from tests.conftest import TestingSessionLocal

    apt = make_apartment(db_session)
    apt_id = apt.id
    real_overlap_check = booking_service.check_date_overlap

    def delete_then_check(*args: object, **kwargs: object) -> bool:
        other_request = TestingSessionLocal()
        try:
            apartment_service.delete_apartment(other_request, apt_id, today=TODAY)
        finally:
            other_request.close()
        return real_overlap_check(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(booking_service, "check_date_overlap", delete_then_check)

    with pytest.raises(HTTPException) as exc_info:
        booking_service.create_booking(
            db_session,
            BookingCreate(
                apartment_id=apt_id,
                guest_name="Ona",
                guest_email="ona@example.com",
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 3),
            ),
        )

    assert exc_info.value.status_code == 404
    assert db_session.scalars(select(Booking)).all() == []
