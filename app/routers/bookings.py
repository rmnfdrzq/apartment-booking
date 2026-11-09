"""REST router for Booking management and overlap prevention (US2, US4)."""

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    BookingCreate,
    BookingResponse,
    BookingUpdate,
    ErrorResponse,
    ValidationErrorResponse,
)
from app.services import booking_service

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)

BOOKING_NOT_FOUND_RESPONSE: Dict[Union[int, str], Dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Booking not found",
    },
}


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
    description="Reserve an apartment for a specified date range. Rejects overlapping bookings with 409 Conflict.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid dates (e.g. check-in date is not before check-out date)",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Apartment not found",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Apartment is not available for the requested date range (collision with existing booking)",
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "Validation error in request payload",
        },
    },
)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Create a new booking."""
    return booking_service.create_booking(db, payload)


@router.get(
    "",
    response_model=List[BookingResponse],
    summary="List all bookings",
    description="Retrieve all bookings with pagination, optionally filtered by apartment ID.",
    responses={
        422: {
            "model": ValidationErrorResponse,
            "description": "Invalid query parameters (limit or offset out of bounds)",
        },
    },
)
def list_bookings(
    apartment_id: Optional[str] = Query(None, description="Filter by apartment ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of bookings to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> List[BookingResponse]:
    """List bookings with pagination."""
    return booking_service.get_all_bookings(db, apartment_id=apartment_id, limit=limit, offset=offset)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get booking details",
    description="Retrieve full details for a specific booking by ID.",
    responses=BOOKING_NOT_FOUND_RESPONSE,
)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Get single booking by ID."""
    booking = booking_service.get_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID '{booking_id}' not found.",
        )
    return booking


@router.put(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Update a booking",
    description="Update dates, guest information, or move booking to another apartment.",
    responses={
        **BOOKING_NOT_FOUND_RESPONSE,
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid dates or attempting to modify a cancelled booking",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Apartment is not available for updated dates (collision with existing booking)",
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "Validation error in request payload",
        },
    },
)
def update_booking(
    booking_id: str,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Update an existing booking."""
    return booking_service.update_booking(db, booking_id, payload)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    description="Mark booking status as CANCELLED, freeing up the dates for new reservations.",
    responses=BOOKING_NOT_FOUND_RESPONSE,
)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Cancel booking."""
    return booking_service.cancel_booking(db, booking_id)
