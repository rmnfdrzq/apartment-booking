"""Tests for OpenAPI specification and documentation completeness."""

import json
from pathlib import Path
from fastapi.testclient import TestClient


def test_openapi_spec_structure_and_metadata(client: TestClient) -> None:
    """Verify that OpenAPI spec contains application metadata and tags."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    assert spec["info"]["title"] == "Apartment Booking API"
    assert "tags" in spec
    tag_names = {t["name"] for t in spec["tags"]}
    assert {"Apartments", "Bookings", "System"}.issubset(tag_names)


def test_openapi_endpoints_and_status_codes_documented(client: TestClient) -> None:
    """Verify that all REST endpoints document status codes and error responses."""
    paths = client.get("/openapi.json").json()["paths"]

    # /apartments
    assert "post" in paths["/apartments"]
    assert "201" in paths["/apartments"]["post"]["responses"]
    assert "422" in paths["/apartments"]["post"]["responses"]

    assert "get" in paths["/apartments"]
    assert "200" in paths["/apartments"]["get"]["responses"]

    # /apartments/search
    assert "get" in paths["/apartments/search"]
    assert "200" in paths["/apartments/search"]["get"]["responses"]
    assert "400" in paths["/apartments/search"]["get"]["responses"]
    assert "422" in paths["/apartments/search"]["get"]["responses"]

    # /apartments/{apartment_id}
    apt_id_path = paths["/apartments/{apartment_id}"]
    assert "404" in apt_id_path["get"]["responses"]
    assert "404" in apt_id_path["put"]["responses"]
    assert "409" in apt_id_path["delete"]["responses"]

    # /bookings
    assert "post" in paths["/bookings"]
    assert "201" in paths["/bookings"]["post"]["responses"]
    assert "400" in paths["/bookings"]["post"]["responses"]
    assert "404" in paths["/bookings"]["post"]["responses"]
    assert "409" in paths["/bookings"]["post"]["responses"]

    # /bookings/{booking_id}
    booking_id_path = paths["/bookings/{booking_id}"]
    assert "404" in booking_id_path["get"]["responses"]
    assert "400" in booking_id_path["put"]["responses"]
    assert "409" in booking_id_path["put"]["responses"]

    # /bookings/{booking_id}/cancel
    assert "post" in paths["/bookings/{booking_id}/cancel"]
    assert "404" in paths["/bookings/{booking_id}/cancel"]["post"]["responses"]


def test_openapi_schemas_have_examples(client: TestClient) -> None:
    """Verify that Pydantic schemas in components contain example payloads."""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    assert "ApartmentCreate" in schemas
    assert "example" in schemas["ApartmentCreate"]

    assert "ApartmentResponse" in schemas
    assert "example" in schemas["ApartmentResponse"]

    assert "BookingCreate" in schemas
    assert "example" in schemas["BookingCreate"]

    assert "BookingResponse" in schemas
    assert "example" in schemas["BookingResponse"]

    assert "ErrorResponse" in schemas
    assert "example" in schemas["ErrorResponse"]


def test_exported_openapi_json_matches_live_spec(client: TestClient) -> None:
    """Verify that docs/openapi.json in the repository is in sync with the live application spec."""
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    assert docs_path.exists(), "docs/openapi.json must exist in the repository"

    with open(docs_path, encoding="utf-8") as f:
        exported_spec = json.load(f)

    live_spec = client.get("/openapi.json").json()
    assert exported_spec == live_spec
