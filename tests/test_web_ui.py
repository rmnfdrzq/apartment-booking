"""Automated tests for Web UI single-page application and static asset delivery."""

from fastapi.testclient import TestClient


def test_web_ui_root_serves_html(client: TestClient) -> None:
    """Verify GET / delivers the main HTML single-page application with HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in response.text
    assert "Apartment Booking" in response.text


def test_web_ui_serves_css_stylesheet(client: TestClient) -> None:
    """Verify /static/styles.css is accessible with proper CSS mime type."""
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    assert "--primary:" in response.text


def test_web_ui_serves_javascript_app(client: TestClient) -> None:
    """Verify /static/app.js is accessible with proper JavaScript mime type."""
    response = client.get("/static/app.js")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert any(js_type in content_type for js_type in ("javascript", "application/x-javascript"))
    assert "setupSearchWorkflow" in response.text
    assert "setupApartmentsWorkflow" in response.text
    assert "setupBookingsWorkflow" in response.text


def test_web_ui_contains_all_workflow_forms_and_modals(client: TestClient) -> None:
    """Verify the HTML contains all forms, input fields, and modals for all 3 workflows."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Navigation tabs
    assert 'id="tab-search"' in html
    assert 'id="tab-apartments"' in html
    assert 'id="tab-bookings"' in html

    # Workflow 1: Search & Book
    assert 'id="search-form"' in html
    assert 'id="search-start-date"' in html
    assert 'id="search-end-date"' in html
    assert 'id="search-results-grid"' in html
    assert 'id="modal-booking"' in html
    assert 'id="form-create-booking"' in html
    assert 'id="book-guest-name"' in html
    assert 'id="book-guest-email"' in html
    assert 'id="book-total-price"' in html

    # Workflow 2: Apartment Catalog (Host)
    assert 'id="apartments-list-grid"' in html
    assert 'id="btn-open-add-apartment"' in html
    assert 'id="modal-add-apartment"' in html
    assert 'id="form-add-apartment"' in html
    assert 'id="modal-edit-apartment"' in html
    assert 'id="form-edit-apartment"' in html

    # Workflow 3: Bookings & Modifications
    assert 'id="bookings-table"' in html
    assert 'id="filter-booking-apartment"' in html
    assert 'id="modal-modify-booking"' in html
    assert 'id="form-modify-booking"' in html
    assert 'id="modify-booking-apartment"' in html


def test_static_nonexistent_file_returns_404(client: TestClient) -> None:
    """Verify requesting an unknown static file returns HTTP 404."""
    response = client.get("/static/nonexistent_file_12345.xyz")
    assert response.status_code == 404
