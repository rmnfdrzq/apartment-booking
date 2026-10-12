"""Unit tests for apartment Pydantic schemas (US1 input validation)."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import ApartmentCreate, ApartmentUpdate

VALID_APARTMENT: dict[str, Any] = {
    "title": "Old Town Studio",
    "description": "Quiet studio near the cathedral",
    "address": "Pilies g. 1, Vilnius",
    "price_per_night": 75.5,
    "max_guests": 2,
}


def test_apartment_create_valid_and_trims_whitespace() -> None:
    data = ApartmentCreate(**{**VALID_APARTMENT, "title": "  Old Town Studio  "})
    assert data.title == "Old Town Studio"
    assert data.price_per_night == 75.5


def test_apartment_create_defaults_max_guests_to_one() -> None:
    payload = {k: v for k, v in VALID_APARTMENT.items() if k != "max_guests"}
    assert ApartmentCreate(**payload).max_guests == 1


@pytest.mark.parametrize("description", ["", "   "])
def test_blank_description_is_stored_as_none(description: str) -> None:
    assert ApartmentCreate(**{**VALID_APARTMENT, "description": description}).description is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "   "),
        ("title", "x" * 256),
        ("address", ""),
        ("description", "x" * 5001),
        ("price_per_night", 0),
        ("price_per_night", -10),
        ("price_per_night", float("inf")),
        ("price_per_night", float("nan")),
        ("price_per_night", 1_000_000.01),
        ("max_guests", 0),
        ("max_guests", 101),
        ("max_guests", 2.5),
    ],
)
def test_apartment_create_rejects_invalid_values(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        ApartmentCreate(**{**VALID_APARTMENT, field: value})


@pytest.mark.parametrize("field", ["title", "address", "price_per_night"])
def test_apartment_create_requires_field(field: str) -> None:
    payload = {k: v for k, v in VALID_APARTMENT.items() if k != field}
    with pytest.raises(ValidationError):
        ApartmentCreate(**payload)


def test_apartment_update_tracks_only_sent_fields() -> None:
    data = ApartmentUpdate(title="New title")
    assert data.model_dump(exclude_unset=True) == {"title": "New title"}


@pytest.mark.parametrize("field", ["title", "address", "price_per_night", "max_guests"])
def test_apartment_update_rejects_null_for_required_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="cannot be null"):
        ApartmentUpdate(**{field: None})


def test_apartment_update_allows_clearing_description() -> None:
    assert ApartmentUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}
    assert ApartmentUpdate(description="  ").model_dump(exclude_unset=True) == {"description": None}


def test_apartment_update_applies_same_bounds_as_create() -> None:
    with pytest.raises(ValidationError):
        ApartmentUpdate(price_per_night=-1)
    with pytest.raises(ValidationError):
        ApartmentUpdate(max_guests=0)
