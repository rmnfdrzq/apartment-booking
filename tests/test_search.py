"""Tests for the date range availability search (US3)."""

from datetime import date
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Apartment, Booking, BookingStatus
from app.services import apartment_service

# Search window used by most tests: check-in 10 Nov, check-out 15 Nov (5 nights).
START = date(2026, 11, 10)
END = date(2026, 11, 15)


def add_apartment(db: Session, title: str) -> Apartment:
    apartment = Apartment(title=title, address="Gedimino pr. 1, Vilnius", price_per_night=80.0, max_guests=2)
    db.add(apartment)
    db.commit()
    db.refresh(apartment)
    return apartment


def add_booking(
    db: Session,
    apartment: Apartment,
    start: date,
    end: date,
    status: BookingStatus = BookingStatus.CONFIRMED,
) -> Booking:
    booking = Booking(
        apartment_id=apartment.id,
        guest_name="Ona",
        guest_email="ona@example.com",
        start_date=start,
        end_date=end,
        total_price=100.0,
        status=status,
    )
    db.add(booking)
    db.commit()
    return booking


def search_ids(db: Session, start: date = START, end: date = END, **kwargs: int) -> list[str]:
    return [a.id for a in apartment_service.search_available_apartments(db, start, end, **kwargs)]


# --- service: availability rules ----------------------------------------------


def test_search_returns_empty_list_when_no_apartments(db_session: Session) -> None:
    assert search_ids(db_session) == []


def test_search_returns_apartment_without_bookings(db_session: Session) -> None:
    apartment = add_apartment(db_session, "Free")
    assert search_ids(db_session) == [apartment.id]


def test_search_returns_only_available_apartments(db_session: Session) -> None:
    free = add_apartment(db_session, "Free")
    booked = add_apartment(db_session, "Booked")
    add_booking(db_session, booked, date(2026, 11, 12), date(2026, 11, 14))

    assert search_ids(db_session) == [free.id]


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 10), date(2026, 11, 15)),  # exact same stay
        (date(2026, 11, 8), date(2026, 11, 11)),  # overlaps check-in day
        (date(2026, 11, 14), date(2026, 11, 20)),  # overlaps last night
        (date(2026, 11, 1), date(2026, 11, 30)),  # encloses the whole window
        (date(2026, 11, 11), date(2026, 11, 12)),  # one night inside the window
    ],
)
def test_search_excludes_apartment_with_overlapping_booking(db_session: Session, start: date, end: date) -> None:
    apartment = add_apartment(db_session, "Booked")
    add_booking(db_session, apartment, start, end)

    assert search_ids(db_session) == []


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 5), date(2026, 11, 10)),  # previous guest checks out on our check-in day
        (date(2026, 11, 15), date(2026, 11, 18)),  # next guest checks in on our check-out day
        (date(2026, 10, 1), date(2026, 10, 5)),  # long before
        (date(2026, 12, 1), date(2026, 12, 5)),  # long after
    ],
)
def test_search_includes_apartment_with_adjacent_or_distant_booking(
    db_session: Session, start: date, end: date
) -> None:
    apartment = add_apartment(db_session, "Turnaround")
    add_booking(db_session, apartment, start, end)

    assert search_ids(db_session) == [apartment.id]


def test_search_includes_apartment_with_cancelled_booking(db_session: Session) -> None:
    apartment = add_apartment(db_session, "Cancelled stay")
    add_booking(db_session, apartment, START, END, status=BookingStatus.CANCELLED)

    assert search_ids(db_session) == [apartment.id]


def test_search_excludes_when_any_of_several_bookings_overlaps(db_session: Session) -> None:
    apartment = add_apartment(db_session, "Busy")
    add_booking(db_session, apartment, date(2026, 11, 1), date(2026, 11, 5))
    add_booking(db_session, apartment, START, END, status=BookingStatus.CANCELLED)
    add_booking(db_session, apartment, date(2026, 11, 14), date(2026, 11, 16))

    assert search_ids(db_session) == []


def test_search_paginates_in_catalog_order(db_session: Session) -> None:
    apartments = [add_apartment(db_session, f"Apartment {i}") for i in range(5)]
    add_booking(db_session, apartments[1], START, END)
    expected = [a.id for a in sorted(apartments, key=lambda a: (a.created_at, a.id)) if a.id != apartments[1].id]

    assert search_ids(db_session, limit=2, offset=0) + search_ids(db_session, limit=2, offset=2) == expected
    assert search_ids(db_session, limit=2, offset=4) == []


@pytest.mark.parametrize(("start", "end"), [(END, START), (START, START)])
def test_search_rejects_invalid_date_window(db_session: Session, start: date, end: date) -> None:
    with pytest.raises(HTTPException) as exc_info:
        apartment_service.search_available_apartments(db_session, start, end)
    assert exc_info.value.status_code == 400


