"""Integration tests for the /apartments REST API (US1)."""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

APARTMENT: dict[str, Any] = {
    "title": "Old Town Studio",
    "description": "Quiet studio near the cathedral",
    "address": "Pilies g. 1, Vilnius",
    "price_per_night": 75.5,
    "max_guests": 2,
}


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/apartments", json={**APARTMENT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def book(client: TestClient, apartment_id: str, start: date, end: date) -> dict[str, Any]:
    response = client.post(
        "/bookings",
        json={
            "apartment_id": apartment_id,
            "guest_name": "Ona",
            "guest_email": "ona@example.com",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- create ------------------------------------------------------------------


def test_create_apartment_returns_201_with_body(client: TestClient) -> None:
    data = create(client)

    assert data["id"]
    assert data["created_at"]
    for field, value in APARTMENT.items():
        assert data[field] == value


@pytest.mark.parametrize(
    "payload_change",
    [
        {"price_per_night": -10},
        {"price_per_night": 0},
        {"price_per_night": "abc"},
        {"max_guests": 0},
        {"max_guests": 101},
        {"title": ""},
        {"title": "   "},
        {"address": "x" * 256},
        {"description": "x" * 5001},
    ],
)
def test_create_apartment_invalid_values_return_422(client: TestClient, payload_change: dict[str, Any]) -> None:
    response = client.post("/apartments", json={**APARTMENT, **payload_change})
    assert response.status_code == 422


@pytest.mark.parametrize("missing", ["title", "address", "price_per_night"])
def test_create_apartment_missing_required_field_returns_422(client: TestClient, missing: str) -> None:
    payload = {k: v for k, v in APARTMENT.items() if k != missing}
    assert client.post("/apartments", json=payload).status_code == 422


@pytest.mark.parametrize("literal", ["Infinity", "NaN"])
def test_create_apartment_rejects_non_finite_price(client: TestClient, literal: str) -> None:
    body = f'{{"title": "Studio", "address": "Pilies g. 1", "price_per_night": {literal}, "max_guests": 2}}'
    response = client.post("/apartments", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


# --- read --------------------------------------------------------------------


def test_list_apartments_empty(client: TestClient) -> None:
    response = client.get("/apartments")
    assert response.status_code == 200
    assert response.json() == []


def test_list_apartments_returns_created(client: TestClient) -> None:
    ids = {create(client, title=f"Apartment {i}")["id"] for i in range(3)}

    response = client.get("/apartments")

    assert response.status_code == 200
    assert {a["id"] for a in response.json()} == ids


def test_list_apartments_pagination(client: TestClient) -> None:
    for i in range(5):
        create(client, title=f"Apartment {i}")

    all_ids = [a["id"] for a in client.get("/apartments").json()]
    page = client.get("/apartments", params={"limit": 2, "offset": 2}).json()

    assert [a["id"] for a in page] == all_ids[2:4]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
def test_list_apartments_invalid_pagination_returns_422(client: TestClient, params: dict[str, int]) -> None:
    assert client.get("/apartments", params=params).status_code == 422


def test_get_apartment_by_id(client: TestClient) -> None:
    created = create(client)

    response = client.get(f"/apartments/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_apartment_returns_404(client: TestClient) -> None:
    response = client.get("/apartments/does-not-exist")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# --- update ------------------------------------------------------------------


def test_update_apartment_partial(client: TestClient) -> None:
    created = create(client)

    response = client.put(f"/apartments/{created['id']}", json={"title": "Renovated Studio", "max_guests": 4})

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Renovated Studio"
    assert data["max_guests"] == 4
    assert data["address"] == created["address"]
    assert data["price_per_night"] == created["price_per_night"]
    assert data["id"] == created["id"]
    assert data["created_at"] == created["created_at"]
    assert client.get(f"/apartments/{created['id']}").json() == data


def test_update_apartment_clears_description(client: TestClient) -> None:
    created = create(client)
    response = client.put(f"/apartments/{created['id']}", json={"description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None


@pytest.mark.parametrize("field", ["title", "address", "price_per_night", "max_guests"])
def test_update_apartment_null_required_field_returns_422(client: TestClient, field: str) -> None:
    created = create(client)

    response = client.put(f"/apartments/{created['id']}", json={field: None})

    assert response.status_code == 422
    assert client.get(f"/apartments/{created['id']}").json() == created


def test_update_apartment_invalid_price_returns_422(client: TestClient) -> None:
    created = create(client)
    assert client.put(f"/apartments/{created['id']}", json={"price_per_night": -5}).status_code == 422


def test_update_missing_apartment_returns_404(client: TestClient) -> None:
    assert client.put("/apartments/does-not-exist", json={"title": "X"}).status_code == 404


def test_update_price_keeps_existing_booking_total(client: TestClient) -> None:
    apartment = create(client, price_per_night=100.0)
    start = date.today() + timedelta(days=10)
    booking = book(client, apartment["id"], start, start + timedelta(days=2))

    client.put(f"/apartments/{apartment['id']}", json={"price_per_night": 300.0})

    assert client.get(f"/bookings/{booking['id']}").json()["total_price"] == 200.0


# --- delete ------------------------------------------------------------------


def test_delete_apartment_returns_204_and_removes_it(client: TestClient) -> None:
    created = create(client)

    response = client.delete(f"/apartments/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/apartments/{created['id']}").status_code == 404
    assert client.get("/apartments").json() == []


def test_delete_missing_apartment_returns_404(client: TestClient) -> None:
    assert client.delete("/apartments/does-not-exist").status_code == 404


def test_delete_apartment_with_upcoming_booking_returns_409(client: TestClient) -> None:
    apartment = create(client)
    start = date.today() + timedelta(days=5)
    booking = book(client, apartment["id"], start, start + timedelta(days=3))

    response = client.delete(f"/apartments/{apartment['id']}")

    assert response.status_code == 409
    assert "active booking" in response.json()["detail"]
    assert client.get(f"/apartments/{apartment['id']}").status_code == 200
    assert client.get(f"/bookings/{booking['id']}").status_code == 200


def test_delete_apartment_after_booking_cancelled_returns_204(client: TestClient) -> None:
    apartment = create(client)
    start = date.today() + timedelta(days=5)
    booking = book(client, apartment["id"], start, start + timedelta(days=3))
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 200

    response = client.delete(f"/apartments/{apartment['id']}")

    assert response.status_code == 204
    assert client.get(f"/bookings/{booking['id']}").status_code == 404


def test_delete_apartment_with_finished_booking_returns_204(client: TestClient) -> None:
    apartment = create(client)
    start = date.today() - timedelta(days=10)
    booking = book(client, apartment["id"], start, start + timedelta(days=3))

    assert client.delete(f"/apartments/{apartment['id']}").status_code == 204
    assert client.get(f"/bookings/{booking['id']}").status_code == 404


def test_deleted_apartment_cannot_be_booked(client: TestClient) -> None:
    apartment = create(client)
    client.delete(f"/apartments/{apartment['id']}")

    start = date.today() + timedelta(days=1)
    response = client.post(
        "/bookings",
        json={
            "apartment_id": apartment["id"],
            "guest_name": "Ona",
            "guest_email": "ona@example.com",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 404


# --- documentation -----------------------------------------------------------


def test_apartment_endpoints_documented_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/apartments"]) == {"get", "post"}
    assert set(paths["/apartments/{apartment_id}"]) == {"get", "put", "delete"}
    assert "409" in paths["/apartments/{apartment_id}"]["delete"]["responses"]
