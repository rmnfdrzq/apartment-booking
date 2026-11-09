"""Tests for application health and root endpoints."""

from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient) -> None:
    """Verify /health returns HTTP 200 with service information."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "version" in data


def test_root_serves_web_app(client: TestClient) -> None:
    """Verify / serves the single-page web application frontend."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Apartment Booking" in response.text
    assert "search-form" in response.text