# --- API: GET /apartments/search ----------------------------------------------


def create_apartment(client: TestClient, title: str) -> dict[str, Any]:
    response = client.post(
        "/apartments",
        json={"title": title, "address": "Gedimino pr. 1, Vilnius", "price_per_night": 80.0, "max_guests": 2},
    )
    assert response.status_code == 201, response.text
    return response.json()


def booking_payload(apartment_id: str, start: date = START, end: date = END) -> dict[str, str]:
    return {
        "apartment_id": apartment_id,
        "guest_name": "Ona",
        "guest_email": "ona@example.com",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def search(client: TestClient, start: date = START, end: date = END, **params: Any) -> Any:
    return client.get(
        "/apartments/search",
        params={"start_date": start.isoformat(), "end_date": end.isoformat(), **params},
    )


def test_search_endpoint_returns_available_apartments(client: TestClient) -> None:
    free = create_apartment(client, "Free")
    booked = create_apartment(client, "Booked")
    assert client.post("/bookings", json=booking_payload(booked["id"])).status_code == 201

    response = search(client)

    assert response.status_code == 200
    assert response.json() == [free]


def test_search_route_is_not_shadowed_by_apartment_id_route(client: TestClient) -> None:
    create_apartment(client, "Free")

    response = search(client)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_endpoint_includes_apartment_again_after_cancellation(client: TestClient) -> None:
    apartment = create_apartment(client, "Popular")
    booking = client.post("/bookings", json=booking_payload(apartment["id"])).json()
    assert search(client).json() == []

    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 200

    assert [a["id"] for a in search(client).json()] == [apartment["id"]]


def test_search_endpoint_reflects_changed_booking_dates(client: TestClient) -> None:
    apartment = create_apartment(client, "Moved stay")
    booking = client.post("/bookings", json=booking_payload(apartment["id"])).json()

    moved = client.put(f"/bookings/{booking['id']}", json={"start_date": "2026-12-01", "end_date": "2026-12-05"})
    assert moved.status_code == 200

    assert [a["id"] for a in search(client).json()] == [apartment["id"]]


def test_search_results_are_bookable_and_excluded_ones_are_not(client: TestClient) -> None:
    """US3 and US4 must agree: found means bookable, excluded means 409."""
    apartments = [create_apartment(client, f"Apartment {i}") for i in range(4)]
    client.post("/bookings", json=booking_payload(apartments[0]["id"], date(2026, 11, 8), date(2026, 11, 11)))
    client.post("/bookings", json=booking_payload(apartments[1]["id"], date(2026, 11, 5), date(2026, 11, 10)))
    client.post("/bookings", json=booking_payload(apartments[2]["id"], date(2026, 11, 14), date(2026, 11, 20)))

    found = {a["id"] for a in search(client).json()}

    assert found == {apartments[1]["id"], apartments[3]["id"]}
    for apartment in apartments:
        status_code = client.post("/bookings", json=booking_payload(apartment["id"])).status_code
        assert status_code == (201 if apartment["id"] in found else 409)


@pytest.mark.parametrize(("start", "end"), [(END, START), (START, START)])
def test_search_endpoint_invalid_date_window_returns_400(client: TestClient, start: date, end: date) -> None:
    response = search(client, start, end)

    assert response.status_code == 400
    assert "start_date" in response.json()["detail"]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_date": "2026-11-10"},
        {"end_date": "2026-11-15"},
        {"start_date": "10-11-2026", "end_date": "2026-11-15"},
        {"start_date": "2026-02-30", "end_date": "2026-03-05"},
        {"start_date": "2026-11-10", "end_date": "2026-11-15", "limit": 0},
        {"start_date": "2026-11-10", "end_date": "2026-11-15", "limit": 501},
        {"start_date": "2026-11-10", "end_date": "2026-11-15", "offset": -1},
    ],
)
def test_search_endpoint_invalid_query_returns_422(client: TestClient, params: dict[str, Any]) -> None:
    assert client.get("/apartments/search", params=params).status_code == 422


def test_search_endpoint_pagination(client: TestClient) -> None:
    ids = [create_apartment(client, f"Apartment {i}")["id"] for i in range(3)]
    all_found = [a["id"] for a in search(client).json()]

    page = search(client, limit=1, offset=1).json()

    assert sorted(all_found) == sorted(ids)
    assert [a["id"] for a in page] == all_found[1:2]


def test_search_endpoint_documented_in_openapi(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/apartments/search"]["get"]

    params = {p["name"]: p for p in operation["parameters"]}
    assert params["start_date"]["required"] is True
    assert params["end_date"]["required"] is True
    assert "400" in operation["responses"]
