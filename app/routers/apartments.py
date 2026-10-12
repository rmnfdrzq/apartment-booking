"""REST router for the apartment catalog (US1)."""

from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Apartment
from app.schemas import ApartmentCreate, ApartmentResponse, ApartmentUpdate
from app.services import apartment_service

router = APIRouter(
    prefix="/apartments",
    tags=["Apartments"],
)

NOT_FOUND_RESPONSE: Dict[Union[int, str], Dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "Apartment not found"},
}

# NOTE (Part 3): declare GET /apartments/search ABOVE the /{apartment_id} routes,
# otherwise "search" is matched as an apartment ID.


@router.post(
    "",
    response_model=ApartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an apartment",
    description="Create a new apartment listing with title, address, nightly price, and guest capacity.",
)
def create_apartment(
    payload: ApartmentCreate,
    db: Session = Depends(get_db),
) -> Apartment:
    """Create a new apartment."""
    return apartment_service.create_apartment(db, payload)


@router.get(
    "",
    response_model=List[ApartmentResponse],
    summary="List apartments",
    description="Retrieve apartments in creation order with pagination.",
)
def list_apartments(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of apartments to return"),
    offset: int = Query(0, ge=0, description="Number of apartments to skip"),
    db: Session = Depends(get_db),
) -> List[Apartment]:
    """List apartments with pagination."""
    return apartment_service.get_apartments(db, limit=limit, offset=offset)


@router.get(
    "/{apartment_id}",
    response_model=ApartmentResponse,
    summary="Get apartment details",
    description="Retrieve a single apartment by ID.",
    responses=NOT_FOUND_RESPONSE,
)
def get_apartment(
    apartment_id: str,
    db: Session = Depends(get_db),
) -> Apartment:
    """Get a single apartment by ID."""
    apartment = apartment_service.get_apartment_by_id(db, apartment_id)
    if apartment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Apartment with ID '{apartment_id}' not found.",
        )
    return apartment


@router.put(
    "/{apartment_id}",
    response_model=ApartmentResponse,
    summary="Update an apartment",
    description=(
        "Partially update an apartment: only the fields sent in the body are changed. "
        "Prices of already confirmed bookings are not affected."
    ),
    responses=NOT_FOUND_RESPONSE,
)
def update_apartment(
    apartment_id: str,
    payload: ApartmentUpdate,
    db: Session = Depends(get_db),
) -> Apartment:
    """Update an existing apartment."""
    return apartment_service.update_apartment(db, apartment_id, payload)


@router.delete(
    "/{apartment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove an apartment",
    description=(
        "Delete an apartment together with its cancelled and finished bookings. "
        "Rejected with 409 Conflict while the apartment has active (upcoming or ongoing) bookings."
    ),
    responses={
        **NOT_FOUND_RESPONSE,
        status.HTTP_409_CONFLICT: {"description": "Apartment has active bookings"},
    },
)
def delete_apartment(
    apartment_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an apartment."""
    apartment_service.delete_apartment(db, apartment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
